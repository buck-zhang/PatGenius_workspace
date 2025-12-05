#!/usr/bin/env python3
"""
PatentField特許検索実行システム - 構成要素ごと検索版

要件仕様に基づく実装：
- 各構成要素ごとに検索式を立て、独立請求項のみの構成要素の結果を統合
- 適応的検索ロジック（50-300件のしきい値判定）
- 並行処理による高速実行
- 重複削除

検索式作成ロジック：
1. ドンピシャFIをOR条件で検索
2. if 50 < ヒット件数 < 300: 終了
3. else ヒット件数 > 300: ドンピシャFI AND ドンピシャキーワード
4. else ヒット件数 < 50: ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from collections import defaultdict

# Google Cloud / Vertex AI for Claude
from google.oauth2 import service_account
from anthropic import AnthropicVertex

# Retry logic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class PerComponentSearchExecutor:
    """構成要素ごと検索実行システム"""

    def __init__(
        self,
        keywords_file: str,
        classifications_file: str,
        patentfield_key_path: str = "../patentfield_key.json",
        google_credentials_path: Optional[str] = None,
        enable_claude: bool = True
    ):
        """
        初期化

        Args:
            keywords_file: キーワードJSONファイルパス
            classifications_file: 特許分類JSONファイルパス
            patentfield_key_path: PatentField APIキーファイルパス
            google_credentials_path: Google Cloud認証情報パス（Claude API用）
            enable_claude: Claude API機能を有効にするか
        """
        # データ読み込み
        with open(keywords_file, 'r', encoding='utf-8') as f:
            self.keywords_data = json.load(f)

        with open(classifications_file, 'r', encoding='utf-8') as f:
            self.classifications_data = json.load(f)

        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        # Claude API設定
        self.enable_claude = enable_claude
        self.claude_client = None

        if enable_claude and google_credentials_path:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    google_credentials_path,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )

                self.claude_client = AnthropicVertex(
                    project_id="ttdc-in-house-dev",
                    region="us-east5",
                    credentials=credentials
                )
                print("✓ Claude API初期化完了")
            except Exception as e:
                print(f"⚠️ Claude API初期化失敗: {e}")
                print("   検索式の最適化機能は無効化されます")
                self.enable_claude = False

        # 統合データ構築
        self.integrated_data = self._integrate_data()

        # 独立請求項の構成要素を特定
        self.independent_components = self._identify_independent_components()

        # 404エラー統計（クエリサニタイゼーション用）
        self.query_error_stats = {
            '404_errors': 0,
            '404_claude_fixed': 0,
            '404_fallback_success': 0,
            '404_final_failure': 0,
            '400_errors': 0,
            'other_http_errors': 0
        }

        # クエリサニタイゼーション設定
        self.enable_claude_sanitization = enable_claude  # Claude修正を有効化
        self.max_sanitization_attempts = 2               # 最大修正試行回数
        self.enable_fallback_strategy = True             # フォールバック有効化

        print("=" * 80)
        print("構成要素ごと検索システム 初期化完了")
        print("=" * 80)
        print(f"✓ PatentField API設定読み込み完了")
        print(f"✓ 全構成要素数: {len(self.integrated_data)}")
        print(f"✓ 独立請求項構成要素数: {len(self.independent_components)}")
        print(f"✓ 独立請求項構成要素: {', '.join(self.independent_components)}")
        print(f"✓ Claude最適化機能: {'有効' if self.enable_claude else '無効'}")
        print("=" * 80)
        print()

    def _integrate_data(self) -> Dict:
        """
        キーワードと分類コードを構成要素番号で統合

        Returns:
            統合データ辞書 {
                '1a': {
                    'element_id': '1a',
                    'element_text': '...',
                    'importance': 0.95,
                    'is_independent': True,
                    'keywords': {...},
                    'classifications': {...}
                }
            }
        """
        integrated = {}

        # キーワードデータをベースに構築
        for kw_item in self.keywords_data['keywords']:
            element_id = kw_item['構成要素番号']

            integrated[element_id] = {
                'element_id': element_id,
                'element_text': kw_item['構成要素'],
                'importance': kw_item['重要度'],
                'is_independent': kw_item.get('is_independent', False),  # 独立請求項フラグ
                'keywords': {
                    'ドンピシャ': [kw['keyword'] for kw in kw_item.get('ドンピシャキーワード_日本語', [])[:10]],
                    '上位概念': [kw['keyword'] for kw in kw_item.get('上位概念キーワード_日本語', [])[:10]],
                    '下位概念': [kw['keyword'] for kw in kw_item.get('下位概念キーワード_日本語', [])[:10]]
                },
                'classifications': {}
            }

        # 分類コードを統合
        classifications = self.classifications_data.get('classifications', {})

        for element_id in integrated.keys():
            integrated[element_id]['classifications'] = {}

            for class_type in ['FI', 'Fterm', 'IPC', 'CPC']:
                if class_type in classifications:
                    integrated[element_id]['classifications'][class_type] = {
                        'ドンピシャ': [
                            item['code']
                            for item in classifications[class_type].get('ドンピシャ', [])
                        ][:15],
                        '上位概念': [
                            item['code']
                            for item in classifications[class_type].get('上位概念', [])
                        ][:10],
                        '下位概念': [
                            item['code']
                            for item in classifications[class_type].get('下位概念', [])
                        ][:5]
                    }

        return integrated

    def _identify_independent_components(self) -> List[str]:
        """
        独立請求項の構成要素を特定

        Returns:
            独立請求項の構成要素IDリスト
        """
        independent = []

        for element_id, data in self.integrated_data.items():
            # 独立請求項フラグがTrueの要素のみを含める
            if data.get('is_independent', False):
                independent.append(element_id)

        # 要素番号順にソート
        independent.sort()

        return independent

    def _validate_fi_code(self, fi_code: str) -> bool:
        """
        FI分類コードのバリデーション（強化版）

        PatentField APIで検索可能なFIコードかどうかを判定する。
        - 空文字列は無効
        - 空白を含むコードは無効（例: "H02K  33/18"）
        - コロン表記(':')を含むコードは無効（例: F21Y115:30）

        Args:
            fi_code: FI分類コード

        Returns:
            True if valid, False otherwise
        """
        if not fi_code:
            return False

        # 空白を含むコードは無効（修正: 新規追加）
        if ' ' in fi_code:
            return False

        # コロン表記を含むコードは無効（F21Yインデキシングコードなど）
        if ':' in fi_code:
            return False

        return True

    def _build_fi_only_query(self, element_id: str, concept_level: str = 'ドンピシャ') -> str:
        """
        FI分類コードのみのOR検索式を構築

        Args:
            element_id: 構成要素番号
            concept_level: 'ドンピシャ' | '上位概念' | '下位概念'

        Returns:
            検索式（例：'FI:H01L27/108 OR FI:H01L29/786'）
        """
        element = self.integrated_data.get(element_id, {})
        classifications = element.get('classifications', {})

        fi_codes = classifications.get('FI', {}).get(concept_level, [])

        if not fi_codes:
            return ""

        # FI分類コードを正規化（空白除去）+ バリデーション
        valid_fi_codes = []
        for code in fi_codes:
            # 空白を除去して正規化
            normalized = code.replace(' ', '')
            # バリデーション
            if self._validate_fi_code(normalized):
                valid_fi_codes.append(normalized)

        if not valid_fi_codes:
            return ""

        # FI分類のOR結合
        query_parts = [f'FI:{code}' for code in valid_fi_codes[:10]]

        return ' OR '.join(query_parts)

    def _build_fi_and_keywords_query(
        self,
        element_id: str,
        fi_concept_level: str = 'ドンピシャ',
        keyword_concept_level: str = 'ドンピシャ'
    ) -> str:
        """
        FI分類 AND キーワードの検索式を構築

        Args:
            element_id: 構成要素番号
            fi_concept_level: FI分類の概念レベル
            keyword_concept_level: キーワードの概念レベル

        Returns:
            検索式（例：'(FI:H01L27/108 OR FI:H01L29/786) AND (半導体 OR トランジスタ)'）
        """
        element = self.integrated_data.get(element_id, {})
        classifications = element.get('classifications', {})
        keywords = element.get('keywords', {})

        # FI分類（正規化 + バリデーション適用）
        fi_codes = classifications.get('FI', {}).get(fi_concept_level, [])
        valid_fi_codes = []
        for code in fi_codes:
            normalized = code.replace(' ', '')
            if self._validate_fi_code(normalized):
                valid_fi_codes.append(normalized)
        fi_query_parts = [f'FI:{code}' for code in valid_fi_codes[:10]]

        # キーワード
        kws = keywords.get(keyword_concept_level, [])

        if not fi_query_parts or not kws:
            # どちらかが空の場合は片方のみ返す
            if fi_query_parts:
                return ' OR '.join(fi_query_parts)
            elif kws:
                return ' OR '.join(kws[:5])
            else:
                return ""

        fi_query = '(' + ' OR '.join(fi_query_parts) + ')'
        keyword_query = '(' + ' OR '.join(kws[:5]) + ')'

        return f"{fi_query} AND {keyword_query}"

    def _execute_patentfield_search(
        self,
        query: str,
        limit: int = 300
    ) -> Tuple[int, List[str]]:
        """
        PatentField APIで検索実行

        Args:
            query: 検索式
            limit: 最大取得件数

        Returns:
            (ヒット件数, 特許番号リスト)
        """
        if not query:
            return 0, []

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        payload = {
            "search_type": "expert",
            "q": query,
            "columns": ["pub_id"],
            "limit": limit,
            "sort_keys": ["-_score"],  # スコア降順（関連度が高い順）
            "score_type": "tfidf"       # TF-IDFスコアリング（デフォルトだが明示）
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
            n_hits = data.get('n_hits', 0)

            patent_ids = [
                record.get('app_doc_id', record.get('pub_id'))
                for record in data.get('records', [])
            ]

            return n_hits, patent_ids

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e.response, 'status_code') else None

            if status_code == 404:
                # 404エラー: クエリ構文エラーの可能性
                self.query_error_stats['404_errors'] += 1
                print(f"    ✗ 404エラー: クエリ構文エラーの可能性")
                print(f"       クエリ: {query[:200]}...")
                return self._handle_query_syntax_error(query, str(e))

            elif status_code == 400:
                # 400エラー: リクエストパラメータエラー
                self.query_error_stats['400_errors'] += 1
                print(f"    ✗ 400エラー: リクエストパラメータエラー")
                print(f"       詳細: {e}")
                return 0, []

            else:
                # その他のHTTPエラー
                self.query_error_stats['other_http_errors'] += 1
                print(f"    ✗ HTTPエラー ({status_code}): {e}")
                return 0, []

        except Exception as e:
            print(f"    ✗ エラー: {e}")
            return 0, []

    def _fetch_top_results(
        self,
        query: str,
        limit: int = 100,
        columns: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        検索式でTop N件の特許データを取得

        Args:
            query: 検索式
            limit: 最大取得件数（デフォルト100、最大1000）
            columns: 取得するカラム（デフォルト: abstract, claims）

        Returns:
            特許データリスト [{'pub_id': '...', 'abstract': '...', 'claims': '...'}, ...]
        """
        if not query:
            return []

        if columns is None:
            # abstractとclaimsを取得（両方とも10240文字まで制限あり）
            columns = ["pub_id", "abstract", "app_claims"]

        # limitの上限チェック（最大1000件）
        limit = min(limit, 1000)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        payload = {
            "search_type": "expert",
            "q": query,
            "columns": columns,
            "limit": limit
        }

        try:
            response = requests.post(
                self.pf_endpoint,
                headers=headers,
                json=payload,
                timeout=120  # Top 100取得は時間がかかる可能性があるため120秒
            )
            response.raise_for_status()

            data = response.json()
            records = data.get('records', [])

            # pub_id, abstract, claimsを含むレコードを返す
            results = []
            for record in records:
                results.append({
                    'pub_id': record.get('app_doc_id', record.get('pub_id', '')),
                    'abstract': record.get('abstract', ''),
                    'claims': record.get('app_claims', record.get('grant_claims', ''))
                })

            return results

        except requests.exceptions.HTTPError as e:
            print(f"    ✗ Top結果取得HTTPエラー: {e}")
            return []
        except requests.exceptions.Timeout:
            print(f"    ✗ Top結果取得タイムアウト（120秒超過）")
            return []
        except Exception as e:
            print(f"    ✗ Top結果取得エラー: {e}")
            return []

    def _generate_refinement_prompt(
        self,
        current_query: str,
        top_results: List[Dict],
        element_text: str,
        current_hits: int
    ) -> str:
        """
        検索式絞り込み用のClaudeプロンプト生成

        Args:
            current_query: 現在の検索式
            top_results: Top 100件の特許データ
            element_text: 構成要素のテキスト
            current_hits: 現在のヒット件数

        Returns:
            Claudeへのプロンプト文字列
        """
        # Top 100のabstractとclaimsを整形
        top_data_summary = []
        for i, result in enumerate(top_results[:20], 1):  # 最初の20件のみ表示（トークン節約）
            abstract = result.get('abstract', '')[:500]  # 500文字まで
            claims = result.get('claims', '')[:500]
            top_data_summary.append(
                f"[{i}] {result.get('pub_id', 'N/A')}\n"
                f"要約: {abstract}\n"
                f"請求項: {claims}\n"
            )

        top_data_text = "\n".join(top_data_summary)

        prompt = f"""# タスク: PatentField検索式の絞り込み最適化

## 現在の状況
- 構成要素: {element_text}
- 現在の検索式: `{current_query}`
- ヒット件数: **{current_hits}件** (目標: 50-300件)
- 問題: ヒット件数が多すぎるため、絞り込みが必要

## 検索結果のTop 20件サンプル
{top_data_text}

## 目標
検索結果を50-300件の範囲に絞り込むための最適化された検索式を生成してください。

## PatentField検索式の構文ルール（重要！）
**CRITICAL**: 以下の構文ルールを厳守してください。これらに違反すると検索エラーが発生します。

1. **AND演算子**: `+` 記号のみ使用（`AND` キーワードは使用不可）
   - 正しい例: `(FI:H01L27/108 OR FI:H01L29/786) + トランジスタ`
   - 誤った例: `(FI:H01L27/108 OR FI:H01L29/786) AND トランジスタ`

2. **OR演算子**: `OR` キーワードを使用
   - 正しい例: `FI:H01L27/108 OR FI:H01L29/786`

3. **NOT演算子**: `-` 記号を使用
   - 正しい例: `トランジスタ + -有機EL`

4. **近傍検索**: `*N数値"単語1 単語2"` 形式
   - 正しい例: `*N3"半導体 製造"`

5. **グルーピング**: `(`, `)` を使用

6. **フィールド指定**:
   - 分類コード用: `FI:`, `IPC:`, `CPC:`, `Fterm:`
   - **キーワードには絶対にフィールドプレフィックスを付けない**（全文検索）
   - 正しい例: `FI:H01L27/108 + トランジスタ`
   - 誤った例: `FI:H01L27/108 + CL:トランジスタ` ← CL:は禁止
   - 誤った例: `FI:H01L27/108 + (電極/CL)` ← /CLは禁止

## 絞り込み戦略
1. Top 20件のサンプルを分析し、関連性の高い特許に共通するキーワードを特定
2. `+` 演算子でキーワードを追加して絞り込む（`AND`は使用しない）
3. `-` 演算子で明らかに無関係な特許を除外
4. NEAR演算子 `*N3"..."` で複数キーワードの近接性を要求

## 化学の発明の場合
1.Fタームを優先的に利用
2.下記戦略に従う
名称の展開（キーワード）
IUPAC名・慣用名: 正式名称だけでなく、現場で使われる通称も含めます。
例：2-プロパノン OR アセトン OR ジメチルケトン
英語略語: 化学物質はアルファベットの略語で書かれることが多いです。
例：ポリ乳酸 OR PLA OR Polylactic acid
異表記の考慮: 日本語特有の表記揺れをカバーします。
例：ビニル OR ビニール、メチル OR メチール（※近年の検索システムは自動補正するものも多いですが、化学物質の一部となると補正が効かないことがあります）
特許分類（FI・Fターム）の活用（最重要）
日本では**Fターム（特にテーマコード4系）**が化学検索の生命線です。
物質名キーワードで拾えない「構造の特徴（例：水酸基を2つ以上持つ）」や「骨格」をFタームで指定します。
実践テクニック: キーワードで検索漏れそうな「誘導体」や「塩」を含みたい場合は、Fタームの「骨格コード」を使います。
検索式の基本構造：[構造] × [物性] × [機能] × [用途]
A. 化学物質（Composition/Compound）の検索
化学物質は表記揺れが最も激しい要素です。
名称のバリエーション（ORで全結合）
基本名: エタノール、ethanol
構造的名称: エチルアルコール、ヒドロキシエタン
化学式表記: C2H5OH（ノイズが多いので注意）、EtOH
英語・日本語: 化学系は英語文献（WOなど）も重要なので、同義語辞書を用いて英語キーワードも必ず含める。
物質の「部分構造」や「誘導体」への対応
「アルキル基」などを「R」と表現するマーカッシュ構造が含まれる場合、テキスト検索では限界があります。
実践: キーワードで「誘導体」「derivat?」を使うか、FI・Fターム（日本）やCPC（欧米）の構造分類を使います。
（例: 日本のFターム「4J002」などはポリマーの配合成分検索に極めて強力です）
B. 数値・パラメータ（Physical Properties）の検索
「粘度が100〜200 mPa・s」のような数値限定発明の場合。
テキスト検索の限界と工夫
テキストで 100 や 200 を検索するとノイズが膨大になります。
実践: 近傍演算子（NEAR, ADJ）を使います。
例: (粘度 OR viscosity) near/5 (100 OR 150 OR 200) ※データベースの仕様による
数値限定Fタームの活用
日本の特許検索では、数値範囲ごとにFタームが割り振られている場合があります（例：膜厚、温度、分子量など）。これを使うのが最も効率的です。
C. 用途・効果（Use/Effect）の検索
「接着剤」「洗浄剤」などの用途や、「耐熱性」「透明性」などの効果。
「〜性」「〜剤」の網羅
実践: 前方一致・後方一致（トランケーション）を多用します。
例: 洗浄? (洗浄剤、洗浄液、洗浄組成物、洗浄方法...)
例: ?耐熱? (高耐熱性、耐熱向上...)
機能的表現への言い換え
「接着剤」を探す場合、「結合」「接合」「バインダー」「粘着」などもORで含める必要があります。

## 出力形式
JSON形式で以下を出力してください:

```json
{{
  "refined_query": "最適化された検索式（PatentField API互換）",
  "reasoning": "絞り込みロジックの説明（簡潔に）"
}}
```

**重要**: 検索式は必ずPatentField APIで実行可能な構文に従ってください。特に `+` 演算子の使用とキーワードのフィールドプレフィックス禁止に注意してください。"""

        return prompt

    def _generate_expansion_prompt(
        self,
        current_keywords: List[str],
        element_text: str,
        current_hits: int
    ) -> str:
        """
        キーワード拡張用のClaudeプロンプト生成

        Args:
            current_keywords: 現在のドンピシャキーワードリスト
            element_text: 構成要素のテキスト
            current_hits: 現在のヒット件数

        Returns:
            Claudeへのプロンプト文字列
        """
        keywords_text = "\n".join([f"- {kw}" for kw in current_keywords])

        prompt = f"""# タスク: 特許検索用キーワードの拡張

## 現在の状況
- 構成要素: {element_text}
- 現在のドンピシャキーワード:
{keywords_text}
- ヒット件数: **{current_hits}件** (目標: 50-300件)
- 問題: ヒット件数が少なすぎるため、検索範囲の拡大が必要

## 目標
検索範囲を拡大しつつ、構成要素の本質的な概念との関連性を維持するための拡張キーワードを生成してください。

## 拡張戦略
1. **同義語・類義語**: 現在のキーワードと同じ意味を持つ別の表現
2. **上位概念**: より広い概念のキーワード（例: "トランジスタ" → "半導体素子"）
3. **関連技術**: 同じ技術分野で使われる関連用語
4. **英語カタカナ表記**: 技術用語の別表記（例: "センサ" ⇔ "センサー"）

## 制約
- 拡張しすぎて無関係な特許が含まれないように注意
- 元のキーワードの概念から大きく逸脱しない
- 生成するキーワード数: 5-10個

## 出力形式
JSON形式で以下を出力してください:

```json
{{
  "expanded_keywords": ["拡張キーワード1", "拡張キーワード2", ...],
  "reasoning": "拡張ロジックの説明（簡潔に）"
}}
```

**重要**: 拡張キーワードは日本語の特許検索に適した用語を選んでください。"""

        return prompt

    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=False
    )
    def _call_claude_for_refinement(
        self,
        prompt: str
    ) -> Optional[Dict]:
        """
        Claude Sonnet 4.5で検索式の絞り込み

        Args:
            prompt: Claudeへのプロンプト

        Returns:
            {'refined_query': '...', 'reasoning': '...'}
            失敗時はNone
        """
        if not self.enable_claude or not self.claude_client:
            print("    ⚠️ Claude API未初期化のため絞り込みスキップ")
            return None

        try:
            print("    ⏳ Claude APIで検索式絞り込み中...")

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5@20250929",
                max_tokens=2048,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # レスポンス解析
            content = response.content[0].text

            # JSON抽出（```json ... ```の中身を抽出）
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content and "}" in content:
                # 直接JSONが含まれている場合
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                print(f"    ✗ Claude応答にJSONが含まれていません")
                return None

            result = json.loads(json_str)

            if 'refined_query' in result:
                print(f"    ✓ 絞り込み検索式生成成功")
                return result
            else:
                print(f"    ✗ 'refined_query'キーがレスポンスに含まれていません")
                return None

        except json.JSONDecodeError as e:
            print(f"    ✗ Claude応答のJSON解析失敗: {e}")
            return None
        except Exception as e:
            print(f"    ✗ Claude API呼び出しエラー: {e}")
            return None

    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=False
    )
    def _call_claude_for_expansion(
        self,
        prompt: str
    ) -> Optional[Dict]:
        """
        Claude Sonnet 4.5でキーワード拡張

        Args:
            prompt: Claudeへのプロンプト

        Returns:
            {'expanded_keywords': [...], 'reasoning': '...'}
            失敗時はNone
        """
        if not self.enable_claude or not self.claude_client:
            print("    ⚠️ Claude API未初期化のため拡張スキップ")
            return None

        try:
            print("    ⏳ Claude APIでキーワード拡張中...")

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5@20250929",
                max_tokens=1024,
                temperature=0.3,  # 拡張は少し創造性を持たせる
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # レスポンス解析
            content = response.content[0].text

            # JSON抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                print(f"    ✗ Claude応答にJSONが含まれていません")
                return None

            result = json.loads(json_str)

            if 'expanded_keywords' in result and isinstance(result['expanded_keywords'], list):
                print(f"    ✓ 拡張キーワード生成成功: {len(result['expanded_keywords'])}個")
                return result
            else:
                print(f"    ✗ 'expanded_keywords'キーがレスポンスに含まれていません")
                return None

        except json.JSONDecodeError as e:
            print(f"    ✗ Claude応答のJSON解析失敗: {e}")
            return None
        except Exception as e:
            print(f"    ✗ Claude API呼び出しエラー: {e}")
            return None

    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=False
    )
    def _call_claude_for_full_regeneration(
        self,
        element_id: str,
        element_text: str,
        current_hits: int,
        top_results: List[Dict],
        previous_query: str,
        iteration: int,
        target_min: int = 50,
        target_max: int = 300
    ) -> Optional[Dict]:
        """
        Claude Sonnet 4.5で検索式を全面的に再生成（反復最適化用）

        Args:
            element_id: 構成要素ID
            element_text: 構成要素テキスト
            current_hits: 現在のヒット件数
            top_results: Top 100件の検索結果
            previous_query: 前回の検索式
            iteration: 反復回数（1-5）
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数

        Returns:
            {'regenerated_query': '...', 'reasoning': '...'}
            失敗時はNone
        """
        if not self.enable_claude or not self.claude_client:
            print("    ⚠️ Claude API未初期化のため再生成スキップ")
            return None

        try:
            print(f"    ⏳ Claude APIで検索式全面再生成中（反復{iteration}/5）...")

            # 構成要素のキーワードと分類コードを取得
            element = self.integrated_data.get(element_id, {})
            keywords_json = element.get('keywords', {})
            classifications_json = element.get('classifications', {})

            # Top結果のサンプル（最大20件）
            sample_results = []
            for i, result in enumerate(top_results[:20], 1):
                pub_id = result.get('pub_id', 'N/A')
                abstract = result.get('abstract', '')[:200]
                claims = result.get('claims', '')[:200]
                sample_results.append(f"[{i}] {pub_id}\n  要約: {abstract}...\n  請求項: {claims}...")

            samples_text = '\n'.join(sample_results)

            # Claudeプロンプト生成
            prompt = f"""# タスク: PatentField検索式の全面的再生成（反復最適化）

## 現在の状況
- **構成要素**: {element_text}
- **現在のヒット件数**: {current_hits}件
- **目標範囲**: {target_min}-{target_max}件
- **前回の検索式**: {previous_query}
- **反復回数**: {iteration}/5

## 構成要素のキーワード
{json.dumps(keywords_json, ensure_ascii=False, indent=2)}

## 構成要素の特許分類コード
{json.dumps(classifications_json, ensure_ascii=False, indent=2)}

## 検索結果のTop 20件サンプル
{samples_text}

## 目標
検索結果を{target_min}-{target_max}件の範囲に収める検索式を全面的に再生成してください。

## 検索式構築戦略
1. **FI/IPC/CPC分類コード**を効果的に組み合わせる
2. **キーワード**はドンピシャ/上位概念/下位概念から最適なものを選択
3. **`+` 演算子（ANDの意味）**を使用して条件を組み合わせる
4. **NEAR演算子**（*N3"単語1 単語2"）で近接性を要求
5. Top結果を分析し、関連性の高い特許に共通する特徴を抽出

## PatentField検索式の構文ルール（CRITICAL！）
**これらのルールに違反すると検索エラーが発生します。**

1. **AND演算子**: `+` 記号のみ使用（`AND` キーワードは絶対に使用不可）
   - ✅ 正しい: `(FI:H01L27/108 OR FI:H01L29/786) + トランジスタ`
   - ❌ 誤り: `(FI:H01L27/108 OR FI:H01L29/786) AND トランジスタ`

2. **OR演算子**: `OR` キーワードを使用
   - ✅ 正しい: `FI:H01L27/108 OR FI:H01L29/786`

3. **NOT演算子**: `-` 記号を使用
   - ✅ 正しい: `トランジスタ + -有機EL`

4. **フィールド指定**:
   - 分類コード用: `FI:`, `IPC:`, `CPC:`, `Fterm:`
   - **キーワードには絶対にフィールドプレフィックスを付けない**（全文検索）
   - ✅ 正しい: `FI:H01L27/108 + トランジスタ`
   - ❌ 誤り: `FI:H01L27/108 + CL:トランジスタ` (CL:禁止)
   - ❌ 誤り: `FI:H01L27/108 + (電極/CL)` (/CL禁止)

5. **括弧のネスト**: 1レベルのみ（例: `(A OR B) + C` は可）

## 出力形式
必ずJSON形式で出力してください：
```json
{{
  "regenerated_query": "再生成した検索式",
  "reasoning": "検索式の設計理由と期待される効果"
}}
```

**重要**: 必ず `+` 演算子を使用し、キーワードにフィールドプレフィックスを付けないでください。"""

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5@20250929",
                max_tokens=3072,
                temperature=0.2,  # 適度な創造性
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # レスポンス解析
            content = response.content[0].text

            # JSON抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                print(f"    ✗ Claude応答にJSONが含まれていません")
                return None

            result = json.loads(json_str)

            if 'regenerated_query' in result:
                print(f"    ✓ 検索式再生成成功（反復{iteration}）")
                return result
            else:
                print(f"    ✗ 'regenerated_query'キーがレスポンスに含まれていません")
                return None

        except json.JSONDecodeError as e:
            print(f"    ✗ Claude応答のJSON解析失敗: {e}")
            return None
        except Exception as e:
            print(f"    ✗ Claude API呼び出しエラー: {e}")
            return None

    def _select_best_attempt(
        self,
        attempts: List[Dict],
        target_min: int = 50,
        target_max: int = 300
    ) -> Dict:
        """
        複数の試行結果から最良の結果を選択

        選択基準:
        1. 目標範囲内（50-300件）の試行があれば、その中で最もヒット数が多いもの
        2. 目標範囲内がなければ、目標範囲に最も近いもの（距離で計算、0件は除外）
        3. 全て0件の場合、そのまま0件を返す

        Args:
            attempts: 試行結果のリスト
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数

        Returns:
            選択された試行結果
        """
        if not attempts:
            return {
                'query': '',
                'hits': 0,
                'patent_ids': [],
                'step': 'none',
                'strategy': '試行なし'
            }

        # 目標範囲内の試行を抽出
        in_range_attempts = [
            att for att in attempts
            if target_min <= att.get('hits', 0) <= target_max
        ]

        if in_range_attempts:
            # 目標範囲内で最もヒット数が多いものを選択
            best = max(in_range_attempts, key=lambda x: x.get('hits', 0))
            print(f"    ✓ 目標範囲内の最良結果を選択: {best.get('hits', 0)}件 (Step {best.get('step', 'N/A')})")
            return best

        # 目標範囲内がなければ、0件以外で目標範囲に最も近いものを選択
        non_zero_attempts = [
            att for att in attempts
            if att.get('hits', 0) > 0
        ]

        if non_zero_attempts:
            # 目標範囲に最も近いものを選択（距離で計算）
            def distance_to_target(hits):
                """目標範囲からの距離を計算"""
                if hits < target_min:
                    return target_min - hits  # 下回る場合
                elif hits > target_max:
                    return hits - target_max  # 上回る場合
                else:
                    return 0  # 範囲内（このケースはin_range_attemptsで処理済み）

            best = min(non_zero_attempts, key=lambda x: distance_to_target(x.get('hits', 0)))
            hits = best.get('hits', 0)
            dist = distance_to_target(hits)

            print(f"    ⚠️ 目標範囲外ですが最良結果を選択: {hits}件 (Step {best.get('step', 'N/A')})")
            print(f"       目標範囲からの距離: {dist}件")
            return best

        # 全て0件の場合、最後の試行を返す
        print(f"    ⚠️ 全て0件のため最後の試行をそのまま返します")
        return attempts[-1]

    def _validate_and_fix_query(
        self,
        query: str
    ) -> Tuple[str, List[str]]:
        """
        PatentField検索式のバリデーションと自動修復

        修正項目:
        1. AND演算子: 'AND' → '+' に変換
        2. キーワードのフィールドプレフィックス除去: 'CL:keyword', 'AB:keyword' → 'keyword'
        3. 不正な構文削除: '/CL', '/AB', '/TI' など
        4. 括弧のバランス修正（可能な場合）
        5. 過度な空白の削除

        Args:
            query: 検索式

        Returns:
            (fixed_query, warning_messages)
        """
        import re

        if not query or not query.strip():
            return "", ["検索式が空です"]

        fixed = query
        warnings = []

        # 1. AND演算子を + に変換（括弧外のみ、フィールドプレフィックス後は除外）
        # "FI:xxx AND FI:yyy" → "FI:xxx + FI:yyy"
        # 単語境界を使用して、ANDキーワードのみを変換
        fixed = re.sub(r'\s+AND\s+', ' + ', fixed)
        if 'AND' in query and '+' in fixed:
            warnings.append("AND演算子を + に変換しました")

        # 2. キーワード用フィールドプレフィックスの除去
        # パターン: (CL:|AB:|TI:|DE:)の後に続くキーワードからプレフィックスを除去
        # ただし、FI:, IPC:, CPC:, Fterm: は保持

        # 2-1. 不正な構文 "/CL", "/AB", "/TI" などを削除
        invalid_patterns = ['/CL', '/AB', '/TI', '/DE', '/PN']
        for pattern in invalid_patterns:
            if pattern in fixed:
                fixed = fixed.replace(pattern, '')
                warnings.append(f"不正な構文 '{pattern}' を削除しました")

        # 2-2. キーワード用プレフィックス（CL:, AB:, TI:, DE:）を除去
        # パターン: (CL:|AB:|TI:|DE:)(\w+) → $2
        # ただし、括弧内でOR/ANDと組み合わせている場合も処理
        keyword_prefixes = ['CL:', 'AB:', 'TI:', 'DE:']
        for prefix in keyword_prefixes:
            if prefix in fixed:
                # プレフィックスを除去（単語の前にあるもののみ）
                fixed = re.sub(rf'\b{re.escape(prefix)}(\S+)', r'\1', fixed)
                warnings.append(f"キーワードの '{prefix}' プレフィックスを除去しました（全文検索化）")

        # 3. 括弧のバランスチェックと修正
        open_count = fixed.count('(')
        close_count = fixed.count(')')

        if open_count > close_count:
            # 不足分の閉じ括弧を末尾に追加
            fixed += ')' * (open_count - close_count)
            warnings.append(f"不足していた閉じ括弧 {open_count - close_count}個を追加しました")
        elif close_count > open_count:
            # 過剰な閉じ括弧を削除（末尾から）
            excess = close_count - open_count
            for _ in range(excess):
                # 最後の閉じ括弧を削除
                last_close = fixed.rfind(')')
                if last_close != -1:
                    fixed = fixed[:last_close] + fixed[last_close+1:]
            warnings.append(f"過剰な閉じ括弧 {excess}個を削除しました")

        # 4. 過度な空白の削除
        fixed = re.sub(r'\s+', ' ', fixed).strip()

        # 5. 空の括弧ペアを削除: "()" → ""
        while '()' in fixed:
            fixed = fixed.replace('()', '')
            if not warnings or warnings[-1] != "空の括弧ペアを削除しました":
                warnings.append("空の括弧ペアを削除しました")

        # 6. 長さチェック
        if len(fixed) > 10000:
            warnings.append("警告: 検索式が非常に長い（10000文字以上）")

        # 7. 最終的に空になった場合
        if not fixed.strip():
            return "", warnings + ["修正後の検索式が空になりました"]

        return fixed, warnings

    def _handle_query_syntax_error(
        self,
        query: str,
        error_message: str
    ) -> Tuple[int, List[str]]:
        """
        404エラー（クエリ構文エラー）のハンドリング

        戦略:
        1. Claude APIで検索式を修正（enable_claude_sanitization=Trueの場合）
        2. フォールバック: 簡略化戦略
        3. 最終手段: 最小限の検索式

        Args:
            query: 元の検索式
            error_message: エラーメッセージ

        Returns:
            (ヒット件数, 特許番号リスト)
        """
        print(f"    [404エラーハンドリング] 検索式修正を試行...")

        # Strategy 1: Claude APIによる修正
        if self.enable_claude_sanitization and self.claude_client:
            for attempt in range(1, self.max_sanitization_attempts + 1):
                print(f"    試行 {attempt}/{self.max_sanitization_attempts}: Claude APIで修正")

                sanitized_query = self._sanitize_query_with_claude(
                    query,
                    error_message,
                    attempt
                )

                if sanitized_query and sanitized_query != query:
                    print(f"       修正されたクエリ: {sanitized_query[:200]}...")

                    # 修正されたクエリで再検索
                    try:
                        hits, patent_ids = self._execute_patentfield_search_direct(sanitized_query)
                        if hits > 0:
                            self.query_error_stats['404_claude_fixed'] += 1
                            print(f"       ✓ Claude修正成功: {hits}件")
                            return hits, patent_ids
                        else:
                            print(f"       ✗ 修正後も0件")
                    except Exception as e:
                        print(f"       ✗ 修正後の検索でエラー: {e}")
                        continue
                else:
                    print(f"       ✗ Claude修正失敗または変更なし")
                    break

        # Strategy 2: フォールバック戦略
        if self.enable_fallback_strategy:
            print(f"    フォールバック戦略: 検索式の簡略化")
            fallback_query = self._simplify_query_fallback(query)

            if fallback_query and fallback_query != query:
                print(f"       簡略化クエリ: {fallback_query[:200]}...")

                try:
                    hits, patent_ids = self._execute_patentfield_search_direct(fallback_query)
                    if hits > 0:
                        self.query_error_stats['404_fallback_success'] += 1
                        print(f"       ✓ フォールバック成功: {hits}件")
                        return hits, patent_ids
                except Exception as e:
                    print(f"       ✗ フォールバック検索でエラー: {e}")

        # Strategy 3: 最終失敗
        self.query_error_stats['404_final_failure'] += 1
        print(f"    ✗ 全ての修正戦略が失敗")
        return 0, []

    def _execute_patentfield_search_direct(
        self,
        query: str,
        limit: int = 300
    ) -> Tuple[int, List[str]]:
        """
        PatentField API直接検索（404エラーハンドリングなし）

        _execute_patentfield_search との違い:
        - 404エラー時に_handle_query_syntax_errorを呼ばない（無限ループ防止）
        - 例外を上位に伝播

        Args:
            query: 検索式
            limit: 最大取得件数

        Returns:
            (ヒット件数, 特許番号リスト)

        Raises:
            requests.exceptions.HTTPError: HTTPエラー時
        """
        if not query:
            return 0, []

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        payload = {
            "search_type": "expert",
            "q": query,
            "columns": ["pub_id"],
            "limit": limit,
            "sort_keys": ["-_score"],
            "score_type": "tfidf"
        }

        response = requests.post(
            self.pf_endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()
        n_hits = data.get('n_hits', 0)

        patent_ids = [
            record.get('app_doc_id', record.get('pub_id'))
            for record in data.get('records', [])
        ]

        return n_hits, patent_ids

    def _sanitize_query_with_claude(
        self,
        original_query: str,
        error_message: str,
        attempt: int = 1
    ) -> Optional[str]:
        """
        Claude APIを使用して検索式を修正

        Args:
            original_query: 元の検索式
            error_message: エラーメッセージ
            attempt: 試行回数

        Returns:
            修正された検索式（またはNone）
        """
        if not self.claude_client:
            return None

        try:
            prompt = self._generate_sanitization_prompt(original_query, error_message, attempt)

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5@20250929",
                max_tokens=2000,
                temperature=0.0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text.strip()

            # JSON応答をパース
            import json
            import re

            # JSONブロックを抽出（```json ... ``` または { ... }）
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)

            if json_match:
                result = json.loads(json_match.group(1))
                corrected_query = result.get('corrected_query', '')
                reason = result.get('reason', '')

                if corrected_query:
                    print(f"       Claude修正理由: {reason[:100]}...")
                    return corrected_query

        except Exception as e:
            print(f"       ✗ Claude API呼び出しエラー: {e}")

        return None

    def _generate_sanitization_prompt(
        self,
        query: str,
        error_message: str,
        attempt: int
    ) -> str:
        """
        クエリサニタイゼーション用のClaudeプロンプトを生成

        Args:
            query: 元の検索式
            error_message: エラーメッセージ
            attempt: 試行回数

        Returns:
            Claudeプロンプト
        """
        return f"""あなたはPatentField API検索式の専門家です。
以下の検索式で404エラーが発生しました。

元の検索式:
{query}

エラー情報:
{error_message}

試行回数: {attempt}/{self.max_sanitization_attempts}

PatentField API Expert検索の構文ルール:
1. **フィールド指定**: FI:, IPC:, CPC:, Fterm: のみ有効
2. **キーワード検索**: CL:, AB:, TI:, DE: は使用不可（全文検索として指定）
3. **演算子**:
   - AND: + 記号を使用
   - OR: OR キーワード
   - NOT: - 記号を使用
   - NEAR: *N[数字]"単語1 単語2" 形式
4. **括弧**: 必ずバランスを取る（開き括弧と閉じ括弧の数が一致）
5. **特殊文字**: 適切にエスケープまたは削除
6. **不正な構文**: /CL, /AB, /TI などは削除

タスク:
上記のルールに従って、検索式を修正してください。
できる限り元の検索意図を保ちつつ、PatentField APIで実行可能な形式に変換してください。

出力形式（JSONのみ、説明文不要）:
{{
  "corrected_query": "修正された検索式",
  "reason": "修正理由（簡潔に）"
}}"""

    def _simplify_query_fallback(
        self,
        query: str
    ) -> str:
        """
        検索式の簡略化フォールバック戦略

        戦略:
        1. AND条件を削除してOR条件のみに
        2. FI:コードのみを抽出
        3. 最小限の検索式

        Args:
            query: 元の検索式

        Returns:
            簡略化された検索式
        """
        import re

        # Strategy 1: AND条件を削除
        # "FI:xxx + FI:yyy" → "FI:xxx OR FI:yyy"
        simplified = re.sub(r'\s*\+\s*', ' OR ', query)
        simplified = re.sub(r'\s+AND\s+', ' OR ', simplified, flags=re.IGNORECASE)

        # Strategy 2: FI:コードのみを抽出
        fi_codes = re.findall(r'FI:[A-Z0-9/*]+', query)
        if fi_codes:
            # FI:コードをOR条件で結合
            simplified = ' OR '.join(fi_codes[:10])  # 最大10個まで

        # 括弧を削除して単純化
        simplified = simplified.replace('(', '').replace(')', '')

        # 過度な空白を削除
        simplified = re.sub(r'\s+', ' ', simplified).strip()

        return simplified

    def _execute_with_retry(
        self,
        func: callable,
        max_retries: int = 3,
        delay: float = 2.0,
        context: str = ""
    ):
        """
        Broken pipeエラー時の自動リトライ

        Args:
            func: 実行する関数
            max_retries: 最大リトライ回数
            delay: リトライ間隔（秒）
            context: エラーログ用のコンテキスト情報

        Returns:
            func()の戻り値

        Raises:
            最終的に失敗した場合の例外
        """
        import time
        import traceback

        for attempt in range(max_retries):
            try:
                return func()
            except (BrokenPipeError, OSError, ConnectionError) as e:
                error_type = type(e).__name__
                error_msg = str(e)

                if attempt < max_retries - 1:
                    print(f"    ⚠️ {error_type}エラー発生: {error_msg}")
                    if context:
                        print(f"       コンテキスト: {context}")
                    print(f"       {delay}秒後に再試行します ({attempt+1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    print(f"    ❌ {error_type}エラー: 最大リトライ回数({max_retries})に達しました")
                    print(f"       エラー詳細: {error_msg}")
                    if context:
                        print(f"       コンテキスト: {context}")
                    print("       スタックトレース:")
                    traceback.print_exc()
                    raise
            except Exception as e:
                # その他の予期しない例外
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"    ❌ 予期しないエラー ({error_type}): {error_msg}")
                if context:
                    print(f"       コンテキスト: {context}")
                print("       スタックトレース:")
                traceback.print_exc()
                raise

    def _validate_patentfield_syntax(
        self,
        query: str
    ) -> Tuple[bool, str]:
        """
        PatentField検索式の簡易構文検証

        チェック項目:
        - 空文字列でないこと
        - 括弧のバランス
        - 基本的な妥当性確認

        Args:
            query: 検索式

        Returns:
            (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "検索式が空です"

        # 括弧のバランスチェック
        open_paren = query.count('(')
        close_paren = query.count(')')

        if open_paren != close_paren:
            return False, f"括弧のバランスが不正です（'(' {open_paren}個, ')' {close_paren}個）"

        # 基本的な妥当性チェック
        if len(query) > 10000:
            return False, "検索式が長すぎます（10000文字以上）"

        return True, ""

    def search_single_component_adaptive(
        self,
        element_id: str,
        target_min_initial: int = 10,
        target_min_claude: int = 50,
        target_max: int = 300
    ) -> Dict:
        """
        単一構成要素の適応的検索（Claude統合版）

        新しい検索ロジック（2段階目標件数対応）：
        1. ドンピシャFIのみで検索
        2. if 10 < hits < 300: 完了（Claude利用前の目標）
        3. else if hits > 300:
           3-1. ドンピシャFI AND ドンピシャキーワード
           3-2. if still > 300 or < 50: Claudeで絞り込み（AND/NOT/NEAR使用）
                                      → Claude利用時は50-300件を目標
        4. else if hits < 10:
           4-1. ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)
           4-2. if still not 50-300: Claudeでキーワード拡張
                                    → Claude利用時は50-300件を目標

        Args:
            element_id: 構成要素番号
            target_min_initial: Claude利用前の目標最小ヒット数（デフォルト: 10）
            target_min_claude: Claude利用時の目標最小ヒット数（デフォルト: 50）
            target_max: 目標最大ヒット数（デフォルト: 300）

        Returns:
            検索結果辞書 {
                'element_id': '1a',
                'element_text': '...',
                'final_query': '...',
                'final_hits': 120,
                'patent_ids': [...],
                'attempts': [...],
                'status': 'success'
            }
        """
        element = self.integrated_data.get(element_id, {})
        element_text = element.get('element_text', '')

        print(f"\n{'='*80}")
        print(f"構成要素 {element_id}: {element_text[:60]}...")
        print(f"{'='*80}")

        attempts = []
        final_query = ""
        final_hits = 0
        final_patent_ids = []
        claude_used = False  # Claude APIを使用したかどうかのフラグ
    
        # ========================================
        # Step 1: ドンピシャFIのみで検索
        # ========================================
        print(f"\n  [Step 1] ドンピシャFIのみで検索")
        query = self._build_fi_only_query(element_id, 'ドンピシャ')
    
        if not query:
            print(f"    ✗ ドンピシャFI分類が見つかりません。スキップします。")
            return {
                'element_id': element_id,
                'element_text': element_text,
                'final_query': "",
                'final_hits': 0,
                'patent_ids': [],
                'attempts': [],
                'status': 'no_fi_codes'
            }
    
        print(f"    検索式: {query[:200]}...")
        hits, patent_ids = self._execute_patentfield_search(query)
        print(f"    ヒット件数: {hits}件")
    
        attempts.append({
            'step': '1',
            'strategy': 'ドンピシャFIのみ',
            'query': query,
            'hits': hits
        })
    
        final_query = query
        final_hits = hits
        final_patent_ids = patent_ids

        # 目標範囲内なら完了（Claude利用前の判定: 10-300件）
        if target_min_initial <= hits <= target_max:
            print(f"    ✓ 目標範囲内（{target_min_initial}-{target_max}件）到達！【Claude利用前】")
            return {
                'element_id': element_id,
                'element_text': element_text,
                'final_query': final_query,
                'final_hits': final_hits,
                'patent_ids': final_patent_ids,
                'attempts': attempts,
                'status': 'success'
            }

        # ========================================
        # Branch A: hits > 300 の場合（絞り込み）
        # ========================================
        if hits > target_max:
            print(f"\n  [Branch A] ヒット件数が多すぎるため絞り込み")
    
            # A-1: ドンピシャFI AND ドンピシャキーワード
            print(f"\n  [A-1] ドンピシャFI AND ドンピシャキーワード")
            query = self._build_fi_and_keywords_query(
                element_id,
                fi_concept_level='ドンピシャ',
                keyword_concept_level='ドンピシャ'
            )
    
            if query:
                print(f"    検索式: {query[:200]}...")
                hits, patent_ids = self._execute_patentfield_search(query)
                print(f"    ヒット件数: {hits}件")
    
                attempts.append({
                    'step': 'A-1',
                    'strategy': 'ドンピシャFI AND ドンピシャキーワード',
                    'query': query,
                    'hits': hits
                })
    
                final_query = query
                final_hits = hits
                final_patent_ids = patent_ids

                # 目標範囲内なら完了（Claude利用前の判定: 10-300件）
                if target_min_initial <= hits <= target_max:
                    print(f"    ✓ 目標範囲内（{target_min_initial}-{target_max}件）到達！【Claude利用前】")
                    return {
                        'element_id': element_id,
                        'element_text': element_text,
                        'final_query': final_query,
                        'final_hits': final_hits,
                        'patent_ids': final_patent_ids,
                        'attempts': attempts,
                        'status': 'success'
                    }

            # A-2: まだ範囲外ならClaude最適化（Claude利用時は50-300件を目標）
            if hits > target_max or hits < target_min_claude:
                print(f"\n  [A-2] Claude APIで検索式絞り込み")
                claude_used = True  # Claudeを使用

                # Top 100取得
                top_results = self._fetch_top_results(query, limit=100)
    
                if top_results:
                    print(f"    ✓ Top {len(top_results)}件取得成功")
    
                    # Claudeプロンプト生成
                    prompt = self._generate_refinement_prompt(
                        current_query=query,
                        top_results=top_results,
                        element_text=element_text,
                        current_hits=hits
                    )
    
                    # Claude呼び出し
                    claude_result = self._call_claude_for_refinement(prompt)
    
                    if claude_result and 'refined_query' in claude_result:
                        refined_query = claude_result['refined_query']
                        reasoning = claude_result.get('reasoning', '')

                        print(f"    ✓ Claude生成検索式: {refined_query[:150]}...")
                        print(f"    理由: {reasoning[:100]}...")

                        # 構文バリデーションと自動修復
                        fixed_query, warnings = self._validate_and_fix_query(refined_query)

                        if warnings:
                            print(f"    ⚠️ クエリ自動修復:")
                            for warning in warnings:
                                print(f"       - {warning}")
                            if fixed_query != refined_query:
                                print(f"    修正前: {refined_query[:100]}...")
                                print(f"    修正後: {fixed_query[:100]}...")

                        # 修復後の検索式で検索実行
                        hits, patent_ids = self._execute_patentfield_search(fixed_query)
                        print(f"    ヒット件数: {hits}件")
    
                        attempts.append({
                            'step': 'A-2',
                            'strategy': 'Claude絞り込み検索',
                            'query': refined_query,
                            'hits': hits,
                            'reasoning': reasoning
                        })
    
                        final_query = refined_query
                        final_hits = hits
                        final_patent_ids = patent_ids

                        # A-2で目標範囲達成なら終了（Claude利用時: 50-300件）
                        if target_min_claude <= hits <= target_max:
                            print(f"    ✓ 目標範囲内（{target_min_claude}-{target_max}件）到達！【Claude利用時】")
                            return {
                                'element_id': element_id,
                                'element_text': element_text,
                                'final_query': final_query,
                                'final_hits': final_hits,
                                'patent_ids': final_patent_ids,
                                'attempts': attempts,
                                'status': 'success'
                            }

            # A-3: まだ範囲外なら反復的Claude最適化（最大5回）
            if hits > target_max or hits < target_min_claude:
                print(f"\n  [A-3] Claude API反復最適化（最大5回）")
                claude_used = True  # Claudeを使用

                iteration_attempts = []  # 反復試行の記録

                for iteration in range(1, 6):
                    print(f"\n  [A-3-{iteration}] 反復{iteration}/5")

                    # Top 100取得
                    top_results = self._fetch_top_results(query, limit=100)

                    if not top_results:
                        print(f"    ✗ Top結果取得失敗、反復終了")
                        break

                    print(f"    ✓ Top {len(top_results)}件取得成功")

                    # Claude全面再生成呼び出し（Claude利用時: 50-300件目標）
                    claude_result = self._call_claude_for_full_regeneration(
                        element_id=element_id,
                        element_text=element_text,
                        current_hits=hits,
                        top_results=top_results,
                        previous_query=query,
                        iteration=iteration,
                        target_min=target_min_claude,
                        target_max=target_max
                    )

                    if claude_result and 'regenerated_query' in claude_result:
                        regenerated_query = claude_result['regenerated_query']
                        reasoning = claude_result.get('reasoning', '')

                        print(f"    ✓ Claude再生成検索式: {regenerated_query[:150]}...")
                        print(f"    理由: {reasoning[:100]}...")

                        # 構文バリデーションと自動修復
                        fixed_query, warnings = self._validate_and_fix_query(regenerated_query)

                        if warnings:
                            print(f"    ⚠️ クエリ自動修復:")
                            for warning in warnings:
                                print(f"       - {warning}")
                            if fixed_query != regenerated_query:
                                print(f"    修正前: {regenerated_query[:100]}...")
                                print(f"    修正後: {fixed_query[:100]}...")

                        # 修復後の検索式で検索実行
                        hits, patent_ids = self._execute_patentfield_search(fixed_query)
                        print(f"    ヒット件数: {hits}件")

                        # 試行を記録（修復後のクエリを保存）
                        iteration_attempt = {
                            'step': f'A-3-{iteration}',
                            'strategy': f'Claude反復最適化（{iteration}/5）',
                            'query': fixed_query,  # 修復後のクエリ
                            'original_query': regenerated_query,  # 元のクエリも記録
                            'hits': hits,
                            'reasoning': reasoning,
                            'patent_ids': patent_ids,
                            'validation_warnings': warnings  # 修復警告も記録
                        }
                        attempts.append(iteration_attempt)
                        iteration_attempts.append(iteration_attempt)

                        # 現在のクエリを更新（次の反復で使用）
                        query = fixed_query

                        # 目標範囲達成なら終了（Claude利用時: 50-300件）
                        if target_min_claude <= hits <= target_max:
                            print(f"    ✓ 目標範囲内（{target_min_claude}-{target_max}件）到達！反復終了")
                            final_query = fixed_query
                            final_hits = hits
                            final_patent_ids = patent_ids
                            break
                    else:
                        print(f"    ✗ Claude再生成失敗、反復終了")
                        break

                # 反復終了後、最良の結果を選択
                if iteration_attempts:
                    print(f"\n  [A-3] 反復結果から最良の試行を選択")
                    best_attempt = self._select_best_attempt(
                        iteration_attempts,
                        target_min_claude,
                        target_max
                    )
                    final_query = best_attempt.get('query', final_query)
                    final_hits = best_attempt.get('hits', final_hits)
                    final_patent_ids = best_attempt.get('patent_ids', final_patent_ids)

        # ========================================
        # Branch B: hits < 10 の場合（拡張）
        # ========================================
        elif hits < target_min_initial:
            print(f"\n  [Branch B] ヒット件数が少なすぎるため拡張")
    
            # B-1: ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)
            print(f"\n  [B-1] ドンピシャFI OR (上位概念FI AND ドンピシャキーワード)")
    
            # 左辺: ドンピシャFI
            left_query = self._build_fi_only_query(element_id, 'ドンピシャ')
    
            # 右辺: 上位概念FI AND ドンピシャキーワード
            right_query = self._build_fi_and_keywords_query(
                element_id,
                fi_concept_level='上位概念',
                keyword_concept_level='ドンピシャ'
            )
    
            if left_query and right_query:
                query = f"({left_query}) OR ({right_query})"
            elif left_query:
                query = left_query
            elif right_query:
                query = right_query
            else:
                query = ""
    
            if query:
                print(f"    検索式: {query[:200]}...")
                hits, patent_ids = self._execute_patentfield_search(query)
                print(f"    ヒット件数: {hits}件")
    
                attempts.append({
                    'step': 'B-1',
                    'strategy': 'ドンピシャFI OR (上位概念FI AND ドンピシャKeyword)',
                    'query': query,
                    'hits': hits
                })
    
                final_query = query
                final_hits = hits
                final_patent_ids = patent_ids

                # 目標範囲内なら完了（Claude利用前の判定: 10-300件）
                if target_min_initial <= hits <= target_max:
                    print(f"    ✓ 目標範囲内（{target_min_initial}-{target_max}件）到達！【Claude利用前】")
                    return {
                        'element_id': element_id,
                        'element_text': element_text,
                        'final_query': final_query,
                        'final_hits': final_hits,
                        'patent_ids': final_patent_ids,
                        'attempts': attempts,
                        'status': 'success'
                    }

            # B-2: まだ範囲外ならClaudeでキーワード拡張（Claude利用時は50-300件を目標）
            if hits < target_min_claude or hits > target_max:
                print(f"\n  [B-2] Claude APIでキーワード拡張")
                claude_used = True  # Claudeを使用

                # 現在のドンピシャキーワード取得
                current_keywords = element.get('keywords', {}).get('ドンピシャ', [])
    
                if current_keywords:
                    # Claudeプロンプト生成
                    prompt = self._generate_expansion_prompt(
                        current_keywords=current_keywords,
                        element_text=element_text,
                        current_hits=hits
                    )
    
                    # Claude呼び出し
                    claude_result = self._call_claude_for_expansion(prompt)
    
                    if claude_result and 'expanded_keywords' in claude_result:
                        expanded_keywords = claude_result['expanded_keywords']
                        reasoning = claude_result.get('reasoning', '')
    
                        print(f"    ✓ Claude拡張キーワード: {expanded_keywords[:5]}...")
                        print(f"    理由: {reasoning[:100]}...")
    
                        # 拡張キーワードで検索式再構築
                        # ドンピシャFI OR (上位概念FI AND 拡張キーワード)
                        fi_donpisya = self._build_fi_only_query(element_id, 'ドンピシャ')
    
                        # 上位概念FIを取得
                        upper_fi_codes = element.get('classifications', {}).get('FI', {}).get('上位概念', [])
                        valid_upper_fi = [code for code in upper_fi_codes if self._validate_fi_code(code)]
    
                        if valid_upper_fi:
                            upper_fi_query = ' OR '.join([f'FI:{code}' for code in valid_upper_fi[:10]])
                            expanded_kw_query = ' OR '.join(expanded_keywords[:5])
    
                            right_part = f"({upper_fi_query}) AND ({expanded_kw_query})"
    
                            if fi_donpisya:
                                query = f"({fi_donpisya}) OR ({right_part})"
                            else:
                                query = right_part
                        else:
                            query = fi_donpisya if fi_donpisya else ""
    
                        if query:
                            print(f"    検索式: {query[:200]}...")
                            hits, patent_ids = self._execute_patentfield_search(query)
                            print(f"    ヒット件数: {hits}件")
    
                            attempts.append({
                                'step': 'B-2',
                                'strategy': 'Claude拡張キーワード検索',
                                'query': query,
                                'hits': hits,
                                'reasoning': reasoning,
                                'expanded_keywords': expanded_keywords
                            })
    
                            final_query = query
                            final_hits = hits
                            final_patent_ids = patent_ids

            # B-3: まだ範囲外なら反復的Claude最適化（最大5回）
            if hits < target_min_claude or hits > target_max:
                print(f"\n  [B-3] Claude API反復最適化（最大5回）")
                claude_used = True  # Claudeを使用

                iteration_attempts = []  # 反復試行の記録

                for iteration in range(1, 6):
                    print(f"\n  [B-3-{iteration}] 反復{iteration}/5")

                    # Top 100取得
                    top_results = self._fetch_top_results(query, limit=100)

                    if not top_results:
                        print(f"    ✗ Top結果取得失敗、反復終了")
                        break

                    print(f"    ✓ Top {len(top_results)}件取得成功")

                    # Claude全面再生成呼び出し（Claude利用時: 50-300件目標）
                    claude_result = self._call_claude_for_full_regeneration(
                        element_id=element_id,
                        element_text=element_text,
                        current_hits=hits,
                        top_results=top_results,
                        previous_query=query,
                        iteration=iteration,
                        target_min=target_min_claude,
                        target_max=target_max
                    )

                    if claude_result and 'regenerated_query' in claude_result:
                        regenerated_query = claude_result['regenerated_query']
                        reasoning = claude_result.get('reasoning', '')

                        print(f"    ✓ Claude再生成検索式: {regenerated_query[:150]}...")
                        print(f"    理由: {reasoning[:100]}...")

                        # 構文バリデーションと自動修復
                        fixed_query, warnings = self._validate_and_fix_query(regenerated_query)

                        if warnings:
                            print(f"    ⚠️ クエリ自動修復:")
                            for warning in warnings:
                                print(f"       - {warning}")
                            if fixed_query != regenerated_query:
                                print(f"    修正前: {regenerated_query[:100]}...")
                                print(f"    修正後: {fixed_query[:100]}...")

                        # 修復後の検索式で検索実行
                        hits, patent_ids = self._execute_patentfield_search(fixed_query)
                        print(f"    ヒット件数: {hits}件")

                        # 試行を記録（修復後のクエリを保存）
                        iteration_attempt = {
                            'step': f'B-3-{iteration}',
                            'strategy': f'Claude反復最適化（{iteration}/5）',
                            'query': fixed_query,  # 修復後のクエリ
                            'original_query': regenerated_query,  # 元のクエリも記録
                            'hits': hits,
                            'reasoning': reasoning,
                            'patent_ids': patent_ids,
                            'validation_warnings': warnings  # 修復警告も記録
                        }
                        attempts.append(iteration_attempt)
                        iteration_attempts.append(iteration_attempt)

                        # 現在のクエリを更新（次の反復で使用）
                        query = fixed_query

                        # 目標範囲達成なら終了（Claude利用時: 50-300件）
                        if target_min_claude <= hits <= target_max:
                            print(f"    ✓ 目標範囲内（{target_min_claude}-{target_max}件）到達！反復終了")
                            final_query = fixed_query
                            final_hits = hits
                            final_patent_ids = patent_ids
                            break
                    else:
                        print(f"    ✗ Claude再生成失敗、反復終了")
                        break

                # 反復終了後、最良の結果を選択
                if iteration_attempts:
                    print(f"\n  [B-3] 反復結果から最良の試行を選択")
                    best_attempt = self._select_best_attempt(
                        iteration_attempts,
                        target_min_claude,
                        target_max
                    )
                    final_query = best_attempt.get('query', final_query)
                    final_hits = best_attempt.get('hits', final_hits)
                    final_patent_ids = best_attempt.get('patent_ids', final_patent_ids)

        # ========================================
        # 最終結果を返す
        # ========================================
        # 最終ステータスの判定は、Claude利用があった場合は target_min_claude、なかった場合は target_min_initial を使用
        if claude_used:
            # Claude API使用時: 50-300件を目標
            status = 'success' if target_min_claude <= final_hits <= target_max else 'out_of_range'
            target_range = f"{target_min_claude}-{target_max}件【Claude利用時】"
        else:
            # Claude API不使用時: 10-300件を目標
            status = 'success' if target_min_initial <= final_hits <= target_max else 'out_of_range'
            target_range = f"{target_min_initial}-{target_max}件【Claude利用前】"

        print(f"\n  最終結果: {final_hits}件")
        print(f"  目標範囲: {target_range}")
        print(f"  ステータス: {status}")
    
        return {
            'element_id': element_id,
            'element_text': element_text,
            'final_query': final_query,
            'final_hits': final_hits,
            'patent_ids': final_patent_ids,
            'attempts': attempts,
            'status': status
        }
    

    def search_all_components_parallel(
        self,
        component_ids: Optional[List[str]] = None,
        max_workers: int = 2  # 修正: 5 → 2 (Claude API負荷軽減)
    ) -> List[Dict]:
        """
        全構成要素を並行検索

        Args:
            component_ids: 検索対象の構成要素IDリスト（Noneなら独立請求項のみ）
            max_workers: 並行処理のワーカー数

        Returns:
            各構成要素の検索結果リスト
        """
        if component_ids is None:
            component_ids = self.independent_components

        print(f"\n{'='*80}")
        print(f"並行検索開始: {len(component_ids)}個の構成要素")
        print(f"並行ワーカー数: {max_workers}")
        print(f"{'='*80}")

        start_time = time.time()
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 全構成要素の検索タスクを投入（リトライロジック付き）
            future_to_component = {}
            for comp_id in component_ids:
                # リトライロジックを組み込んだラムダ関数
                retry_func = lambda cid=comp_id: self._execute_with_retry(
                    lambda: self.search_single_component_adaptive(cid),
                    max_retries=3,
                    delay=2.0,
                    context=f"Component {cid}"
                )
                future = executor.submit(retry_func)
                future_to_component[future] = comp_id

            # 完了したタスクから順に結果を収集
            for future in as_completed(future_to_component):
                comp_id = future_to_component[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    import traceback
                    error_type = type(e).__name__
                    error_msg = str(e)

                    print(f"\n✗ 構成要素 {comp_id} の検索でエラー ({error_type}): {error_msg}")
                    print(f"   詳細なスタックトレース:")
                    traceback.print_exc()

                    results.append({
                        'element_id': comp_id,
                        'element_text': '',
                        'final_query': '',
                        'final_hits': 0,
                        'patent_ids': [],
                        'attempts': [],
                        'status': 'error',
                        'error': f"{error_type}: {error_msg}"
                    })

        elapsed_time = time.time() - start_time

        print(f"\n{'='*80}")
        print(f"並行検索完了")
        print(f"処理時間: {elapsed_time:.2f}秒")
        print(f"{'='*80}")

        # 構成要素ID順にソート
        results.sort(key=lambda x: x['element_id'])

        return results

    def merge_and_deduplicate(self, search_results: List[Dict]) -> Dict:
        """
        検索結果を統合し、重複を削除

        Args:
            search_results: 各構成要素の検索結果リスト

        Returns:
            統合結果 {
                'total_components': 5,
                'total_unique_patents': 150,
                'merged_patent_ids': [...],
                'component_summary': [...]
            }
        """
        print(f"\n{'='*80}")
        print(f"検索結果の統合・重複削除")
        print(f"{'='*80}")

        all_patent_ids = []
        component_summary = []

        for result in search_results:
            element_id = result['element_id']
            patent_ids = result.get('patent_ids', [])
            hits = result.get('final_hits', 0)
            status = result.get('status', 'unknown')

            all_patent_ids.extend(patent_ids)

            component_summary.append({
                'element_id': element_id,
                'element_text': result.get('element_text', ''),
                'hits': hits,
                'retrieved_count': len(patent_ids),
                'status': status
            })

            print(f"  {element_id}: {hits}件 (取得: {len(patent_ids)}件) - {status}")

        # 重複削除と出現頻度順ソート
        # 複数の構成要素でヒットした特許を優先的に上位に配置
        from collections import Counter
        patent_counts = Counter(all_patent_ids)
        unique_patent_ids = [pid for pid, count in patent_counts.most_common()]

        print(f"\n  総取得件数（重複含む）: {len(all_patent_ids)}件")
        print(f"  重複削除後の件数: {len(unique_patent_ids)}件")
        print(f"  重複削除数: {len(all_patent_ids) - len(unique_patent_ids)}件")
        print(f"  ソート方法: 出現頻度順（複数構成要素でヒットした特許を優先）")

        return {
            'total_components': len(search_results),
            'total_unique_patents': len(unique_patent_ids),
            'merged_patent_ids': unique_patent_ids,
            'component_summary': component_summary,
            'sorted_by_frequency': True
        }

    def execute_full_search(
        self,
        use_independent_only: bool = True,
        max_workers: int = 5,
        output_file: Optional[str] = None
    ) -> Dict:
        """
        完全検索実行（独立請求項のみ、並行処理、結果統合）

        Args:
            use_independent_only: 独立請求項のみを検索するか
            max_workers: 並行ワーカー数
            output_file: 結果出力ファイルパス（Noneなら出力なし）

        Returns:
            統合結果
        """
        print(f"\n{'#'*80}")
        print(f"# 完全検索実行")
        print(f"# 独立請求項のみ: {use_independent_only}")
        print(f"# 並行ワーカー数: {max_workers}")
        print(f"{'#'*80}")

        start_time = time.time()

        # ステップ1: 並行検索
        if use_independent_only:
            component_ids = self.independent_components
        else:
            component_ids = list(self.integrated_data.keys())

        search_results = self.search_all_components_parallel(
            component_ids,
            max_workers=max_workers
        )

        # ステップ2: 結果統合・重複削除
        merged_result = self.merge_and_deduplicate(search_results)

        # 処理時間
        elapsed_time = time.time() - start_time
        merged_result['elapsed_time'] = elapsed_time

        # 詳細結果を追加
        merged_result['component_results'] = search_results

        print(f"\n{'#'*80}")
        print(f"# 完全検索完了")
        print(f"# 総処理時間: {elapsed_time:.2f}秒")
        print(f"# 最終取得件数: {merged_result['total_unique_patents']}件")
        print(f"{'#'*80}")

        # クエリエラー統計の表示
        self._print_query_error_stats()

        # ファイル出力
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged_result, f, ensure_ascii=False, indent=2)
            print(f"\n結果を保存しました: {output_file}")

        return merged_result

    def _print_query_error_stats(self):
        """クエリエラー統計を表示"""
        total_404 = self.query_error_stats['404_errors']

        if total_404 > 0:
            print(f"\n{'='*80}")
            print(f"クエリエラー統計")
            print(f"{'='*80}")
            print(f"404エラー総数: {total_404}件")
            print(f"  - Claude修正成功: {self.query_error_stats['404_claude_fixed']}件 "
                  f"({self.query_error_stats['404_claude_fixed']/total_404*100:.1f}%)")
            print(f"  - フォールバック成功: {self.query_error_stats['404_fallback_success']}件 "
                  f"({self.query_error_stats['404_fallback_success']/total_404*100:.1f}%)")
            print(f"  - 最終失敗: {self.query_error_stats['404_final_failure']}件 "
                  f"({self.query_error_stats['404_final_failure']/total_404*100:.1f}%)")

            success_rate = (self.query_error_stats['404_claude_fixed'] +
                          self.query_error_stats['404_fallback_success']) / total_404 * 100
            print(f"\n404エラー回復率: {success_rate:.1f}%")
            print(f"{'='*80}")

        if self.query_error_stats['400_errors'] > 0:
            print(f"\n400エラー: {self.query_error_stats['400_errors']}件")

        if self.query_error_stats['other_http_errors'] > 0:
            print(f"その他のHTTPエラー: {self.query_error_stats['other_http_errors']}件")


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(description='構成要素ごと特許検索実行')
    parser.add_argument('--keywords', required=True, help='キーワードJSONファイル')
    parser.add_argument('--classifications', required=True, help='特許分類JSONファイル')
    parser.add_argument('--pf-key', default='../patentfield_key.json', help='PatentField APIキー')
    parser.add_argument('--workers', type=int, default=5, help='並行ワーカー数')
    parser.add_argument('--output', help='結果出力JSONファイル')
    parser.add_argument('--all-components', action='store_true', help='全構成要素を検索（独立請求項のみではない）')

    args = parser.parse_args()

    # 検索実行
    executor = PerComponentSearchExecutor(
        keywords_file=args.keywords,
        classifications_file=args.classifications,
        patentfield_key_path=args.pf_key
    )

    result = executor.execute_full_search(
        use_independent_only=not args.all_components,
        max_workers=args.workers,
        output_file=args.output
    )

    print("\n検索完了！")


if __name__ == '__main__':
    main()
