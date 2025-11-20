#!/usr/bin/env python3
"""
特許構成要件キーワード抽出システム
Claude Sonnet 4.5 (Vertex AI) + PatentField API による検索キーワード自動生成

作成日: 2025年
対象: 特許審査における先行文献調査実務
"""

import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Union, Optional
import sys

# Google Cloud / Vertex AI
from google.oauth2 import service_account
from anthropic import AnthropicVertex


class PatentKeywordExtractor:
    """構成要件から検索キーワードを抽出"""

    def __init__(
        self,
        credentials_path: str,
        patentfield_key_path: str = "../patentfield_key.json",
        project_id: str = "ttdc-in-house-dev",
        region: str = "us-east5",
        model: str = "claude-sonnet-4-5@20250929"
    ):
        """
        初期化

        Args:
            credentials_path: Google Cloud サービスアカウントJSONファイルのパス
            patentfield_key_path: PatentField API認証情報JSONファイルのパス
            project_id: Google Cloud プロジェクトID
            region: Vertex AIリージョン
            model: Claude モデル名
        """
        self.project_id = project_id
        self.region = region
        self.model = model

        # Google Cloud認証情報の読み込み
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

        # Claude クライアントの初期化
        self.client = AnthropicVertex(
            project_id=self.project_id,
            region=self.region,
            credentials=self.credentials
        )

        # PatentField API設定の読み込み
        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        print(f"初期化完了: Claude {model}, PatentField API")

    def build_search_query(
        self,
        constituents: List[Dict],
        importance_threshold: float = 0.9
    ) -> Dict:
        """
        検索式構築（Claude使用）

        Args:
            constituents: 構成要件リスト
            importance_threshold: 重要度の閾値（この値以上をAND条件に使用）

        Returns:
            {"query": "検索式", "strategy": "戦略説明", "high_importance_items": [...]}
        """
        # 重要度でソート
        sorted_constituents = sorted(
            constituents,
            key=lambda x: x['構成要素の重要度'],
            reverse=True
        )

        # プロンプト構築
        constituents_text = "\n".join([
            f"[{c['構成要素番号']}] 重要度{c['構成要素の重要度']}: {c['構成要素']}"
            for c in sorted_constituents
        ])

        system_prompt = """あなたは特許検索の専門家です。
構成要件から先行文献調査用の検索式を構築する際、以下の原則に従ってください：

1. 重要度の高い構成要素（0.9以上）をAND条件で組み合わせる
2. ヒット件数を絞り込むため、必須要素のみを使用
3. PatentField APIのコマンド検索構文を使用（CL: 請求項、AB: 要約、TI: タイトル）
4. 検索式は簡潔かつ効果的に

**重要な構文制約:**
- ネストした括弧は使用禁止（例: CL:(A AND (B OR C)) は不可）
- 括弧は1レベルのみ（例: CL:(A OR B) AND CL:C は可）
- OR条件は同じフィールド内でのみ使用（例: CL:(A OR B) は可）
- 複雑な条件は分解して記述（例: CL:A AND CL:(B OR C) AND CL:D）"""

        user_prompt = f"""以下の構成要件から、先行文献調査用の検索式を構築してください。

【構成要件リスト】
{constituents_text}

【要求】
1. 重要度{importance_threshold}以上の要素を特定
2. これらをAND条件で組み合わせた検索式を作成
3. PatentField APIのコマンド検索形式で出力
4. ヒット件数の目標: 50-500件程度

【検索式の正しい例】
✓ 正: CL:論理回路 AND CL:トランジスタ AND CL:オフ電流
✓ 正: CL:論理回路 AND CL:トランジスタ AND CL:オフ電流 AND CL:容量素子
✓ 正: (CL:論理回路 OR CL:フリップフロップ) AND CL:トランジスタ AND CL:オフ電流

【検索式の誤った例】
✗ 誤: CL:(トランジスタ AND (オフ電流 OR リーク電流)) ← ネストした括弧
✗ 誤: CL:(A OR B) AND CL:(C OR D) ← 複数のOR句
✗ 誤: CL:(論理回路 OR フリップフロップ) AND CL:(オフ電流 OR リーク電流) ← 複数のOR句

【重要な制約】
- OR句は最大1つのみ使用可能
- OR句を使う場合は (CL:A OR CL:B) の形式を推奨
- 基本はシンプルなANDのみの検索式を優先

【出力フォーマット（JSON）】
{{
  "query": "CL:論理回路 AND CL:トランジスタ AND CL:オフ電流",
  "strategy": "重要度1.0の「オフ電流」を核として、重要度0.95の「論理回路」「トランジスタ」をAND条件で組み合わせ",
  "high_importance_items": ["1d", "1a", "1c"],
  "expected_hits": "100-300件"
}}

JSONのみを出力してください。"""

        print("検索式を構築中...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = response.content[0].text

            # トークン使用量
            tokens = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }

            # JSONパース
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_text = response_text[json_start:json_end]
            result = json.loads(json_text)

            result['tokens'] = tokens

            return result

        except Exception as e:
            print(f"検索式構築エラー: {e}")
            raise

    def preliminary_search(
        self,
        query: str,
        limit: int = 50
    ) -> Dict:
        """
        PatentField API予備検索

        Args:
            query: 検索式
            limit: 取得件数（最大50件）

        Returns:
            {"n_hits": ヒット件数, "records": [...]}
        """
        print(f"PatentField API予備検索実行: {query}")
        print(f"取得件数: {limit}件")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        payload = {
            "search_type": "expert",  # コマンド検索
            "q": query,
            "columns": [
                "app_doc_id",
                "title",
                "abstract",
                "app_claims",
                "description"
            ],
            "limit": limit,
            "sort_keys": ["-_score"]
        }

        try:
            response = requests.post(
                self.pf_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )

            response.raise_for_status()
            result = response.json()

            print(f"ヒット件数: {result.get('n_hits', 0)}件")
            print(f"取得件数: {len(result.get('records', []))}件")

            return result

        except requests.exceptions.RequestException as e:
            print(f"PatentField API エラー: {e}")
            raise

    def refine_keywords(
        self,
        constituent: Dict,
        search_results: List[Dict]
    ) -> Dict:
        """
        キーワード精錬（Claude使用）

        Args:
            constituent: 構成要素
            search_results: 予備検索結果

        Returns:
            {
                "ドンピシャキーワード_日本語": [...],
                "上位概念キーワード_日本語": [...],
                "下位概念キーワード_日本語": [...],
                "ドンピシャキーワード_英語": [...],
                "上位概念キーワード_英語": [...],
                "下位概念キーワード_英語": [...]
            }
        """
        # 検索結果から全文テキストを結合
        texts = []
        for i, record in enumerate(search_results[:20], 1):  # 最初の20件を分析
            title = record.get('title', '')
            abstract = record.get('abstract', '')
            claims = record.get('app_claims', '')[:5000]  # 最初の5000文字
            texts.append(f"【文献{i}】\nタイトル: {title}\n要約: {abstract}\n請求項: {claims}\n")

        combined_text = "\n".join(texts)

        system_prompt = """あなたは特許検索のキーワード分析専門家です。

予備検索結果から、構成要素に対する最適な検索キーワードを3階層で抽出してください：

1. ドンピシャキーワード: 構成要素に完全一致する用語
2. 上位概念キーワード: より広い概念の用語
3. 下位概念キーワード: より具体的な用語

各階層で5-10個のキーワードを優先度順に並べ、日本語と英語の両方を出力してください。"""

        user_prompt = f"""【構成要素】
番号: {constituent['構成要素番号']}
内容: {constituent['構成要素']}
重要度: {constituent['構成要素の重要度']}

【予備検索結果（抜粋）】
{combined_text[:30000]}

【タスク】
上記の予備検索結果を分析し、この構成要素に対する検索キーワードを抽出してください。

【出力フォーマット（JSON）】
{{
  "ドンピシャキーワード_日本語": [
    {{"keyword": "論理回路", "priority": 1, "頻出度": 45}},
    {{"keyword": "論理ゲート", "priority": 2, "頻出度": 23}}
  ],
  "上位概念キーワード_日本語": [
    {{"keyword": "回路", "priority": 1, "頻出度": 87}},
    {{"keyword": "電子回路", "priority": 2, "頻出度": 34}}
  ],
  "下位概念キーワード_日本語": [
    {{"keyword": "AND回路", "priority": 1, "頻出度": 15}},
    {{"keyword": "OR回路", "priority": 2, "頻出度": 12}}
  ],
  "ドンピシャキーワード_英語": [
    {{"keyword": "logic circuit", "priority": 1, "頻出度": 42}},
    {{"keyword": "logic gate", "priority": 2, "頻出度": 21}}
  ],
  "上位概念キーワード_英語": [
    {{"keyword": "circuit", "priority": 1, "頻出度": 82}},
    {{"keyword": "electronic circuit", "priority": 2, "頻出度": 31}}
  ],
  "下位概念キーワード_英語": [
    {{"keyword": "AND gate", "priority": 1, "頻出度": 14}},
    {{"keyword": "OR gate", "priority": 2, "頻出度": 11}}
  ]
}}

JSONのみを出力してください。"""

        print(f"  [{constituent['構成要素番号']}] キーワード精錬中...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = response.content[0].text

            # トークン使用量
            tokens = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }

            # JSONパース
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_text = response_text[json_start:json_end]
            keywords = json.loads(json_text)

            keywords['tokens'] = tokens

            return keywords

        except Exception as e:
            print(f"  キーワード精錬エラー: {e}")
            raise

    def extract_keywords(
        self,
        constituent_json_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        min_importance: float = 0.7,
        importance_threshold: float = 0.9
    ) -> Dict:
        """
        メイン処理: 構成要件JSONからキーワード抽出

        Args:
            constituent_json_path: 構成要件JSONファイルのパス
            output_path: 出力ファイルパス（Noneの場合は自動生成）
            min_importance: キーワード抽出対象の最小重要度
            importance_threshold: 予備検索で使用する重要度閾値

        Returns:
            分析結果の辞書
        """
        start_time = time.time()
        constituent_json_path = Path(constituent_json_path)

        print(f"構成要件JSONを読み込み中: {constituent_json_path}")

        # 構成要件JSON読み込み
        with open(constituent_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get('status') != 'success':
            raise ValueError(f"構成要件JSONのstatusがsuccessではありません: {data.get('status')}")

        constituents = data['構成要件']
        print(f"構成要件数: {len(constituents)}個")

        # 重要度でフィルタ
        target_constituents = [
            c for c in constituents
            if c['構成要素の重要度'] >= min_importance
        ]
        print(f"抽出対象（重要度>={min_importance}）: {len(target_constituents)}個")

        # ステップ1: 検索式構築
        print("\n" + "="*60)
        print("ステップ1: 検索式構築")
        print("="*60)
        query_result = self.build_search_query(constituents, importance_threshold)

        print(f"検索式: {query_result['query']}")
        print(f"戦略: {query_result['strategy']}")

        # ステップ2: PatentField API予備検索
        print("\n" + "="*60)
        print("ステップ2: PatentField API予備検索")
        print("="*60)
        search_result = self.preliminary_search(query_result['query'], limit=50)

        # ステップ3: キーワード精錬
        print("\n" + "="*60)
        print("ステップ3: キーワード精錬")
        print("="*60)

        keywords_list = []
        total_refine_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        for constituent in target_constituents:
            keywords = self.refine_keywords(constituent, search_result.get('records', []))

            # トークンを集計
            tokens = keywords.pop('tokens')
            for key in total_refine_tokens:
                total_refine_tokens[key] += tokens[key]

            # 結果に追加
            keywords_list.append({
                "構成要素番号": constituent['構成要素番号'],
                "構成要素": constituent['構成要素'],
                "重要度": constituent['構成要素の重要度'],
                **keywords
            })

        # 処理時間
        processing_time = time.time() - start_time

        # 結果を構造化
        result = {
            "status": "success",
            "input_file": str(constituent_json_path),
            "予備検索": {
                "検索式": query_result['query'],
                "戦略": query_result['strategy'],
                "ヒット件数": search_result.get('n_hits', 0),
                "取得件数": len(search_result.get('records', [])),
                "高重要度構成要素": query_result.get('high_importance_items', [])
            },
            "keywords": keywords_list,
            "tokens": {
                "step1_構築": query_result['tokens'],
                "step3_精錬": total_refine_tokens,
                "total_tokens": (
                    query_result['tokens']['total_tokens'] +
                    total_refine_tokens['total_tokens']
                )
            },
            "処理時間_秒": round(processing_time, 2),
            "model": self.model
        }

        # 出力ファイルパスの決定
        if output_path is None:
            output_path = constituent_json_path.parent / f"{constituent_json_path.stem.replace('_構成要件', '')}_キーワード.json"
        else:
            output_path = Path(output_path)

        # 結果を保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n結果を保存しました: {output_path}")

        return result

    def print_summary(self, result: Dict):
        """分析結果のサマリーを表示"""
        print("\n" + "="*60)
        print("キーワード抽出 - 分析結果サマリー")
        print("="*60)

        if result['status'] == 'success':
            print(f"✓ 分析成功")

            # 予備検索情報
            pre_search = result['予備検索']
            print(f"\n【予備検索】")
            print(f"  検索式: {pre_search['検索式']}")
            print(f"  戦略: {pre_search['戦略']}")
            print(f"  ヒット件数: {pre_search['ヒット件数']:,}件")
            print(f"  取得件数: {pre_search['取得件数']}件")

            # キーワード抽出結果
            print(f"\n【キーワード抽出】")
            print(f"  抽出対象構成要素数: {len(result['keywords'])}個")

            for i, kw in enumerate(result['keywords'][:3], 1):  # 最初の3個を表示
                print(f"\n  {i}. [{kw['構成要素番号']}] {kw['構成要素'][:40]}...")
                print(f"     重要度: {kw['重要度']}")
                print(f"     日本語ドンピシャ: {', '.join([k['keyword'] for k in kw['ドンピシャキーワード_日本語'][:3]])}")
                print(f"     英語ドンピシャ: {', '.join([k['keyword'] for k in kw['ドンピシャキーワード_英語'][:3]])}")

            if len(result['keywords']) > 3:
                print(f"\n  ... 他 {len(result['keywords']) - 3} 個")

            # トークン使用量
            tokens = result['tokens']
            print(f"\n【トークン使用量】")
            print(f"  ステップ1（検索式構築）: {tokens['step1_構築']['total_tokens']:,} tokens")
            print(f"  ステップ3（キーワード精錬）: {tokens['step3_精錬']['total_tokens']:,} tokens")
            print(f"  合計: {tokens['total_tokens']:,} tokens")

            print(f"\n処理時間: {result['処理時間_秒']} 秒")
            print(f"モデル: {result['model']}")

        else:
            print(f"✗ 分析失敗")
            print(f"エラー: {result.get('message', '不明')}")


def main():
    """メイン実行関数（コマンドライン用）"""
    import argparse

    parser = argparse.ArgumentParser(
        description='特許構成要件キーワード抽出システム（Claude Sonnet 4.5 + PatentField API）'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='入力ファイル（構成要件JSON）'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='出力ファイル（デフォルト: 入力ファイル名_キーワード.json）'
    )
    parser.add_argument(
        '-c', '--credentials',
        type=str,
        default='../ttdc-in-house-dev-3e07247326cb.json',
        help='Google Cloud サービスアカウントJSONファイル'
    )
    parser.add_argument(
        '-p', '--patentfield-key',
        type=str,
        default='../patentfield_key.json',
        help='PatentField API認証情報JSONファイル'
    )
    parser.add_argument(
        '-m', '--min-importance',
        type=float,
        default=0.7,
        help='キーワード抽出対象の最小重要度'
    )
    parser.add_argument(
        '-t', '--threshold',
        type=float,
        default=0.9,
        help='予備検索で使用する重要度閾値'
    )

    args = parser.parse_args()

    # エクストラクター初期化
    extractor = PatentKeywordExtractor(
        credentials_path=args.credentials,
        patentfield_key_path=args.patentfield_key
    )

    # キーワード抽出実行
    result = extractor.extract_keywords(
        constituent_json_path=args.input_file,
        output_path=args.output,
        min_importance=args.min_importance,
        importance_threshold=args.threshold
    )

    # サマリー表示
    extractor.print_summary(result)

    # 終了コード
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
