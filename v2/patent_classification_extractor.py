#!/usr/bin/env python3
"""
特許分類コード抽出システム

構成要件JSONから特許分類コード（Fterm, FI, IPC, CPC）を抽出するシステム。
PatentField APIの予備検索結果とOpenSearch特許分類検索APIの結果を統合し、
Claude Sonnet 4.5を用いて3段階の分類階層を生成します。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from google.oauth2 import service_account
from anthropic import AnthropicVertex


class PatentClassificationExtractor:
    """特許分類コード抽出クラス"""

    def __init__(
        self,
        credentials_path: str,
        patentfield_key_path: str = "../patentfield_key.json",
        opensearch_base_url: str = "http://localhost:8000",
        project_id: str = "ttdc-in-house-dev",
        region: str = "us-east5",
        model: str = "claude-sonnet-4-5@20250929"
    ):
        """
        初期化

        Args:
            credentials_path: Google Cloud認証情報JSONファイルのパス
            patentfield_key_path: PatentField API keyファイルのパス
            opensearch_base_url: OpenSearch APIのベースURL
            project_id: Google CloudプロジェクトID
            region: Vertex AIのリージョン
            model: 使用するClaudeモデル
        """
        # Claude Sonnet 4.5クライアントの初期化
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.client = AnthropicVertex(
            project_id=project_id,
            region=region,
            credentials=self.credentials
        )
        self.model = model

        # PatentField API設定の読み込み
        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        # OpenSearch API設定
        self.opensearch_base_url = opensearch_base_url

        print(f"✓ Claude Sonnet 4.5クライアント初期化完了 (model: {model})")
        print(f"✓ PatentField API設定読み込み完了")
        print(f"✓ OpenSearch API: {opensearch_base_url}")

    @staticmethod
    def _normalize_classification_code(code: str) -> str:
        """
        分類コードの正規化（空白除去）

        PatentField APIで検索可能な形式に正規化する。
        FI分類コードなどに含まれる空白を除去する。

        Args:
            code: 分類コード（例: "H02K  33/18", "F16H  35/00  G"）

        Returns:
            正規化された分類コード（例: "H02K33/18", "F16H35/00G"）

        Examples:
            >>> _normalize_classification_code("H02K  33/18")
            'H02K33/18'
            >>> _normalize_classification_code("F16H  35/00  G")
            'F16H35/00G'
            >>> _normalize_classification_code("G11B   5/325  F")
            'G11B5/325F'
        """
        # 全ての空白を除去
        return code.replace(' ', '')

    def patentfield_preliminary_search(
        self,
        constituents: List[Dict],
        min_importance: float = 0.9
    ) -> Dict[str, List[Dict]]:
        """
        PatentField APIで予備検索を実行し、分類コードランキングを取得

        Args:
            constituents: 構成要件リスト
            min_importance: 検索クエリ構築に使用する最小重要度

        Returns:
            分類コードランキング辞書 {
                'IPC': [...],
                'CPC': [...],
                'FI': [...],
                'Fterm': [...]
            }
        """
        print("\n" + "="*80)
        print("STEP 1: PatentField予備検索（分類コードランキング取得）")
        print("="*80)

        # 1. 検索クエリ構築
        search_query = self._build_search_query(constituents, min_importance)
        print(f"\n検索式: {search_query['query']}")
        print(f"戦略: {search_query['strategy']}")

        # 2. PatentField APIで集計検索
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        # 各分類タイプの集計条件
        classification_fields = {
            'IPC': 'ipcs',
            'CPC': 'cpcs',
            'FI': 'fis',
            'Fterm': 'fterms'
        }

        results = {}

        for class_type, field_name in classification_fields.items():
            print(f"\n{class_type}ランキング取得中...")

            payload = {
                "search_type": "expert",
                "q": search_query['query'],
                "columns": [field_name],  # 必要な分類フィールドのみ
                "limit": 100,  # 集計用に多めに取得
                "group_conditions": [
                    {
                        "key": field_name,
                        "limit": 20,  # 上位20件を取得
                        "sort_keys": ["-_nsubrecs"]
                    }
                ]
            }

            try:
                response = requests.post(
                    self.pf_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()

                data = response.json()

                # 集計結果を抽出（drilldowns_recordsから取得）
                if 'drilldowns_records' in data and field_name in data['drilldowns_records']:
                    drill_data = data['drilldowns_records'][field_name]
                    if isinstance(drill_data, list):
                        # "その他"を除外し、上位20件を取得
                        results[class_type] = [
                            {
                                'code': item['_key'],
                                'count': item['_nsubrecs'],
                                'title_ja': item.get('explain', ''),
                                'source': 'PatentField'
                            }
                            for item in drill_data
                            if item.get('_key') != 'その他'
                        ][:20]
                        print(f"  ✓ {len(results[class_type])}件取得")
                    else:
                        results[class_type] = []
                        print(f"  ⚠ 集計結果なし")
                else:
                    results[class_type] = []
                    print(f"  ⚠ 集計結果なし")

            except requests.exceptions.HTTPError as e:
                print(f"  ✗ HTTPエラー: {e}")
                print(f"  レスポンス: {e.response.text}")
                results[class_type] = []
            except Exception as e:
                print(f"  ✗ エラー: {e}")
                results[class_type] = []

        return results

    def opensearch_classification_search(
        self,
        constituents: List[Dict],
        classification_types: List[str] = ['IPC', 'CPC', 'FI']
    ) -> Dict[str, List[Dict]]:
        """
        OpenSearch APIで分類コード検索

        Args:
            constituents: 構成要件リスト
            classification_types: 検索対象の分類タイプリスト

        Returns:
            分類コード検索結果辞書 {
                'IPC': [...],
                'CPC': [...],
                'FI': [...]
            }
        """
        print("\n" + "="*80)
        print("STEP 2: OpenSearch特許分類検索")
        print("="*80)

        results = {ct: [] for ct in classification_types}

        for class_type in classification_types:
            print(f"\n{class_type}検索中...")
            all_results = {}  # code -> max score

            for const in constituents:
                query_text = const['構成要素']

                try:
                    response = requests.post(
                        f"{self.opensearch_base_url}/search/text",
                        json={
                            "query": query_text,
                            "classification_type": class_type,
                            "limit": 20,
                            "min_score": 0.0
                        },
                        timeout=30
                    )
                    response.raise_for_status()

                    data = response.json()

                    for result in data.get('results', []):
                        classification = result['classification']
                        code = classification['code']
                        score = result['similarity_score']

                        # 各コードの最高スコアを保持
                        if code not in all_results or all_results[code]['score'] < score:
                            all_results[code] = {
                                'code': code,
                                'score': score,
                                'title_ja': classification.get('title_ja', ''),
                                'title_en': classification.get('title_en', ''),
                                'source': 'OpenSearch'
                            }

                except requests.exceptions.RequestException as e:
                    print(f"  ⚠ 検索エラー ({const['構成要素番号']}): {e}")
                    continue

            # スコア順でソート
            results[class_type] = sorted(
                all_results.values(),
                key=lambda x: x['score'],
                reverse=True
            )[:30]  # 上位30件

            print(f"  ✓ {len(results[class_type])}件取得")

        return results

    def merge_and_hierarchize(
        self,
        patentfield_results: Dict[str, List[Dict]],
        opensearch_results: Dict[str, List[Dict]],
        constituents: List[Dict]
    ) -> Dict:
        """
        PatentFieldとOpenSearch結果を統合し、3段階階層化

        Args:
            patentfield_results: PatentField検索結果
            opensearch_results: OpenSearch検索結果
            constituents: 構成要件リスト

        Returns:
            階層化された分類コード辞書
        """
        print("\n" + "="*80)
        print("STEP 3: 結果統合と階層化（Claude使用）")
        print("="*80)

        classifications = {}

        # 各分類タイプを処理
        for class_type in ['IPC', 'CPC', 'FI', 'Fterm']:
            print(f"\n{class_type}処理中...")

            pf_codes = patentfield_results.get(class_type, [])
            os_codes = opensearch_results.get(class_type, [])

            # 統合と階層化
            hierarchy = self._merge_and_hierarchize_one_type(
                class_type=class_type,
                patentfield_codes=pf_codes,
                opensearch_codes=os_codes,
                constituents=constituents
            )

            classifications[class_type] = hierarchy

            print(f"  ✓ ドンピシャ: {len(hierarchy['ドンピシャ'])}件")
            print(f"  ✓ 上位概念: {len(hierarchy['上位概念'])}件")
            print(f"  ✓ 下位概念: {len(hierarchy['下位概念'])}件")

        return classifications

    def _merge_and_hierarchize_one_type(
        self,
        class_type: str,
        patentfield_codes: List[Dict],
        opensearch_codes: List[Dict],
        constituents: List[Dict]
    ) -> Dict:
        """
        1つの分類タイプについて統合と階層化を実行

        Args:
            class_type: 分類タイプ（IPC, CPC, FI, Fterm）
            patentfield_codes: PatentFieldからの分類コード
            opensearch_codes: OpenSearchからの分類コード
            constituents: 構成要件リスト

        Returns:
            階層化結果 {'ドンピシャ': [...], '上位概念': [...], '下位概念': [...]}
        """
        system_prompt = f"""あなたは特許分類のエキスパートです。
