"""
特許構成要件分割・検索システム
Patent Component Analysis and Search System

このモジュールは特許の構成要件を分割し、適切な検索式を作成して
先行技術調査を実施するためのシステムです。
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.oauth2 import service_account
import requests


# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ComponentElement:
    """構成要素（構成要件）のデータモデル"""
    構成要素番号: str  # 例: "1a", "2b"
    構成要素: str  # 構成要素のテキスト
    構成要素のサポート箇所: str  # 全文の中でサポートする記載箇所
    構成要素の簡単説明: str  # 簡単な説明
    構成要素の従属関係: str  # 従属関係を示す記号 (例: "|", "->")
    構成要素の重要度: float  # 0.0～1.0の重要度

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)


@dataclass
class ComponentKeywords:
    """構成要素のキーワード情報"""
    構成要素番号: str
    基本キーワード: List[str]
    同義語類義語: List[str]
    上位概念: List[str]
    下位概念: List[str]
    機能キーワード: List[str]
    専門用語: List[str]

    def get_all_keywords(self) -> List[str]:
        """全てのキーワードを取得"""
        return (self.基本キーワード + self.同義語類義語 +
                self.上位概念 + self.下位概念 +
                self.機能キーワード + self.専門用語)


@dataclass
class ComponentClassification:
    """構成要素の特許分類コード情報"""
    構成要素番号: str
    FI分類: List[str]
    IPC分類: List[str]
    CPC分類: List[str]
    予備検索CPC: List[str]
    最終分類: List[str]  # 統合された最終的な分類コード


class SearchRangeAdjustment(Enum):
    """検索範囲の調整方向"""
    EXPAND = "expand"  # 拡大
    NARROW = "narrow"  # 縮小
    MAINTAIN = "maintain"  # 維持


# ============================================================================
# Gemini Client
# ============================================================================

class GeminiClient:
    """Google Gemini API クライアント (Vertex AI経由)"""

    def __init__(self,
                 service_account_path: str,
                 project_id: str = "ttdc-in-house-dev",
                 location: str = "us-central1",
                 model_name: str = "gemini-2.5-pro"):
        """
        初期化

        Args:
            service_account_path: サービスアカウントJSONファイルのパス
            project_id: Google Cloud プロジェクトID
            location: リージョン（デフォルト: us-central1）
            model_name: 使用するGeminiモデル名
        """
        self.service_account_path = service_account_path
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self._configure_api()

    def _configure_api(self):
        """API設定"""
        try:
            # サービスアカウント認証
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )

            # Vertex AIの初期化
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=credentials
            )

            # Geminiモデルの取得
            self.model = GenerativeModel(self.model_name)

            logger.info(f"Vertex AI Gemini configured - Project: {self.project_id}, "
                       f"Location: {self.location}, Model: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to configure Vertex AI Gemini API: {e}")
            raise

    def generate_content(self, prompt: str,
                        temperature: float = 0.7,
                        max_output_tokens: int = 8192) -> str:
        """
        コンテンツ生成

        Args:
            prompt: プロンプト
            temperature: 温度パラメータ
            max_output_tokens: 最大出力トークン数

        Returns:
            生成されたテキスト
        """
        try:
            # 生成設定
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

            # コンテンツ生成
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            return response.text

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise


# ============================================================================
# Component Analyzer
# ============================================================================

class PatentComponentAnalyzer:
    """特許構成要件分析クラス"""

    def __init__(self, gemini_client: GeminiClient):
        """
        初期化

        Args:
            gemini_client: GeminiClientインスタンス
        """
        self.gemini = gemini_client

    def analyze_patent_components(self, patent_data: str) -> List[ComponentElement]:
        """
        特許データを構成要件に分割

        Args:
            patent_data: PDF/XML形式の特許データ（テキスト化されたもの）

        Returns:
            構成要素のリスト
        """
        prompt = self._create_component_analysis_prompt(patent_data)

        logger.info("Analyzing patent components with Gemini...")
        response = self.gemini.generate_content(prompt, temperature=0.3)

        # JSONレスポンスをパース
        components = self._parse_component_response(response)

        logger.info(f"Extracted {len(components)} components")
        return components

    def _create_component_analysis_prompt(self, patent_data: str) -> str:
        """構成要件分割プロンプトの作成"""

        prompt = f"""
