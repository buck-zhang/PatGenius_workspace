#!/usr/bin/env python3
"""
進歩性判断エンジン - Vertex AI Gemini 2.0/3.0版

本願特許の構成要素と検索結果特許との構成対比を実行し、
X文献（単独文献）とY文献（組み合わせ文献）を摘出する。

2025年最新のVertex AI SDK・Gemini APIベストプラクティスに準拠
"""

import os
import json
import time
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from pathlib import Path
from itertools import combinations
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import requests


class NoveltyAssessmentEngine:
    """
    進歩性判断エンジン

    機能:
    1. 検索結果特許との個別構成対比
    2. X文献の摘出（全構成要素を単独で備える特許）
    3. Y文献の摘出（3件以内の組み合わせで全構成要素を備える特許群）
       - 優先度1: 独立請求項の構成要素
       - 優先度2: 主要な構成要素（重要度>=0.8）
       - 優先度3: 全ての構成要素
    """

    def __init__(
        self,
        project_id: str,
        location: str = "global",
        model_name: str = "gemini-3-pro-preview",
        patentfield_key_path: str = None,
        output_dir: str = "./novelty_assessment_results",
        max_workers: int = 5
    ):
        """
        初期化

        Args:
            project_id: Google Cloud プロジェクトID
            location: Vertex AIのロケーション（Gemini 3 Proは'global'を使用）
            model_name: 使用するGeminiモデル名
            patentfield_key_path: PatentField APIキーのパス
            output_dir: 結果出力ディレクトリ
            max_workers: 並列処理数
        """
        # Vertex AI初期化
        vertexai.init(project=project_id, location=location)

        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers

        # Geminiモデル設定
        self.model = self._setup_gemini_model()

        # PatentField API設定
        if patentfield_key_path and Path(patentfield_key_path).exists():
            with open(patentfield_key_path, 'r') as f:
                pf_config = json.load(f)
                self.pf_api_key = pf_config.get('api_key')
                self.pf_base_url = pf_config.get('base_url', 'https://api.patentfield.com')
        else:
            self.pf_api_key = None
            print("警告: PatentField APIキーが設定されていません")

        # 統計情報
        self.stats = {
            'total_comparisons': 0,
            'successful_comparisons': 0,
            'failed_comparisons': 0,
            'api_errors': 0,
            'total_time_seconds': 0
        }

    def _setup_gemini_model(self) -> GenerativeModel:
        """Gemini 3.0 Pro Previewモデルのセットアップ"""
        # 2025年ベストプラクティス（特許判断用）:
        # - Gemini 3 Pro: 最新の推論特化モデル（1M context window）
        # - temperature=0.0: 決定論的な判断、ハルシネーション防止
        # - 技術的・事実ベースのタスクには0.0-0.4推奨
        # - max_output_tokens: 最大64K（Gemini 3の上限）

        generation_config = GenerationConfig(
            temperature=0.0,  # 決定論的判断（特許対比は事実ベース）
            max_output_tokens=8192,  # 特許対比に十分なサイズ
            response_mime_type="application/json"
        )

        model = GenerativeModel(
            model_name=self.model_name,
            generation_config=generation_config
        )

        return model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    def _fetch_patent_full_data(self, patent_id: str) -> Dict:
        """
        PatentField APIから特許全文データを取得（検索API使用）

        Args:
            patent_id: 特許番号（例: JP2023020908、JP2023020908A）

        Returns:
            全文データ辞書
        """
        if not self.pf_api_key:
            # APIキーがない場合はダミーデータ
            return {
                'patent_id': patent_id,
                'abstract': 'データ取得失敗',
                'claims': 'データ取得失敗',
                'description': 'データ取得失敗',
                'error': 'No API key'
            }

        try:
            headers = {
                'Authorization': f'Bearer {self.pf_api_key}',
                'Content-Type': 'application/json'
            }

            # PatentField検索APIを使用（特許番号で検索）
            # 末尾のAを除去して検索（JP2023020908AとJP2023020908の両方に対応）
            search_patent_id = patent_id.rstrip('A')

            payload = {
                "search_type": "expert",
                "q": f"PN:{search_patent_id}",  # 特許番号検索
                "columns": [
                    "app_doc_id",
                    "pub_id",
                    "title",
                    "abstract",
                    "app_claims",
                    "grant_claims",
                    "description",
                    "cross_applicants",
                    "app_date"
                ],
                "limit": 1
            }

            # 検索エンドポイント（base_urlに/patents/searchを追加）
            search_endpoint = f"{self.pf_base_url}/patents/search"

            response = requests.post(
                search_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            records = data.get('records', [])

            if not records:
                # 見つからない場合
                return {
                    'patent_id': patent_id,
                    'abstract': '',
                    'claims': '',
                    'description': '',
                    'error': 'Patent not found'
                }

            record = records[0]

            return {
                'patent_id': patent_id,
                'abstract': record.get('abstract', ''),
                'claims': record.get('app_claims', record.get('grant_claims', '')),
                'description': record.get('description', '')[:10000],  # 最初の10000文字（API制限対応）
                'applicant': ', '.join(record.get('cross_applicants', [])) if record.get('cross_applicants') else '',
                'filing_date': record.get('app_date', '')
            }

        except Exception as e:
            print(f"    警告: {patent_id}のデータ取得失敗 - {str(e)}")
            return {
                'patent_id': patent_id,
                'abstract': '',
                'claims': '',
                'description': '',
                'error': str(e)
            }

    def _build_composition_comparison_prompt(
        self,
        base_elements: List[Dict],
        target_patent_data: Dict
    ) -> str:
        """
        構成対比判断プロンプトの生成

        Args:
            base_elements: 本願特許の構成要素リスト
            target_patent_data: 対象特許の全文データ

        Returns:
            プロンプト文字列
        """
        # 構成要素を整形
        elements_text = ""
        for elem in base_elements:
            elements_text += f"【{elem['構成要素番号']}】{elem['構成要素']}\n"
            elements_text += f"  説明: {elem.get('構成要素の簡単説明', '')}\n"
            elements_text += f"  重要度: {elem.get('構成要素の重要度', 0.5)}\n"
            elements_text += f"  独立請求項: {elem.get('is_independent', False)}\n\n"

        prompt = f"""
# タスク: 特許の構成対比判断

あなたは特許実務の専門家です。本願特許の各構成要素が、対象特許（先行技術）に開示されているかを判断してください。

## 判断基準（特許庁審査基準に基づく）

### 1. 「開示されている」の定義
以下のいずれかに該当する場合、構成要素は「開示されている」と判断します：

- **明示的開示**: 請求項または明細書に同一または実質的に同一の構成が記載
- **図面による開示**: 図面に当該構成要素が視覚的に示されている
- **当業者自明の開示**: 明細書の記載から当業者が容易に理解できる構成

### 2. 実質的同一性の判断

以下の観点で実質的に同一かを評価してください：

- **機能・作用**: 同じ機能・作用を果たすか
- **構造・組成**: 化学構造・物理構造が同等か
- **技術的意義**: 技術課題の解決手段として同等か

### 3. 化学構造・材料の具体的限定に関する判断基準（重要）

本願特許が**化学構造や材料の具体的な限定**（例：「エチルオキシドスペーサーを有する」「特定の置換基を持つ」など）を含む場合：

#### ケース1: 対象特許に同じ具体的限定が明示されている
→ **開示あり (TRUE)** と判断

#### ケース2: 対象特許に異なる具体的限定が明示されている
例：本願「エチルオキシドスペーサー」vs 対象特許「メチレンスペーサー」
→ **開示なし (FALSE)** と判断
理由：構造上の明確な差異が存在する

#### ケース3: 対象特許に上位概念のみが開示され、具体的限定の記載がない
例：本願「エチルオキシドスペーサーを有するPFPE」vs 対象特許「PFPE化合物」のみ
→ **開示なし (FALSE)** と判断
理由：上位概念の開示は下位概念の具体的限定を開示したことにはならない

#### ケース4: 対象特許に複数の選択肢が例示され、本願の限定が含まれる
例：対象特許「メチレン、エチレン、またはプロピレンスペーサー」と明示
→ **開示あり (TRUE)** と判断

### 4. 一貫性の確保（必須）

- **すべての対象特許に対して同じ判断基準を適用**してください
- 同じレベルの開示に対しては、必ず同じ判断（TRUE/FALSE）を下してください
- 特定の特許だけに寛容な判断や厳格な判断を適用しないでください

### 5. 「保守的判断」の適用条件

以下の場合に限り、疑わしい場合は「開示あり」と判断してください：

✓ **適用する場合**:
- 対象特許の記載が不明瞭で、開示の有無が判断困難な場合
- 技術常識から見て、当業者が容易に理解できる範囲の記載の場合
- 機能的に同等で、表現のみが異なる場合

❌ **適用しない場合**:
- 化学構造・材料の具体的限定が異なる場合（上記ケース2）
- 上位概念のみで下位概念の限定がない場合（上記ケース3）
- 対象特許に明確に異なる構成が記載されている場合

## 本願特許の構成要素

{elements_text}

## 対象特許（先行技術）

**特許番号**: {target_patent_data.get('patent_id', 'Unknown')}
**出願人**: {target_patent_data.get('applicant', 'Unknown')}
**出願日**: {target_patent_data.get('filing_date', 'Unknown')}

### 要約
{target_patent_data.get('abstract', '（データなし）')[:3000]}

### 請求の範囲
{target_patent_data.get('claims', '（データなし）')[:10000]}

### 詳細な説明（主要部分）
{target_patent_data.get('description', '（データなし）')[:30000]}

## 出力形式（必須）

以下のJSON形式で、各構成要素について判断結果を出力してください：

```json
{{
  "target_patent_id": "{target_patent_data.get('patent_id', 'Unknown')}",
  "comparison_date": "{datetime.now().strftime('%Y-%m-%d')}",
  "element_comparisons": [
    {{
      "element_id": "構成要素番号",
      "is_disclosed": true または false,
      "evidence": {{
        "locations": ["請求項1", "段落0025"],
        "quoted_text": "対象特許からの引用（該当箇所）",
        "reasoning": "開示あり/なしと判断した理由"
      }}
    }}
  ],
  "overall_assessment": {{
    "total_elements": 構成要素総数,
    "disclosed_elements": 開示ありの要素数,
    "disclosure_rate": 開示率(0.0-1.0),
    "novelty_risk": "high / medium / low"
  }}
}}
```

## 重要な指示

1. **各構成要素を個別に判断**: 一括判断ではなく、要素ごとに詳細に分析
2. **証拠の明示**: 判断根拠を対象特許からの引用で示す
3. **JSON形式厳守**: 必ず有効なJSON形式で出力
4. **簡潔なプロンプト**: Gemini 3は簡潔な指示に最適化されています

それでは、上記の基準に従って構成対比を実施してください。
"""
        return prompt

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    def _compare_with_gemini(
        self,
        base_elements: List[Dict],
        target_patent_data: Dict
    ) -> Dict:
        """
        Geminiで構成対比を実行

        Args:
            base_elements: 本願特許の構成要素リスト
            target_patent_data: 対象特許の全文データ

        Returns:
            構成対比結果JSON
        """
        # プロンプト生成
        prompt = self._build_composition_comparison_prompt(
            base_elements,
            target_patent_data
        )

        try:
            # Gemini API呼び出し
            response = self.model.generate_content(prompt)

            # JSON抽出
            result_text = response.text

            # JSONパース
            result = json.loads(result_text)

            return result

        except json.JSONDecodeError as e:
            print(f"    ❌ JSON解析エラー: {str(e)}")
            # フォールバック: 全てFalseで返す
            return self._create_fallback_result(
                target_patent_data['patent_id'],
                base_elements,
                error=f"JSON parsing failed: {str(e)}"
            )

        except Exception as e:
            print(f"    ❌ Gemini APIエラー: {str(e)}")
            self.stats['api_errors'] += 1
            return self._create_fallback_result(
                target_patent_data['patent_id'],
                base_elements,
                error=str(e)
            )

    def _create_fallback_result(
        self,
        patent_id: str,
        base_elements: List[Dict],
        error: str = None
    ) -> Dict:
        """エラー時のフォールバック結果生成"""
        return {
            "target_patent_id": patent_id,
            "comparison_date": datetime.now().strftime('%Y-%m-%d'),
            "element_comparisons": [
                {
                    "element_id": elem['構成要素番号'],
                    "is_disclosed": False,
                    "evidence": {
                        "locations": [],
                        "quoted_text": "",
                        "reasoning": f"エラーのため判断不可: {error}"
                    }
                }
                for elem in base_elements
            ],
            "overall_assessment": {
                "total_elements": len(base_elements),
                "disclosed_elements": 0,
                "disclosure_rate": 0.0,
                "novelty_risk": "unknown",
                "error": error
            }
        }

    def assess_single_patent(
        self,
        base_patent_elements: List[Dict],
        target_patent_id: str
    ) -> Dict:
        """
        単一の対象特許に対する構成対比

        Args:
            base_patent_elements: 本願特許の構成要素
            target_patent_id: 対象特許ID

        Returns:
            構成対比結果
        """
        print(f"  構成対比実行: {target_patent_id}", flush=True)

        try:
            # 特許全文データ取得
            target_data = self._fetch_patent_full_data(target_patent_id)

            # Geminiで構成対比
            comparison_result = self._compare_with_gemini(
                base_patent_elements,
                target_data
            )

            # 結果保存
            output_path = self.output_dir / f"comparison_{target_patent_id}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(comparison_result, f, ensure_ascii=False, indent=2)

            self.stats['successful_comparisons'] += 1
            return comparison_result

        except Exception as e:
            print(f"    ❌ エラー: {target_patent_id} - {str(e)}")
            self.stats['failed_comparisons'] += 1
            return self._create_fallback_result(target_patent_id, base_patent_elements, str(e))

    def extract_x_references_with_priority(
        self,
        comparison_results: List[Dict],
        all_elements: Set[str],
        independent_elements: Set[str]
    ) -> Tuple[List[str], str]:
        """
        X文献の摘出（優先順位付きフォールバック戦略）

        新ロジック（v2.1.2+）:
        - 優先順位付きフォールバック:
          優先度1: 全要素をカバー → 見つかったら終了
          優先度2: 独立請求項をカバー → 見つかったら終了
          見つからない: X文献なし

        Args:
            comparison_results: 全ての構成対比結果
            all_elements: 全構成要素IDのセット
            independent_elements: 独立請求項の構成要素IDのセット

        Returns:
            (X文献の特許IDリスト, 採用された優先度レベル)
        """
        # 優先度1: 全要素をカバーする文献
        print(f"  優先度1: 全要素をカバーするX文献を探索中...")
        x_all = self._search_x_references(comparison_results, all_elements)
        if x_all:
            print(f"    → 見つかりました（{len(x_all)}件）")
            return x_all, "x_priority_1_all_elements"

        print(f"    → 見つかりませんでした")

        # 優先度2: 独立請求項をカバーする文献
        print(f"  優先度2: 独立請求項をカバーするX文献を探索中...")
        x_independent = self._search_x_references(comparison_results, independent_elements)
        if x_independent:
            print(f"    → 見つかりました（{len(x_independent)}件）")
            return x_independent, "x_priority_2_independent_elements"

        print(f"    → 見つかりませんでした")

        # 何も見つからなかった
        return [], "no_x_references"

    def _search_x_references(
        self,
        comparison_results: List[Dict],
        element_ids: Set[str]
    ) -> List[str]:
        """
        X文献の探索（指定された要素セットで）

        Args:
            comparison_results: 全ての構成対比結果
            element_ids: 対象とする構成要素IDのセット

        Returns:
            X文献の特許IDリスト
        """
        x_references = []

        for result in comparison_results:
            patent_id = result.get('target_patent_id')
            element_comparisons = result.get('element_comparisons', [])

            # 対象構成要素の開示状況を確認
            disclosed_elements = set()
            for elem in element_comparisons:
                if elem.get('is_disclosed', False) and elem['element_id'] in element_ids:
                    disclosed_elements.add(elem['element_id'])

            # 全ての対象構成要素が開示されているか
            if disclosed_elements == element_ids:
                x_references.append(patent_id)

        return x_references

    def extract_x_references(
        self,
        comparison_results: List[Dict],
        element_ids: Set[str]
    ) -> List[str]:
        """
        X文献の摘出（単純版・下位互換用）

        このメソッドは下位互換性のために残していますが、
        新しいロジックでは extract_x_references_with_priority() を使用してください。

        Args:
            comparison_results: 全ての構成対比結果
            element_ids: 対象とする構成要素IDのセット

        Returns:
            X文献の特許IDリスト
        """
        return self._search_x_references(comparison_results, element_ids)

    def _search_y_combinations(
        self,
        patent_coverage: Dict[str, Set[str]],
        element_ids: Set[str],
        k: int
    ) -> List[Dict]:
        """
        指定されたk（組み合わせ数）でY文献を探索

        Args:
            patent_coverage: 各特許の開示要素マッピング
            element_ids: 対象とする構成要素IDのセット
            k: 組み合わせ数（2または3）

        Returns:
            Y文献候補のリスト
        """
        y_references = []

        # 各特許を主引例として試す
        for primary_patent in patent_coverage.keys():
            # 副引例の候補（主引例以外）
            secondary_candidates = [p for p in patent_coverage.keys() if p != primary_patent]

            # 副引例の組み合わせ（k-1件: 1件または2件）
            for secondary_combo in combinations(secondary_candidates, k - 1):
                # 主引例 + 副引例の組み合わせ
                combo = [primary_patent] + list(secondary_combo)

                # 組み合わせでカバーされる構成要素の論理和
                combined_coverage = set()
                for patent_id in combo:
                    combined_coverage |= patent_coverage[patent_id]

                # 全ての対象構成要素がカバーされているか
                if combined_coverage == element_ids:
                    y_references.append({
                        "patents": combo,
                        "primary_reference": primary_patent,
                        "secondary_references": list(secondary_combo),
                        "combination_count": k,
                        "coverage": {
                            pid: list(patent_coverage[pid])
                            for pid in combo
                        }
                    })

        return y_references

    def extract_y_references_with_priority(
        self,
        comparison_results: List[Dict],
        all_elements: Set[str],
        independent_elements: Set[str]
    ) -> Tuple[List[Dict], str]:
        """
        Y文献の摘出（優先順位付きフォールバック戦略）

        新ロジック（v2.1.2+）:
        - k=1（単独特許）は除外
        - 優先順位付きフォールバック:
          優先度1: k=2 × 全要素 → 見つかったら終了
          優先度2: k=2 × 独立請求項 【並行】
          優先度3: k=3 × 全要素     【並行】→ どちらか見つかったら両方出力して終了
          優先度4: k=3 × 独立請求項 → 見つかったら終了
          見つからない: Y文献なし

        Args:
            comparison_results: 全ての構成対比結果
            all_elements: 全構成要素IDのセット
            independent_elements: 独立請求項の構成要素IDのセット

        Returns:
            (Y文献のリスト, 採用された優先度レベル)
        """
        # 各特許がどの構成要素を開示しているかをマッピング（全要素ベース）
        patent_coverage_all = {}
        patent_coverage_independent = {}

        for result in comparison_results:
            patent_id = result.get('target_patent_id')
            element_comparisons = result.get('element_comparisons', [])

            # 全要素での開示
            disclosed_all = set()
            for elem in element_comparisons:
                if elem.get('is_disclosed', False) and elem['element_id'] in all_elements:
                    disclosed_all.add(elem['element_id'])
            if disclosed_all:
                patent_coverage_all[patent_id] = disclosed_all

            # 独立請求項での開示
            disclosed_independent = set()
            for elem in element_comparisons:
                if elem.get('is_disclosed', False) and elem['element_id'] in independent_elements:
                    disclosed_independent.add(elem['element_id'])
            if disclosed_independent:
                patent_coverage_independent[patent_id] = disclosed_independent

        # 優先度1: k=2 × 全要素
        print(f"  優先度1: k=2 × 全要素で探索中...")
        y_k2_all = self._search_y_combinations(patent_coverage_all, all_elements, k=2)
        if y_k2_all:
            print(f"    → 見つかりました（{len(y_k2_all)}件）")
            return y_k2_all, "priority_1_k2_all_elements"

        print(f"    → 見つかりませんでした")

        # 優先度2 & 3（並行探索）
        print(f"  優先度2 & 3: k=2 × 独立請求項 と k=3 × 全要素 を並行探索中...")
        y_k2_independent = self._search_y_combinations(patent_coverage_independent, independent_elements, k=2)
        y_k3_all = self._search_y_combinations(patent_coverage_all, all_elements, k=3)

        if y_k2_independent and y_k3_all:
            # 両方見つかった場合は両方をマージ
            print(f"    → 両方見つかりました（k=2独立: {len(y_k2_independent)}件, k=3全要素: {len(y_k3_all)}件）")
            merged = y_k2_independent + y_k3_all
            return merged, "priority_2_3_k2_independent_k3_all"
        elif y_k2_independent:
            print(f"    → k=2 × 独立請求項のみ見つかりました（{len(y_k2_independent)}件）")
            return y_k2_independent, "priority_2_k2_independent_elements"
        elif y_k3_all:
            print(f"    → k=3 × 全要素のみ見つかりました（{len(y_k3_all)}件）")
            return y_k3_all, "priority_3_k3_all_elements"

        print(f"    → どちらも見つかりませんでした")

        # 優先度4: k=3 × 独立請求項
        print(f"  優先度4: k=3 × 独立請求項で探索中...")
        y_k3_independent = self._search_y_combinations(patent_coverage_independent, independent_elements, k=3)
        if y_k3_independent:
            print(f"    → 見つかりました（{len(y_k3_independent)}件）")
            return y_k3_independent, "priority_4_k3_independent_elements"

        print(f"    → 見つかりませんでした")

        # 何も見つからなかった
        return [], "no_y_references"

    def extract_y_references(
        self,
        comparison_results: List[Dict],
        element_ids: Set[str],
        max_combination: int = 3
    ) -> List[Dict]:
        """
        Y文献の摘出（単純版・下位互換用）

        このメソッドは下位互換性のために残していますが、
        新しいロジックでは extract_y_references_with_priority() を使用してください。

        Args:
            comparison_results: 全ての構成対比結果
            element_ids: 対象とする構成要素IDのセット
            max_combination: 最大組み合わせ数（デフォルト3）

        Returns:
            Y文献のリスト
        """
        # 各特許がどの構成要素を開示しているかをマッピング
        patent_coverage = {}
        for result in comparison_results:
            patent_id = result.get('target_patent_id')
            element_comparisons = result.get('element_comparisons', [])

            disclosed = set()
            for elem in element_comparisons:
                if elem.get('is_disclosed', False) and elem['element_id'] in element_ids:
                    disclosed.add(elem['element_id'])

            if disclosed:
                patent_coverage[patent_id] = disclosed

        # k=2, k=3の両方を探索
        y_references = []
        for k in range(2, max_combination + 1):
            y_k = self._search_y_combinations(patent_coverage, element_ids, k)
            y_references.extend(y_k)

        return y_references

    def assess_novelty(
        self,
        base_patent_structure_file: str,
        search_result_file: str,
        limit: Optional[int] = None
    ) -> Dict:
        """
        進歩性判断の実行（メインメソッド）

        Args:
            base_patent_structure_file: 本願特許構成要素JSONパス
            search_result_file: 検索結果JSONパス
            limit: 処理する特許数の上限（None=全件）

        Returns:
            進歩性判断サマリー
        """
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"進歩性判断（構成対比）開始")
        print(f"{'='*60}")
        print(f"使用モデル: {self.model_name}")
        print(f"並列処理数: {self.max_workers}\n")

        # 入力データ読み込み
        with open(base_patent_structure_file, 'r', encoding='utf-8') as f:
            base_data = json.load(f)
            # 本願特許IDの取得（優先順位: 1. JSONのpatent_id, 2. ファイル名から抽出）
            base_patent_id = base_data.get('patent_id')
            if not base_patent_id or base_patent_id in ['Unknown', 'success']:
                # ファイル名からpatent_idを抽出（例: test_001_JP2013224028_structure.json -> JP2013224028）
                import re
                filename = Path(base_patent_structure_file).name
                match = re.search(r'(JP\d{4,}\d+[A-Z]?)', filename, re.IGNORECASE)
                if match:
                    base_patent_id = match.group(1).upper()
                else:
                    base_patent_id = 'Unknown'
            base_elements = base_data['構成要件']

        with open(search_result_file, 'r', encoding='utf-8') as f:
            search_data = json.load(f)
            target_patent_ids = search_data.get('merged_patent_ids', [])

        # 本願特許自身を除外（重要：X文献・Y文献は先行技術文献であるべき）
        # 特許番号の正規化（末尾のAを除去して比較）
        base_patent_id_normalized = base_patent_id.rstrip('A')
        original_count = len(target_patent_ids)
        target_patent_ids = [
            pid for pid in target_patent_ids
            if pid.rstrip('A') != base_patent_id_normalized
        ]
        excluded_count = original_count - len(target_patent_ids)
        if excluded_count > 0:
            print(f"⚠ 警告: 検索結果から本願特許自身を除外しました: {excluded_count}件")

        # 処理対象の限定
        if limit:
            target_patent_ids = target_patent_ids[:limit]

        print(f"本願特許: {base_patent_id}")
        print(f"構成要素数: {len(base_elements)}")
        print(f"対象特許数: {len(target_patent_ids)}（本願特許を除く）\n")

        # Phase 1: 個別構成対比（並列処理）
        print(f"Phase 1: 個別構成対比を実行中...")
        all_comparisons = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.assess_single_patent,
                    base_elements,
                    patent_id
                ): patent_id
                for patent_id in target_patent_ids
            }

            for future in as_completed(futures):
                result = future.result()
                all_comparisons.append(result)
                self.stats['total_comparisons'] += 1

                # 進捗表示
                if self.stats['total_comparisons'] % 10 == 0:
                    print(f"  進捗: {self.stats['total_comparisons']}/{len(target_patent_ids)}")

        print(f"Phase 1完了: {len(all_comparisons)}件の構成対比完了\n")

        # Phase 2: X文献・Y文献の摘出（優先順位付き）
        print(f"Phase 2: X文献・Y文献の摘出を実行中...")

        # 構成要素の分類
        independent_elements = set(
            elem['構成要素番号']
            for elem in base_elements
            if elem.get('is_independent', False)
        )

        all_elements = set(elem['構成要素番号'] for elem in base_elements)

        print(f"  独立請求項の構成要素: {len(independent_elements)}個")
        print(f"  全構成要素: {len(all_elements)}個\n")

        # X文献の摘出（優先順位付きフォールバック）
        print(f"X文献の探索（優先順位付きフォールバック）...")
        final_x_refs, x_priority_level = self.extract_x_references_with_priority(
            all_comparisons,
            all_elements,
            independent_elements
        )
        print(f"  採用された優先度: {x_priority_level}")
        print(f"  X文献: {len(final_x_refs)}件\n")

        # Y文献の摘出（優先順位付きフォールバック）
        print(f"Y文献の探索（優先順位付きフォールバック）...")
        final_y_refs, y_priority_level = self.extract_y_references_with_priority(
            all_comparisons,
            all_elements,
            independent_elements
        )
        print(f"  採用された優先度: {y_priority_level}")
        print(f"  Y文献: {len(final_y_refs)}件\n")

        # 最終結果（X文献とY文献の優先度レベルを統合）
        priority_level = f"{x_priority_level}|{y_priority_level}"

        # サマリー生成
        elapsed_time = time.time() - start_time
        self.stats['total_time_seconds'] = elapsed_time

        summary = {
            "base_patent_id": base_patent_id,
            "assessment_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "search_results_count": len(target_patent_ids),
            "successful_comparisons": self.stats['successful_comparisons'],
            "failed_comparisons": self.stats['failed_comparisons'],
            "priority_level_used": priority_level,
            "x_references": {
                "count": len(final_x_refs),
                "patents": final_x_refs
            },
            "y_references": {
                "count": len(final_y_refs),
                "combinations": final_y_refs[:20]  # 上位20件のみ
            },
            "statistics": self.stats,
            "elapsed_time_seconds": elapsed_time
        }

        # サマリー保存
        summary_path = self.output_dir / "novelty_assessment_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"{'='*60}")
        print(f"処理完了")
        print(f"{'='*60}")
        print(f"総処理件数: {self.stats['total_comparisons']}")
        print(f"成功: {self.stats['successful_comparisons']}")
        print(f"失敗: {self.stats['failed_comparisons']}")
        print(f"採用された優先度: {priority_level}")
        print(f"X文献数: {len(final_x_refs)}")
        print(f"Y文献数: {len(final_y_refs)}")
        print(f"処理時間: {elapsed_time:.1f}秒")
        print(f"サマリー保存先: {summary_path}\n")

        return summary



if __name__ == "__main__":
    # テスト実行
    import sys

    if len(sys.argv) < 4:
        print("使用方法: python novelty_assessment_engine.py <project_id> <structure_json> <search_result_json> [limit]")
        sys.exit(1)

    project_id = sys.argv[1]
    structure_file = sys.argv[2]
    search_file = sys.argv[3]
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None

    engine = NoveltyAssessmentEngine(
        project_id=project_id,
        location="global",  # Gemini 3 ProはGlobalエンドポイント使用
        model_name="gemini-3-pro-preview",
        output_dir="./novelty_assessment_results"
    )

    summary = engine.assess_novelty(
        base_patent_structure_file=structure_file,
        search_result_file=search_file,
        limit=limit
    )

    print(f"\n完了: {summary['x_references']['count']}件のX文献、{summary['y_references']['count']}件のY文献を検出")