以下のタスクを実行してください：

1. **交差分析**: PatentField予備検索結果とOpenSearch検索結果の両方に出現する分類コードを特定
2. **階層分析**: 分類コードの親子関係を分析
3. **3段階分類**: 以下の3つのカテゴリーに分類
   - **ドンピシャ**: 構成要件に最も適合する分類コード（交差結果を優先）
   - **上位概念**: ドンピシャの親分類コード
   - **下位概念**: ドンピシャの子分類コード

**優先順位ルール:**
1. PatentFieldとOpenSearch両方に出現 → 最優先でドンピシャに分類
2. 出現頻度・スコアが高い → ドンピシャに分類
3. ドンピシャの明確な親コード → 上位概念
4. ドンピシャの明確な子コード → 下位概念

**出力形式:**
```json
{{
  "ドンピシャ": [
    {{
      "code": "分類コード",
      "title_ja": "日本語タイトル",
      "title_en": "英語タイトル",
      "priority": 1,
      "sources": ["PatentField", "OpenSearch"],
      "evidence": "選定理由"
    }}
  ],
  "上位概念": [...],
  "下位概念": [...]
}}
```

各カテゴリーは優先度順（priority: 1, 2, 3...）でソートしてください。
"""

        user_prompt = f"""# タスク: {class_type}分類コードの統合と階層化