入力されたPDF/XMLのデータの特許の全てを確認して下記の要求通りに構成要件表を生成してください。

# 要求

発明全体と完全に一致する先行技術（ドンピシャの文献）が見つかることは稀です。
発明を小さな要素（構成要件）に分解することで、個々の要素や、いくつかの要素の組み合わせを開示する文献を広く探し出すことができます。

特許性を判断する上で、新規性だけでなく**進歩性**（容易に思いつけたか否か）も重要です。
各構成要件が公知であるか、また、それらを組み合わせることが容易であったか（動機付けがあるか）を検討するために、まず発明を要素に分解する必要があります。

## 分割方法

以下の方法から、入力特許の内容によって適切な方法を選択して分割してください：

1. **クレームの文言に従う**
   - クレームの記載を文法的に解釈し、「〜部材と、」「〜手段と、」「〜する工程と、」といった名詞句や動詞句を単位として抽出します。
   - 「及び」「並びに」「であって」「有し」「備え」などの接続詞や句読点（、。）は、要素の区切りを示していることが多いです。

2. **機能的・構造的単位で区切る**
   - 発明を構成する部品・部材（構造的単位）や、それらが果たす役割・機能（機能的単位）に着目して分割します。

3. **発明の「課題解決手段」を意識する**
   - 発明が解決しようとする課題（従来技術の問題点）と、その課題を解決するための手段（本発明の特徴）を意識します。
   - 特に特徴部分（従来技術と異なる部分）は、調査の核となるため、より詳細に分割・分析することが重要です。

4. **「必須の構成」か「任意の構成」かを見極める**
   - まずは必須の構成要件（独立請求項に記載の全要件）を漏れなく抽出することが基本です。

## 重要な注意点

- 細かすぎる分割は避ける：意味のある機能的・構造的なまとまりを意識してください
- 発明の一体性：分割はあくまで分析のためであり、最終的にはそれらの要素が組み合わさって本願発明の課題を解決していることを念頭に置いてください

## 出力形式

以下のJSON配列形式で出力してください：

```json
[
  {{
    "構成要素番号": "1a",
    "構成要素": "構成要素のテキスト",
    "構成要素のサポート箇所": "全文の中でこの構成要素をサポートする記載箇所",
    "構成要素の簡単説明": "この構成要素の簡単な説明",
    "構成要素の従属関係": "|",
    "構成要素の重要度": 0.8
  }},
  ...
]
```

- **構成要素番号**: クレームごとは数字の1、2、3、クレームの中の要素はa、b、c
- **構成要素**: 構成要素のテキスト
- **構成要素のサポート箇所**: 全文の中でこの構成要素をサポートする記載箇所
- **構成要素の簡単説明**: この構成要素の簡単な説明
- **構成要素の従属関係**: 前後の構成要件の従属関係を簡単な記号で表記（例："|"、"->"）
- **構成要素の重要度**: この構成要素が特徴部なのかを0~1の間の数字で評価

# 特許データ

{patent_data}

# 出力

JSON配列のみを出力してください（説明文や```json```などのマークダウンは不要です）：
"""
        return prompt

    def _parse_component_response(self, response: str) -> List[ComponentElement]:
        """Geminiレスポンスをパースして構成要素リストに変換"""
        try:
            # レスポンスからJSON部分を抽出
            json_str = response.strip()

            # マークダウンのコードブロックを除去
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]

            json_str = json_str.strip()

            # JSONパース
            data = json.loads(json_str)

            # ComponentElementオブジェクトのリストに変換
            components = []
            for item in data:
                component = ComponentElement(
                    構成要素番号=item["構成要素番号"],
                    構成要素=item["構成要素"],
                    構成要素のサポート箇所=item["構成要素のサポート箇所"],
                    構成要素の簡単説明=item["構成要素の簡単説明"],
                    構成要素の従属関係=item["構成要素の従属関係"],
                    構成要素の重要度=float(item["構成要素の重要度"])
                )
                components.append(component)

            return components

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response: {response}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse component response: {e}")
            raise


# ============================================================================
# Keyword Generator
# ============================================================================

class KeywordGenerator:
    """キーワード生成クラス"""

    def __init__(self, gemini_client: GeminiClient):
        """
        初期化

        Args:
            gemini_client: GeminiClientインスタンス
        """
        self.gemini = gemini_client

    def generate_keywords(self, component: ComponentElement) -> ComponentKeywords:
        """
        構成要素のキーワードを生成

        Args:
            component: 構成要素

        Returns:
            ComponentKeywords
        """
        prompt = self._create_keyword_generation_prompt(component)

        logger.info(f"Generating keywords for component: {component.構成要素番号}")
        response = self.gemini.generate_content(prompt, temperature=0.5)

        # JSONレスポンスをパース
        keywords = self._parse_keyword_response(component.構成要素番号, response)

        return keywords

    def _create_keyword_generation_prompt(self, component: ComponentElement) -> str:
        """キーワード生成プロンプトの作成"""

        prompt = f"""
