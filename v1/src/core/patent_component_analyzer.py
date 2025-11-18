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

# Anthropic SDK for Claude via Vertex AI
try:
    from anthropic import AnthropicVertex
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    # Note: logger will be defined later, so we use logging module directly here
    import logging as _logging
    _logging.warning("Anthropic SDK not installed. Claude models will not be available.")


# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Default CPC Codes by Technical Domain (Fallback Strategy)
# ============================================================================

DEFAULT_CPC_BY_DOMAIN = {
    # 半導体・電子デバイス (Semiconductor & Electronic Devices)
    "semiconductor": ["H01L", "H10B", "H10D", "H10K", "H10N", "H01L29"],

    # メモリ・記憶装置 (Memory & Storage)
    "memory": ["G11C", "G11C11", "G11C7", "G11C8", "G11B"],

    # ディスプレイ・表示装置 (Display Devices)
    "display": ["G09G", "G09G3", "G09F"],

    # トランジスタ (Transistor Technology)
    "transistor": ["H01L29", "H10D30", "H10D86", "H10B41"],

    # 論理回路・パルス技術 (Logic Circuits & Pulse Technology)
    "circuit": ["H03K", "H03K3", "H03K19", "H03L", "G06F"],

    # 材料技術 (Material Technology)
    "material": ["C01B", "C01G", "C23C", "C30B"],

    # 通信・信号処理 (Communication & Signal Processing)
    "communication": ["H04L", "H04B", "H04N"],

    # 電源・電力供給 (Power Supply)
    "power": ["H02M", "H02J", "G05F"],
}


# ============================================================================
# AI Client Factory
# ============================================================================