## 構成要件
{json.dumps(constituents, ensure_ascii=False, indent=2)}

## PatentField予備検索結果（上位{len(patentfield_codes)}件）
{json.dumps(patentfield_codes, ensure_ascii=False, indent=2)}

## OpenSearch検索結果（上位{len(opensearch_codes)}件）
{json.dumps(opensearch_codes, ensure_ascii=False, indent=2)}

---

上記データを分析し、{class_type}分類コードを3段階（ドンピシャ/上位概念/下位概念）に階層化してください。

**重要:**
- PatentFieldとOpenSearchの交差を最優先
- 各カテゴリーは最大15件まで
- 必ずJSON形式で出力
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text

            # JSON抽出
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            hierarchy = json.loads(json_text)

            # 分類コードを正規化（空白除去）
            for concept_level in ['ドンピシャ', '上位概念', '下位概念']:
                if concept_level in hierarchy:
                    for item in hierarchy[concept_level]:
                        if 'code' in item:
                            item['code'] = self._normalize_classification_code(item['code'])

            return hierarchy

        except Exception as e:
            print(f"  ✗ Claude処理エラー: {e}")
            return {
                'ドンピシャ': [],
                '上位概念': [],
                '下位概念': []
            }

    def _build_search_query(
        self,
        constituents: List[Dict],
        min_importance: float
    ) -> Dict[str, str]:
        """
        構成要件から検索クエリを構築（Claude使用）

        Args:
            constituents: 構成要件リスト
            min_importance: 最小重要度

        Returns:
            {'query': 検索式, 'strategy': 戦略説明}
        """
        # 重要度フィールドは複数のパターンがあるため、優先順でチェック
        high_importance = [
            c for c in constituents
            if c.get('構成要素の重要度', c.get('構成要件の重要度', c.get('重要度', 0))) >= min_importance
        ]

        system_prompt = """あなたは特許検索クエリの構築エキスパートです。

**タスク:**
構成要件から、PatentField API用のコマンド検索式を構築してください。

**重要な構文制約:**
- ネストした括弧は使用禁止（例: (A AND (B OR C)) は不可）
- 括弧は1レベルのみ（例: (A OR B) AND C は可）
- OR条件は同じ括弧内でのみ使用（例: (A OR B) は可）
- 複雑な条件は分解して記述（例: A AND B AND C）
- **キーワードにはフィールドプレフィックス（CL:, AB:等）を付けず、全文検索とする**

**検索式の正しい例:**
✓ 正: 論理回路 AND トランジスタ AND オフ電流
✓ 正: (論理回路 OR フリップフロップ) AND トランジスタ AND オフ電流

**検索式の誤った例:**
✗ 誤: (トランジスタ AND (オフ電流 OR リーク電流)) ← ネストした括弧
✗ 誤: (A OR B) AND (C OR D) ← 複数のOR句
✗ 誤: CL:論理回路 AND CL:トランジスタ ← フィールドプレフィックス使用（全文検索にならない）

**出力形式:**
```json
{
  "query": "検索式",
  "strategy": "戦略説明"
}
```
"""

        user_prompt = f"""以下の高重要度構成要件からPatentField検索式を構築してください：

{json.dumps(high_importance, ensure_ascii=False, indent=2)}

重要度{min_importance}以上の要素を使用し、シンプルなAND接続を優先してください。
**重要: キーワードは最大4つまで、OR句は最大1つまで、ネスト禁止です。**
検索がヒットしないリスクを避けるため、少数の核心キーワードのみを使用してください。
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text

            # JSON抽出
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            result = json.loads(json_text)
            return result

        except Exception as e:
            print(f"警告: クエリ構築失敗、デフォルト使用: {e}")
            # フォールバック（キーワードは全文検索、フィールドプレフィックスなし）
            keywords = [c['構成要素'][:10] for c in high_importance[:3]]
            return {
                'query': ' AND '.join(keywords),
                'strategy': 'デフォルト戦略（上位3要素のAND検索、全文検索）'
            }

    def extract(
        self,
        input_file: str,
        output_file: Optional[str] = None,
        min_importance: float = 0.9
    ) -> Dict:
        """
        分類コード抽出の実行

        Args:
            input_file: 入力構成要件JSONファイル
            output_file: 出力ファイルパス（省略時は自動生成）
            min_importance: 検索に使用する最小重要度

        Returns:
            抽出結果の辞書
        """
        # 入力ファイル読み込み
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        constituents = data['構成要件']

        print(f"\n入力ファイル: {input_file}")
        print(f"構成要件数: {len(constituents)}")
        print(f"最小重要度: {min_importance}")

        # STEP 1: PatentField予備検索
        patentfield_results = self.patentfield_preliminary_search(
            constituents,
            min_importance
        )

        # STEP 2: OpenSearch検索
        opensearch_results = self.opensearch_classification_search(
            constituents,
            classification_types=['IPC', 'CPC', 'FI']
        )

        # STEP 3: 統合と階層化
        classifications = self.merge_and_hierarchize(
            patentfield_results,
            opensearch_results,
            constituents
        )

        # 結果の構築
        result = {
            'status': 'success',
            'input_file': input_file,
            'min_importance': min_importance,
            'classifications': classifications,
            'metadata': {
                'patentfield_counts': {
                    k: len(v) for k, v in patentfield_results.items()
                },
                'opensearch_counts': {
                    k: len(v) for k, v in opensearch_results.items()
                }
            }
        }

        # 出力ファイル保存
        if output_file is None:
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_特許分類.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print("\n" + "="*80)
        print("✓ 処理完了")
        print("="*80)
        print(f"出力ファイル: {output_file}")

        for class_type, hierarchy in classifications.items():
            print(f"\n{class_type}:")
            print(f"  ドンピシャ: {len(hierarchy['ドンピシャ'])}件")
            print(f"  上位概念: {len(hierarchy['上位概念'])}件")
            print(f"  下位概念: {len(hierarchy['下位概念'])}件")

        return result


def main():
    """コマンドライン実行"""
    import argparse

    parser = argparse.ArgumentParser(
        description='特許分類コード抽出システム',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python patent_classification_extractor.py tests/jp2014007731A_構成要件.json
  python patent_classification_extractor.py input.json --output output.json
  python patent_classification_extractor.py input.json --min-importance 0.95
        """
    )

    parser.add_argument(
        'input_file',
        help='入力構成要件JSONファイル'
    )
    parser.add_argument(
        '-o', '--output',
        help='出力ファイルパス（省略時は自動生成）'
    )
    parser.add_argument(
        '--credentials',
        default='../gcp-sa-key.json',
        help='Google Cloud認証情報ファイル (default: ../gcp-sa-key.json)'
    )
    parser.add_argument(
        '--patentfield-key',
        default='../patentfield_key.json',
        help='PatentField APIキーファイル (default: ../patentfield_key.json)'
    )
    parser.add_argument(
        '--opensearch-url',
        default='http://localhost:8000',
        help='OpenSearch APIのURL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--min-importance',
        type=float,
        default=0.9,
        help='検索に使用する最小重要度 (default: 0.9)'
    )

    args = parser.parse_args()

    # 入力ファイルの存在確認
    if not Path(args.input_file).exists():
        print(f"エラー: 入力ファイルが見つかりません: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # 認証情報の存在確認
    if not Path(args.credentials).exists():
        print(f"エラー: 認証情報ファイルが見つかりません: {args.credentials}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.patentfield_key).exists():
        print(f"エラー: PatentField APIキーファイルが見つかりません: {args.patentfield_key}", file=sys.stderr)
        sys.exit(1)

    try:
        # 抽出器の初期化
        extractor = PatentClassificationExtractor(
            credentials_path=args.credentials,
            patentfield_key_path=args.patentfield_key,
            opensearch_base_url=args.opensearch_url
        )

        # 抽出実行
        extractor.extract(
            input_file=args.input_file,
            output_file=args.output,
            min_importance=args.min_importance
        )

    except KeyboardInterrupt:
        print("\n\n処理を中断しました", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nエラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