以下の構成要素に対して、特許検索に有効なキーワードを生成してください。

# 構成要素情報

- **番号**: {component.構成要素番号}
- **構成要素**: {component.構成要素}
- **説明**: {component.構成要素の簡単説明}
- **重要度**: {component.構成要素の重要度}

# キーワード生成要求

1. **基本キーワード**: 各要素の名称（キーワード）をそのまま抽出
2. **同義語・類義語**: 同義語や類義語を洗い出す
3. **上位概念**: より広い意味の言葉
4. **下位概念**: より狭い意味の言葉
5. **機能キーワード**: 作用・機能・目的を表す言葉
6. **専門用語**: 業界用語・専門用語・古い表現

# 出力形式

以下のJSON形式で出力してください：

```json
{{
  "基本キーワード": ["キーワード1", "キーワード2"],
  "同義語類義語": ["類義語1", "類義語2"],
  "上位概念": ["上位概念1", "上位概念2"],
  "下位概念": ["下位概念1", "下位概念2"],
  "機能キーワード": ["機能1", "機能2"],
  "専門用語": ["専門用語1", "専門用語2"]
}}
```

JSON形式のみを出力してください（説明文やマークダウンは不要です）：
"""
        return prompt

    def _parse_keyword_response(self, component_id: str, response: str) -> ComponentKeywords:
        """Geminiレスポンスをパースしてキーワード情報に変換"""
        try:
            # レスポンスからJSON部分を抽出
            json_str = response.strip()

            # マークダウンのコードブロックを除去
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]

            json_str = json_str.strip()

            # JSONパース
            data = json.loads(json_str)

            keywords = ComponentKeywords(
                構成要素番号=component_id,
                基本キーワード=data.get("基本キーワード", []),
                同義語類義語=data.get("同義語類義語", []),
                上位概念=data.get("上位概念", []),
                下位概念=data.get("下位概念", []),
                機能キーワード=data.get("機能キーワード", []),
                専門用語=data.get("専門用語", [])
            )

            return keywords

        except Exception as e:
            logger.error(f"Failed to parse keyword response: {e}")
            logger.error(f"Response: {response}")
            raise


# ============================================================================
# Classification Finder
# ============================================================================

class ClassificationFinder:
    """特許分類コード特定クラス"""

    def __init__(self, opensearch_api_url: str, google_patents_api_url: str):
        """
        初期化

        Args:
            opensearch_api_url: OpenSearch特許分類検索APIのURL
            google_patents_api_url: Google Patents検索APIのURL
        """
        self.opensearch_api_url = opensearch_api_url
        self.google_patents_api_url = google_patents_api_url

    def find_classifications(self, component: ComponentElement,
                           keywords: ComponentKeywords) -> ComponentClassification:
        """
        構成要素の特許分類コードを特定

        Args:
            component: 構成要素
            keywords: キーワード情報

        Returns:
            ComponentClassification
        """
        logger.info(f"Finding classifications for component: {component.構成要素番号}")

        # OpenSearch APIで分類コード検索（FI優先、なければIPC）
        fi_ipc_codes = self._search_opensearch_classifications(component, keywords)

        # 予備検索（Google Patents → CPC → FI変換）
        preliminary_codes = self._preliminary_search(component, keywords)

        # 結果を統合
        final_codes = self._merge_classifications(fi_ipc_codes, preliminary_codes)

        classification = ComponentClassification(
            構成要素番号=component.構成要素番号,
            FI分類=fi_ipc_codes.get("FI", []),
            IPC分類=fi_ipc_codes.get("IPC", []),
            CPC分類=preliminary_codes.get("CPC", []),
            予備検索CPC=preliminary_codes.get("CPC", []),
            最終分類=final_codes
        )

        return classification

    def _search_opensearch_classifications(self, component: ComponentElement,
                                          keywords: ComponentKeywords) -> Dict[str, List[str]]:
        """OpenSearch APIで特許分類コードを検索"""
        try:
            # 検索テキストを構築
            search_text = f"{component.構成要素} {component.構成要素の簡単説明}"

            # APIリクエスト
            response = requests.post(
                f"{self.opensearch_api_url}/search",
                json={
                    "text": search_text,
                    "classification_types": ["fi", "ipc"],
                    "top_k": 10,
                    "use_semantic_search": True
                },
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # FIとIPCを分類
            fi_codes = []
            ipc_codes = []

            for result in data.get("results", []):
                code = result.get("code", "")
                classification_type = result.get("classification_type", "").upper()

                if classification_type == "FI":
                    fi_codes.append(code)
                elif classification_type == "IPC":
                    ipc_codes.append(code)

            return {
                "FI": fi_codes[:5],  # 上位5件
                "IPC": ipc_codes[:5]
            }

        except Exception as e:
            logger.error(f"OpenSearch classification search failed: {e}")
            return {"FI": [], "IPC": []}

    def _preliminary_search(self, component: ComponentElement,
                           keywords: ComponentKeywords) -> Dict[str, List[str]]:
        """予備検索（Google Patents → CPC）"""
        try:
            # キーワードを取得（上位5件）
            search_keywords = keywords.基本キーワード[:3] + keywords.機能キーワード[:2]

            if not search_keywords:
                return {"CPC": []}

            # Google Patents APIでの検索
            response = requests.post(
                f"{self.google_patents_api_url}/search",
                json={
                    "keywords": search_keywords,
                    "max_results": 20
                },
                timeout=60
            )
            response.raise_for_status()

            data = response.json()

            # CPCランキングを取得
            cpc_ranking = data.get("cpc_ranking", [])
            cpc_codes = [item["cpc_code"] for item in cpc_ranking[:10]]

            # CPCをFIに変換（OpenSearch APIを使用）
            fi_codes = self._convert_cpc_to_fi(cpc_codes)

            return {
                "CPC": cpc_codes,
                "FI": fi_codes
            }

        except Exception as e:
            logger.error(f"Preliminary search failed: {e}")
            return {"CPC": []}

    def _convert_cpc_to_fi(self, cpc_codes: List[str]) -> List[str]:
        """CPCをFIに変換"""
        try:
            # CPC→FI変換APIを呼び出し
            # （ここでは簡略化のため、OpenSearch検索APIでCPCを使ってFIを検索）
            response = requests.post(
                f"{self.opensearch_api_url}/search",
                json={
                    "cpc_codes": cpc_codes,
                    "classification_types": ["fi"],
                    "top_k": 10
                },
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            fi_codes = [result["code"] for result in data.get("results", [])]

            return fi_codes[:5]

        except Exception as e:
            logger.error(f"CPC to FI conversion failed: {e}")
            return []

    def _merge_classifications(self, opensearch_results: Dict[str, List[str]],
                              preliminary_results: Dict[str, List[str]]) -> List[str]:
        """2つの結果を統合して最終的な分類コードを決定"""

        # OpenSearchのFI結果
        fi_opensearch = set(opensearch_results.get("FI", []))

        # 予備検索のFI結果
        fi_preliminary = set(preliminary_results.get("FI", []))

        # 交わり（共通部分）を優先
        common_fi = list(fi_opensearch & fi_preliminary)

        if common_fi:
            return common_fi

        # 交わりがない場合は、両方を結合（OpenSearch優先）
        all_fi = list(fi_opensearch) + [fi for fi in fi_preliminary if fi not in fi_opensearch]

        # FIがない場合はIPCを使用
        if not all_fi:
            all_fi = opensearch_results.get("IPC", [])

        return all_fi[:5]  # 上位5件


# ============================================================================
# Export functions
# ============================================================================

def save_components_to_json(components: List[ComponentElement],
                           output_path: str):
    """構成要素をJSONファイルに保存"""
    data = [comp.to_dict() for comp in components]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Components saved to: {output_path}")


def load_components_from_json(input_path: str) -> List[ComponentElement]:
    """JSONファイルから構成要素を読み込み"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    components = [ComponentElement(**item) for item in data]
    logger.info(f"Loaded {len(components)} components from: {input_path}")

    return components