def create_ai_client(config_dict: Dict[str, Any] = None):
    """
    設定に基づいてAIクライアント（GeminiまたはClaude）を作成

    Args:
        config_dict: AIモデルの設定辞書（provider, model_name, etc.）
                    Noneの場合はconfig/ai_config.yamlから自動読み込み

    Returns:
        GeminiClient または ClaudeClient のインスタンス

    Examples:
        >>> # 設定ファイルから自動読み込み（component_analyzer用）
        >>> client = create_ai_client()

        >>> # カスタム設定で作成
        >>> custom_config = {
        ...     "provider": "anthropic",
        ...     "model_name": "claude-sonnet-4-5@20250929",
        ...     "temperature": 0.3,
        ...     "max_output_tokens": 16384
        ... }
        >>> client = create_ai_client(custom_config)
    """
    # 設定を読み込み
    if config_dict is None:
        from config.config_loader import config
        vertex_ai_config = config.get_vertex_ai_config()
        component_analyzer_config = config.get_component_analyzer_config()

        provider = component_analyzer_config.get("provider", "anthropic")
        model_name = component_analyzer_config.get("model_name", "claude-sonnet-4-5@20250929")
        project_id = vertex_ai_config.get("project_id", "ttdc-in-house-dev")
        region = vertex_ai_config.get("region", "asia-southeast1")
        service_account_path = vertex_ai_config.get("service_account_path", "./cred/ttdc-in-house-dev-2a46b2cf52e6.json")
    else:
        provider = config_dict.get("provider", "anthropic")
        model_name = config_dict.get("model_name", "claude-sonnet-4-5@20250929")
        project_id = config_dict.get("project_id", "ttdc-in-house-dev")
        region = config_dict.get("region", "asia-southeast1")
        service_account_path = config_dict.get("service_account_path", "./cred/ttdc-in-house-dev-2a46b2cf52e6.json")

    # プロバイダーに応じてクライアントを作成
    if provider.lower() == "anthropic":
        logger.info(f"Creating ClaudeClient with model: {model_name}")
        return ClaudeClient(
            service_account_path=service_account_path,
            project_id=project_id,
            location=region,
            model_name=model_name
        )
    elif provider.lower() == "google":
        logger.info(f"Creating GeminiClient with model: {model_name}")
        return GeminiClient(
            service_account_path=service_account_path,
            project_id=project_id,
            location=region,
            model_name=model_name
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: 'anthropic', 'google'")


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class TokenUsage:
    """AI API呼び出しのトークン使用量"""
    prompt_tokens: int  # 入力トークン数
    completion_tokens: int  # 出力トークン数
    total_tokens: int  # 合計トークン数

    def to_dict(self) -> Dict[str, int]:
        """辞書形式に変換"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }


@dataclass
class ComponentElement:
    """構成要素（構成要件）のデータモデル"""
    構成要素番号: str  # 例: "1a", "2b"
    構成要素: str  # 構成要素のテキスト
    構成要素のサポート箇所: str  # 全文の中でサポートする記載箇所
    段落番号: List[str]  # サポート箇所の段落番号リスト (例: ["0021", "0025"])
    構成要素の簡単説明: str  # 簡単な説明
    構成要素の重要度: float  # 0.0～1.0の重要度（発明の特徴度）

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)


@dataclass
class ComponentKeywords:
    """構成要素のキーワード情報（合計15個以内）"""
    構成要素番号: str
    一次検索キーワード: List[str]  # 基本的な検索キーワード（5個程度）
    検索範囲拡大キーワード: List[str]  # 上位概念、同義語など（5個程度）
    検索範囲縮小キーワード: List[str]  # 下位概念、専門用語など（5個程度）

    def get_all_keywords(self) -> List[str]:
        """全てのキーワードを取得（最大15個）"""
        all_kw = self.一次検索キーワード + self.検索範囲拡大キーワード + self.検索範囲縮小キーワード
        return all_kw[:15]  # 15個以内に制限

    def get_primary_keywords(self) -> List[str]:
        """1次検索用キーワードを取得"""
        return self.一次検索キーワード

    def get_expanded_keywords(self) -> List[str]:
        """範囲拡大用キーワードを取得"""
        return self.一次検索キーワード + self.検索範囲拡大キーワード

    def get_narrowed_keywords(self) -> List[str]:
        """範囲縮小用キーワードを取得"""
        return self.検索範囲縮小キーワード if self.検索範囲縮小キーワード else self.一次検索キーワード


@dataclass
class ComponentClassification:
    """構成要素の特許分類コード情報（合計10個以内）"""
    構成要素番号: str
    一次特定最終CPC: List[str]  # 基本的なCPC分類（3-4個程度）
    検索範囲拡大最終CPC: List[str]  # 上位・関連CPC（3個程度）
    検索範囲縮小最終CPC: List[str]  # 下位・詳細CPC（3個程度）

    # 参考情報（内部処理用）
    IPC分類: List[str] = None

    def __post_init__(self):
        if self.IPC分類 is None:
            self.IPC分類 = []

    def get_all_cpc(self) -> List[str]:
        """全てのCPCを取得（最大10個）"""
        all_cpc = self.一次特定最終CPC + self.検索範囲拡大最終CPC + self.検索範囲縮小最終CPC
        return all_cpc[:10]  # 10個以内に制限

    def get_primary_cpc(self) -> List[str]:
        """1次特定用CPCを取得"""
        return self.一次特定最終CPC

    def get_expanded_cpc(self) -> List[str]:
        """範囲拡大用CPCを取得"""
        return self.一次特定最終CPC + self.検索範囲拡大最終CPC

    def get_narrowed_cpc(self) -> List[str]:
        """範囲縮小用CPCを取得"""
        return self.検索範囲縮小最終CPC if self.検索範囲縮小最終CPC else self.一次特定最終CPC

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "構成要素番号": self.構成要素番号,
            "一次特定最終CPC": self.一次特定最終CPC,
            "検索範囲拡大最終CPC": self.検索範囲拡大最終CPC,
            "検索範囲縮小最終CPC": self.検索範囲縮小最終CPC,
            "IPC分類": self.IPC分類
        }


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
                        max_output_tokens: int = 8192) -> Tuple[str, TokenUsage]:
        """
        コンテンツ生成

        Args:
            prompt: プロンプト
            temperature: 温度パラメータ
            max_output_tokens: 最大出力トークン数

        Returns:
            (生成されたテキスト, トークン使用量)
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

            # マルチパートレスポンスに対応
            try:
                # 単一パートレスポンスの場合
                text = response.text
            except Exception as text_error:
                # マルチパートレスポンスの場合（thinking/reasoningを含む）
                logger.info("Multi-part response detected, extracting text from all parts")

                # 全てのテキストパートを結合
                all_text = []
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            all_text.append(part.text)

                text = "\n".join(all_text)

                if not text:
                    raise ValueError(f"Could not extract text from response: {text_error}")

            # トークン使用量を抽出
            try:
                usage_metadata = response.usage_metadata
                token_usage = TokenUsage(
                    prompt_tokens=usage_metadata.prompt_token_count,
                    completion_tokens=usage_metadata.candidates_token_count,
                    total_tokens=usage_metadata.total_token_count
                )
                logger.info(f"Token usage: prompt={token_usage.prompt_tokens}, "
                           f"completion={token_usage.completion_tokens}, "
                           f"total={token_usage.total_tokens}")
            except Exception as usage_error:
                logger.warning(f"Could not extract token usage: {usage_error}")
                # トークン使用量が取得できない場合はデフォルト値
                token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            return text, token_usage

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise


class ClaudeClient:
    """Anthropic Claude API クライアント (Vertex AI経由)"""

    def __init__(self,
                 service_account_path: str,
                 project_id: str = "ttdc-in-house-dev",
                 location: str = "asia-southeast1",
                 model_name: str = "claude-sonnet-4-5@20250929"):
        """
        初期化

        Args:
            service_account_path: サービスアカウントJSONファイルのパス
            project_id: Google Cloud プロジェクトID
            location: リージョン（デフォルト: asia-southeast1）
            model_name: 使用するClaudeモデル名
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic SDK is not installed. Please install it with: pip install anthropic[vertex]")

        self.service_account_path = service_account_path
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self._configure_api()

    def _configure_api(self):
        """API設定"""
        try:
            # Set environment variable for service account
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.service_account_path

            # Initialize AnthropicVertex client
            self.client = AnthropicVertex(
                project_id=self.project_id,
                region=self.location
            )

            logger.info(f"Vertex AI Claude configured - Project: {self.project_id}, "
                       f"Location: {self.location}, Model: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to configure Vertex AI Claude API: {e}")
            raise

    def generate_content(self, prompt: str,
                        temperature: float = 0.0,
                        max_output_tokens: int = 8192) -> Tuple[str, TokenUsage]:
        """
        コンテンツ生成

        Args:
            prompt: プロンプト
            temperature: 温度パラメータ（デフォルト: 0.0 - deterministic）
            max_output_tokens: 最大出力トークン数（デフォルト: 8192、上限: 200000）

        Returns:
            (生成されたテキスト, トークン使用量)
        """
        try:
            # Claude APIでは最大200000トークンまでサポート
            max_tokens = min(max_output_tokens, 200000)

            # Claudeのメッセージ形式でリクエスト
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # レスポンスからテキストを抽出
            if response.content and len(response.content) > 0:
                # テキストコンテンツのみを結合
                text_parts = [block.text for block in response.content if hasattr(block, 'text')]
                text = "\n".join(text_parts)
            else:
                raise ValueError("Empty response from Claude API")

            # トークン使用量を抽出
            try:
                usage = response.usage
                token_usage = TokenUsage(
                    prompt_tokens=usage.input_tokens,
                    completion_tokens=usage.output_tokens,
                    total_tokens=usage.input_tokens + usage.output_tokens
                )
                logger.info(f"Token usage: prompt={token_usage.prompt_tokens}, "
                           f"completion={token_usage.completion_tokens}, "
                           f"total={token_usage.total_tokens}")
            except Exception as usage_error:
                logger.warning(f"Could not extract token usage: {usage_error}")
                # トークン使用量が取得できない場合はデフォルト値
                token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            return text, token_usage

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

    def analyze_patent_components(self, patent_data: str) -> Tuple[List[ComponentElement], TokenUsage]:
        """
        特許データを構成要件に分割

        Args:
            patent_data: PDF/XML形式の特許データ（テキスト化されたもの）

        Returns:
            (構成要素のリスト, トークン使用量)
        """
        prompt = self._create_component_analysis_prompt(patent_data)

        logger.info("Analyzing patent components with Gemini...")
        response, token_usage = self.gemini.generate_content(prompt, temperature=0.3, max_output_tokens=16384)

        # JSONレスポンスをパース
        components = self._parse_component_response(response)

        logger.info(f"Extracted {len(components)} components")
        logger.info(f"Token usage for component analysis: {token_usage.to_dict()}")
        return components, token_usage

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
    "構成要素のサポート箇所": "【請求項１】、【００２１】、【図１】",
    "段落番号": ["0001", "0021"],
    "構成要素の簡単説明": "この構成要素の簡単な説明",
    "構成要素の重要度": 0.8
  }},
  {{
    "構成要素番号": "1b",
    "構成要素": "構成要素のテキスト",
    "構成要素のサポート箇所": "【請求項１】、【００２５】",
    "段落番号": ["0001", "0025"],
    "構成要素の簡単説明": "この構成要素の簡単な説明",
    "構成要素の重要度": 0.9
  }},
  {{
    "構成要素番号": "1c",
    "構成要素": "構成要素のテキスト",
    "構成要素のサポート箇所": "【請求項１】、【００２７】",
    "段落番号": ["0001", "0027"],
    "構成要素の簡単説明": "この構成要素の簡単な説明",
    "構成要素の重要度": 0.7
  }}
]
```

### フィールドの説明

- **構成要素番号**: クレームごとは数字の1、2、3、クレームの中の要素はa、b、c
- **構成要素**: 構成要素のテキスト
- **構成要素のサポート箇所**: 全文の中でこの構成要素をサポートする記載箇所（例：【請求項１】、【００２１】、【図１】）
- **段落番号**: サポート箇所から抽出した段落番号のリスト（例：["0001", "0021", "0025"]）
  - 【００２１】→ "0021"、【請求項１】→ "0001" のように数字のみを抽出
  - 【図１】などの図は含めない
- **構成要素の簡単説明**: この構成要素の簡単な説明
- **構成要素の重要度**: この構成要素が発明の特徴部なのかを0~1の間の数字で評価
  - 1.0に近い: 発明の核心的な特徴
  - 0.5前後: 重要だが従来技術にもある要素
  - 0に近い: 一般的な周辺要素

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
                    構成要素番号=item.get("構成要素番号", f"unknown_{len(components)}"),  # デフォルトは連番
                    構成要素=item.get("構成要素", ""),  # デフォルトは空文字列
                    構成要素のサポート箇所=item.get("構成要素のサポート箇所", ""),  # デフォルトは空文字列
                    段落番号=item.get("段落番号", []),  # デフォルトは空リスト
                    構成要素の簡単説明=item.get("構成要素の簡単説明", ""),  # デフォルトは空文字列
                    構成要素の重要度=float(item.get("構成要素の重要度", 0.5))  # デフォルトは0.5
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

    def generate_keywords(self, component: ComponentElement) -> Tuple[ComponentKeywords, TokenUsage]:
        """
        構成要素のキーワードを生成

        Args:
            component: 構成要素

        Returns:
            (ComponentKeywords, トークン使用量)
        """
        prompt = self._create_keyword_generation_prompt(component)

        logger.info(f"Generating keywords for component: {component.構成要素番号}")
        response, token_usage = self.gemini.generate_content(prompt, temperature=0.5, max_output_tokens=4096)

        # JSONレスポンスをパース
        keywords = self._parse_keyword_response(component.構成要素番号, response)

        logger.info(f"Token usage for keyword generation (component {component.構成要素番号}): {token_usage.to_dict()}")
        return keywords, token_usage

    def _create_keyword_generation_prompt(self, component: ComponentElement) -> str:
        """キーワード生成プロンプトの作成（特許検索理論に基づく改善版）"""

        prompt = f"""
以下の構成要素に対して、**先行技術調査に最適化されたキーワード**を生成してください。

# 構成要素情報

- **番号**: {component.構成要素番号}
- **構成要素**: {component.構成要素}
- **説明**: {component.構成要素の簡単説明}
- **重要度**: {component.構成要素の重要度}

# 特許検索におけるキーワード戦略

特許検索では、発明者とは異なる表現で同じ技術が記載されていることが多いため、以下の観点でキーワードを選定してください：

1. **構造的キーワード vs 機能的キーワード**
   - 構造的：物理的な構成要素（例：「薄膜トランジスタ」「メモリセル」）
   - 機能的：技術的機能・効果（例：「電荷保持」「データ記憶」）

2. **日英バイリンガル対応**
   - 日本語キーワードだけでなく、英語の国際標準用語も含める
   - 例：「酸化物半導体」→ "oxide semiconductor"

3. **技術分野の専門用語**
   - 半導体分野：FET, TFT, IGZO, MOSFET, channel, gate, drain, source
   - メモリ分野：DRAM, SRAM, flash, volatile, non-volatile, retention
   - ディスプレイ分野：pixel, LCD, OLED, active matrix, display driver

4. **上位概念・下位概念の階層**
   - 上位概念（範囲拡大）：より一般的な技術カテゴリ
   - 下位概念（範囲縮小）：具体的な実装方式や材料名

# キーワード生成要求

**合計15個以内**のキーワードを以下の3つのカテゴリに分類して生成してください：

## 1. 一次検索キーワード（5個程度）
- 構成要素の核となる基本的なキーワード
- 構造的キーワード + 機能的キーワードのバランス
- 日本語と英語の重要用語を含む
- 例：
  - 半導体技術：「トランジスタ」「transistor」「チャネル層」「channel」「オフ電流」
  - メモリ技術：「記憶素子」「memory cell」「データ保持」「retention」「読み出し」
  - ディスプレイ技術：「画素」「pixel」「表示素子」「display element」「駆動回路」

## 2. 検索範囲拡大キーワード（5個程度）
- 上位概念、同義語、類義語、関連技術
- より広い技術カテゴリ
- 国際標準用語、業界標準用語
- 例：
  - 半導体技術：「半導体素子」「電子デバイス」「semiconductor device」「electronic element」
  - メモリ技術：「記憶装置」「storage」「不揮発性」「non-volatile」「データ格納」
  - ディスプレイ技術：「表示装置」「display」「映像表示」「画像表示」「アクティブマトリクス」

## 3. 検索範囲縮小キーワード（5個程度）
- 下位概念、専門用語、具体的な材料名・方式名
- 技術的に詳細な実装方式
- 特定の材料、構造、プロセス
- 例：
  - 半導体技術：「MOSFET」「IGZO」「酸化物TFT」「oxide TFT」「InGaZnO」
  - メモリ技術：「DRAM」「SRAM」「フローティングゲート」「floating gate」「キャパシタ」
  - ディスプレイ技術：「有機EL」「OLED」「液晶」「LCD」「TFT-LCD」

# 出力形式

以下のJSON形式で出力してください：

```json
{{
  "一次検索キーワード": ["キーワード1", "keyword1", "キーワード2", "keyword2", "キーワード3"],
  "検索範囲拡大キーワード": ["上位概念1", "broader term1", "関連技術1", "related tech1", "同義語1"],
  "検索範囲縮小キーワード": ["具体的材料1", "specific method1", "専門用語1", "詳細技術1", "実装方式1"]
}}
```

# 重要な制約

- **合計15個以内**を厳守してください（各カテゴリ5個程度）
- 日本語と英語の用語をバランスよく含めてください
- 構造的キーワードと機能的キーワードの両方を含めてください
- 技術分野に応じた専門用語を優先してください
- 国際特許検索も考慮して、英語の標準用語を含めてください

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
                一次検索キーワード=data.get("一次検索キーワード", []),
                検索範囲拡大キーワード=data.get("検索範囲拡大キーワード", []),
                検索範囲縮小キーワード=data.get("検索範囲縮小キーワード", [])
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
        self.global_preliminary_fi = None  # 全体で一度だけ実行する予備検索のFI結果をキャッシュ

    def perform_global_preliminary_search(self,
                                         components: List[ComponentElement],
                                         keywords_list: List[ComponentKeywords]) -> Dict[str, List[str]]:
        """
        全体で一度だけ予備検索を実行（全構成要素のキーワードを使用）

        仕様：
        - 全ての構成要素の生成されたキーワード（特に発明の核心を表すもの）を使用
        - Google Patents検索APIで検索
        - 検索結果からCPCランキングを取得
        - CPCをOpenSearch APIでFIに変換して出力

        Args:
            components: 全構成要素リスト
            keywords_list: 全キーワードリスト

        Returns:
            FIコードの辞書 {"FI": [...]}
        """
        logger.info("Performing global preliminary search with all component keywords...")

        # 全ての構成要素のキーワード（特に発明の核心を表すもの）を収集
        # 重要度でソート（降順）して、最も重要な構成要素のキーワードを優先
        sorted_components = sorted(
            zip(components, keywords_list),
            key=lambda x: x[0].構成要素の重要度,
            reverse=True
        )

        all_keywords = []
        for component, keywords in sorted_components:
            # 重要度が高い構成要素のキーワードを優先
            if component.構成要素の重要度 >= 0.6:
                primary_kw = keywords.get_primary_keywords()
                # 一次検索キーワードから最大2個を追加（全体で5個に制限するため）
                for kw in primary_kw[:2]:
                    if kw not in all_keywords:
                        all_keywords.append(kw)
                    if len(all_keywords) >= 5:  # 一次検索キーワードの上限: 5個
                        break

            if len(all_keywords) >= 5:
                break

        logger.info(f"Collected {len(all_keywords)} keywords from high-importance components")
        logger.info(f"Keywords: {all_keywords}")

        if not all_keywords:
            logger.warning("No keywords collected for global preliminary search")
            return {"FI": []}

        try:
            # Google Patents APIで検索（キーワード数を5個に制限）
            response = requests.post(
                f"{self.google_patents_api_url}/search",
                json={
                    "keywords": all_keywords[:5],  # 一次検索キーワードの上限: 5個
                    "max_results": 50
                },
                timeout=120  # CPC抽出のため120秒に延長
            )
            response.raise_for_status()

            data = response.json()

            # CPCランキングを取得（仕様書: 上位3個以内）
            cpc_ranking = data.get("cpc_ranking", [])
            cpc_codes = [item["cpc_code"] for item in cpc_ranking[:3]]

            logger.info(f"Global preliminary search CPC codes: {cpc_codes}")

            # CPCが空の場合、OpenSearchのみに依存
            if not cpc_codes:
                logger.warning("CPC ranking is empty. Relying solely on OpenSearch results instead of fallback codes.")
                self.global_preliminary_fi = {"CPC": []}
                return self.global_preliminary_fi

            # 結果をキャッシュ（CPCのみを保持）
            self.global_preliminary_fi = {"CPC": cpc_codes}

            return self.global_preliminary_fi

        except Exception as e:
            logger.error(f"Global preliminary search failed: {e}")
            self.global_preliminary_fi = {"CPC": []}
            return self.global_preliminary_fi

    def find_classifications(self, component: ComponentElement,
                           keywords: ComponentKeywords,
                           use_global_preliminary: bool = True) -> Tuple[ComponentClassification, Dict[str, Any]]:
        """
        構成要素の特許分類コードを特定

        Args:
            component: 構成要素
            keywords: キーワード情報
            use_global_preliminary: 全体予備検索結果を使用するか（デフォルト: True）

        Returns:
            Tuple[ComponentClassification, classification_history]:
                - ComponentClassification: 分類コード情報
                - classification_history: 分類特定プロセスの詳細履歴
        """
        logger.info(f"Finding classifications for component: {component.構成要素番号}")

        # OpenSearch APIで分類コード検索（FI優先、なければIPC）
        fi_ipc_codes = self._search_opensearch_classifications(component, keywords)

        # 予備検索結果を取得
        if use_global_preliminary and self.global_preliminary_fi is not None:
            # 全体で一度実行した予備検索結果を使用（旧方式）
            logger.info("Using cached global preliminary search results")
            preliminary_codes = self.global_preliminary_fi
        else:
            # 個別に予備検索を実行（仕様書通りの実装）
            logger.info(f"Performing individual preliminary search for component {component.構成要素番号}")
            preliminary_codes = self._preliminary_search(component, keywords)

        # 結果を統合してカテゴリ分け (交差コードも取得)
        categorized_cpc, intersection_cpc = self._categorize_cpc_codes_with_intersection(fi_ipc_codes, preliminary_codes)

        classification = ComponentClassification(
            構成要素番号=component.構成要素番号,
            一次特定最終CPC=categorized_cpc["primary"],
            検索範囲拡大最終CPC=categorized_cpc["expanded"],
            検索範囲縮小最終CPC=categorized_cpc["narrowed"],
            IPC分類=fi_ipc_codes.get("IPC", [])
        )

        # 分類特定プロセスの詳細履歴を作成
        classification_history = {
            "component_id": component.構成要素番号,
            "gemini_cpc_codes": preliminary_codes.get("CPC", []),
            "opensearch_cpc_codes": fi_ipc_codes.get("CPC", []),
            "preliminary_cpc_codes": preliminary_codes.get("CPC", []),
            "intersection_cpc_codes": intersection_cpc,
            "final_combined_cpc_codes": categorized_cpc["primary"] + categorized_cpc["expanded"] + categorized_cpc["narrowed"]
        }

        return classification, classification_history

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

    def _infer_technical_domain(self, component: ComponentElement,
                                keywords: ComponentKeywords) -> str:
        """
        キーワードから技術分野を推定（ルールベース）

        Args:
            component: 構成要素
            keywords: キーワード情報

        Returns:
            技術分野名（DEFAULT_CPC_BY_DOMAINのキー）
        """
        # テキストを結合
        text = f"{component.構成要素} {component.構成要素の簡単説明} "
        text += " ".join(keywords.一次検索キーワード)
        text = text.lower()

        # ルールベース分類（特許検索の実務経験に基づく）
        if any(kw in text for kw in ["メモリ", "記憶", "memory", "storage", "記憶装置", "ram", "rom", "dram", "sram"]):
            return "memory"
        elif any(kw in text for kw in ["半導体", "トランジスタ", "semiconductor", "transistor", "fet", "mos", "cmos"]):
            return "semiconductor"
        elif any(kw in text for kw in ["ディスプレイ", "表示", "display", "lcd", "oled", "画面", "液晶"]):
            return "display"
        elif any(kw in text for kw in ["回路", "論理", "circuit", "logic", "パルス", "pulse", "クロック", "clock"]):
            return "circuit"
        elif any(kw in text for kw in ["酸化物", "oxide", "材料", "material", "成膜", "薄膜", "film"]):
            return "material"
        elif any(kw in text for kw in ["通信", "信号", "communication", "signal", "伝送", "transmission"]):
            return "communication"
        elif any(kw in text for kw in ["電源", "電力", "power", "supply", "voltage"]):
            return "power"
        else:
            # デフォルトは半導体分野
            return "semiconductor"

    def _get_fallback_cpc_codes(self, component: ComponentElement,
                                keywords: ComponentKeywords) -> List[str]:
        """
        フォールバックCPCコードを取得（予備検索失敗時用）

        Args:
            component: 構成要素
            keywords: キーワード情報

        Returns:
            フォールバックCPCコードのリスト
        """
        # 技術分野を推定
        domain = self._infer_technical_domain(component, keywords)

        # デフォルトCPCコードを取得
        fallback_cpc = DEFAULT_CPC_BY_DOMAIN.get(domain, [])

        logger.info(f"Using fallback CPC codes for domain '{domain}': {fallback_cpc[:5]}")

        return fallback_cpc

    def _preliminary_search(self, component: ComponentElement,
                           keywords: ComponentKeywords) -> Dict[str, List[str]]:
        """予備検索（Google Patents → CPC）with retry logic and fallback strategy"""
        import time

        # キーワードを取得（一次検索キーワード）
        search_keywords = keywords.get_primary_keywords()

        if not search_keywords:
            logger.warning("No primary keywords available, using fallback CPC codes")
            fallback_cpc = self._get_fallback_cpc_codes(component, keywords)
            return {"CPC": fallback_cpc[:10]}  # 上位10個に制限

        # リトライ設定（強化版：5回リトライ、指数バックオフ）
        max_retries = 5
        base_retry_delay = 5  # 秒

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # 指数バックオフ: 5秒、10秒、20秒、40秒
                    retry_delay = base_retry_delay * (2 ** (attempt - 1))
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} for preliminary search (waiting {retry_delay}s)")
                    time.sleep(retry_delay)

                # Google Patents APIでの検索
                # 予備検索ではCPCランキングのみ取得（個別特許ページ訪問をスキップ）
                response = requests.post(
                    f"{self.google_patents_api_url}/search",
                    json={
                        "keywords": search_keywords,
                        "max_results": 50,  # 20→50に増加（より多くの特許から分析）
                        "cpc_ranking_only": True,  # CPCランキングのみ取得
                        "max_ranking_items": 100    # 50→100に増加（より多様なCPCコードを取得）
                    },
                    timeout=120  # Selenium処理が遅いためタイムアウトを延長
                )
                response.raise_for_status()

                data = response.json()

                # CPCランキングを取得（上位10個に拡大 - リコール改善）
                cpc_ranking = data.get("cpc_ranking", [])
                cpc_codes = [item["cpc_code"] for item in cpc_ranking[:10]]

                # CPCコードが取得できなかった場合はフォールバックを使用
                if not cpc_codes:
                    logger.warning("No CPC codes retrieved from preliminary search, using fallback")
                    fallback_cpc = self._get_fallback_cpc_codes(component, keywords)
                    return {"CPC": fallback_cpc[:10]}

                logger.info(f"Preliminary search succeeded on attempt {attempt + 1}")
                return {
                    "CPC": cpc_codes
                }

            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Preliminary search attempt {attempt + 1} timed out after 120s: {e}, retrying...")
                else:
                    logger.error(f"Preliminary search timed out after {max_retries} attempts (total wait: 120s per attempt)")
                    logger.info("Using fallback CPC codes based on technical domain inference")
                    fallback_cpc = self._get_fallback_cpc_codes(component, keywords)
                    return {"CPC": fallback_cpc[:10]}
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Preliminary search attempt {attempt + 1} network error: {type(e).__name__}: {e}, retrying...")
                else:
                    logger.error(f"Preliminary search network error after {max_retries} attempts: {type(e).__name__}: {e}")
                    logger.info("Using fallback CPC codes based on technical domain inference")
                    fallback_cpc = self._get_fallback_cpc_codes(component, keywords)
                    return {"CPC": fallback_cpc[:10]}
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Preliminary search attempt {attempt + 1} unexpected error: {type(e).__name__}: {e}, retrying...")
                else:
                    logger.error(f"Preliminary search unexpected error after {max_retries} attempts: {type(e).__name__}: {e}")
                    logger.info("Using fallback CPC codes based on technical domain inference")
                    fallback_cpc = self._get_fallback_cpc_codes(component, keywords)
                    return {"CPC": fallback_cpc[:10]}

    def _categorize_cpc_codes(self, opensearch_results: Dict[str, List[str]],
                            preliminary_results: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        CPC分類コードを3つのカテゴリに分類（合計10個以内）

        改善版：予備検索とOpenSearchの交差（両方に現れるコード）を優先し、
        精度の高い分類コードを選択する

        Returns:
            {
                "primary": [一次特定最終CPC（3-4個）],
                "expanded": [検索範囲拡大最終CPC（3個）],
                "narrowed": [検索範囲縮小最終CPC（3個）]
            }
        """
        # OpenSearchのCPC結果
        cpc_opensearch = opensearch_results.get("CPC", [])

        # 予備検索のCPC結果
        cpc_preliminary = preliminary_results.get("CPC", [])

        logger.info(f"OpenSearch CPC codes: {cpc_opensearch[:5]}")
        logger.info(f"Preliminary search CPC codes: {cpc_preliminary[:5]}")

        # ステップ1: 両方に現れるCPCコード（交差）を最優先
        cpc_opensearch_set = set(cpc_opensearch)
        cpc_preliminary_set = set(cpc_preliminary)
        intersection_cpc = list(cpc_opensearch_set & cpc_preliminary_set)

        logger.info(f"Intersection CPC codes: {intersection_cpc}")

        # ステップ2: 交差がない場合、OpenSearch結果を優先（特許本文との関連性が高い）
        # その後、予備検索結果を追加
        all_cpc = []
        seen = set()

        # 交差結果を最優先で追加
        for cpc in intersection_cpc:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # OpenSearch結果を追加（交差に含まれないもの）
        for cpc in cpc_opensearch:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # 予備検索結果を追加（交差とOpenSearchに含まれないもの）
        for cpc in cpc_preliminary:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # CPCがない場合はIPCを使用
        if not all_cpc:
            logger.warning("No CPC codes found, falling back to IPC")
            ipc_codes = opensearch_results.get("IPC", [])
            for ipc in ipc_codes:
                if ipc not in seen:
                    all_cpc.append(ipc)
                    seen.add(ipc)

        logger.info(f"Final combined CPC codes (top 10): {all_cpc[:10]}")

        # カテゴリ分け（合計10個以内）
        # 交差結果が存在する場合、それを一次特定に優先的に含める
        primary_cpc = all_cpc[:4]  # 一次特定：最上位3-4件
        expanded_cpc = all_cpc[4:7] if len(all_cpc) > 4 else []  # 検索範囲拡大：次の3件
        narrowed_cpc = all_cpc[7:10] if len(all_cpc) > 7 else []  # 検索範囲縮小：次の3件

        return {
            "primary": primary_cpc,
            "expanded": expanded_cpc,
            "narrowed": narrowed_cpc
        }

    def _categorize_cpc_codes_with_intersection(self, opensearch_results: Dict[str, List[str]],
                                              preliminary_results: Dict[str, List[str]]) -> Tuple[Dict[str, List[str]], List[str]]:
        """
        CPC分類コードを3つのカテゴリに分類し、交差コードも返す（合計10個以内）

        改善版：予備検索とOpenSearchの交差（両方に現れるコード）を優先し、
        精度の高い分類コードを選択する

        Returns:
            Tuple[Dict[str, List[str]], List[str]]:
                - categorized_dict: {
                    "primary": [一次特定最終CPC（3-4個）],
                    "expanded": [検索範囲拡大最終CPC（3個）],
                    "narrowed": [検索範囲縮小最終CPC（3個）]
                  }
                - intersection_codes: 両方に現れたCPCコードのリスト
        """
        # OpenSearchのCPC結果
        cpc_opensearch = opensearch_results.get("CPC", [])

        # 予備検索のCPC結果
        cpc_preliminary = preliminary_results.get("CPC", [])

        logger.info(f"OpenSearch CPC codes: {cpc_opensearch[:5]}")
        logger.info(f"Preliminary search CPC codes: {cpc_preliminary[:5]}")

        # ステップ1: 両方に現れるCPCコード（交差）を最優先
        cpc_opensearch_set = set(cpc_opensearch)
        cpc_preliminary_set = set(cpc_preliminary)
        intersection_cpc = list(cpc_opensearch_set & cpc_preliminary_set)

        logger.info(f"Intersection CPC codes: {intersection_cpc}")

        # ステップ2: 交差がない場合、OpenSearch結果を優先（特許本文との関連性が高い）
        # その後、予備検索結果を追加
        all_cpc = []
        seen = set()

        # 交差結果を最優先で追加
        for cpc in intersection_cpc:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # OpenSearch結果を追加（交差に含まれないもの）
        for cpc in cpc_opensearch:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # 予備検索結果を追加（交差とOpenSearchに含まれないもの）
        for cpc in cpc_preliminary:
            if cpc not in seen:
                all_cpc.append(cpc)
                seen.add(cpc)

        # CPCがない場合はIPCを使用
        if not all_cpc:
            logger.warning("No CPC codes found, falling back to IPC")
            ipc_codes = opensearch_results.get("IPC", [])
            for ipc in ipc_codes:
                if ipc not in seen:
                    all_cpc.append(ipc)
                    seen.add(ipc)

        logger.info(f"Final combined CPC codes (top 10): {all_cpc[:10]}")

        # カテゴリ分け（合計10個以内）
        # 交差結果が存在する場合、それを一次特定に優先的に含める
        primary_cpc = all_cpc[:4]  # 一次特定：最上位3-4件
        expanded_cpc = all_cpc[4:7] if len(all_cpc) > 4 else []  # 検索範囲拡大：次の3件
        narrowed_cpc = all_cpc[7:10] if len(all_cpc) > 7 else []  # 検索範囲縮小：次の3件

        categorized_dict = {
            "primary": primary_cpc,
            "expanded": expanded_cpc,
            "narrowed": narrowed_cpc
        }

        return categorized_dict, intersection_cpc


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
