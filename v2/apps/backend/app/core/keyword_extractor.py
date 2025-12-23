#!/usr/bin/env python3
"""
特許構成要件キーワード抽出システム
Claude Sonnet 4.5 (Vertex AI) + PatentField API による検索キーワード自動生成

作成日: 2025年
対象: 特許審査における先行文献調査実務

最適化:
- AsyncIO完全移行 (2025年ベストプラクティス)
- Claude Prompt Caching (コスト90%削減、レイテンシ85%削減)
- aiohttp による HTTP/2 セッション再利用
"""

import json
import time
import asyncio
import aiohttp
import requests
from pathlib import Path
from typing import Dict, List, Union, Optional
import sys
import logging

# Google Cloud / Vertex AI
from google.oauth2 import service_account
from anthropic import AnthropicVertex

# Retry logic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    AsyncRetrying
)

# ロギング設定
logger = logging.getLogger(__name__)


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

    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def _call_claude_with_retry(self, **kwargs):
        """
        リトライロジック付きClaude API呼び出し

        Args:
            **kwargs: client.messages.createに渡すパラメータ

        Returns:
            Claude APIレスポンス
        """
        return self.client.messages.create(**kwargs)

    async def _call_claude_with_retry_async(self, **kwargs):
        """
        リトライロジック付きClaude API呼び出し（非同期版）

        Args:
            **kwargs: client.messages.createに渡すパラメータ

        Returns:
            Claude APIレスポンス
        """
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((Exception,)),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            stop=stop_after_attempt(3),
            reraise=True
        ):
            with attempt:
                # Claude APIは同期APIなので、スレッドプールで実行
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: self.client.messages.create(**kwargs)
                )

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
        # 重要度取得ヘルパー関数（構成要素の重要度 or 構成要件の重要度 両方に対応）
        def get_importance(c):
            return c.get('構成要素の重要度', c.get('構成要件の重要度', 0))

        # 重要度でソート
        sorted_constituents = sorted(
            constituents,
            key=get_importance,
            reverse=True
        )

        # プロンプト構築
        constituents_text = "\n".join([
            f"[{c['構成要素番号']}] 重要度{get_importance(c)}: {c['構成要素']}"
            for c in sorted_constituents
        ])

        system_prompt = """あなたは特許検索の専門家です。
構成要件から先行文献調査用の検索式を構築する際、以下の原則に従ってください：

1. 重要度の高い構成要素（0.9以上）をAND条件で組み合わせる
2. ヒット件数を絞り込むため、必須要素のみを使用
3. PatentField APIの全文検索（fulltext）構文を使用
4. 検索式は簡潔かつ効果的に

**PatentField API 全文検索構文:**
- AND条件: `+` または半角スペース（例: `+論理回路 +トランジスタ` or `論理回路 トランジスタ`）
- OR条件: `OR`（例: `論理回路 OR フリップフロップ`）
- NOT条件: `-`（例: `+半導体 -シリコン`）
- グルーピング: `()`（例: `(論理回路 OR フリップフロップ) +トランジスタ`）
- フレーズ検索: `""`（例: `"酸化物半導体"`）

**重要な構文制約:**
- 基本的にAND条件（+またはスペース）でキーワードを結合
- OR条件はグルーピング()内で使用
- 複雑なネストは避け、シンプルな構造を保つ
- 全文検索のため、フィールド指定（CL:、AB:など）は不要"""

        user_prompt = f"""以下の構成要件から、先行文献調査用の検索式を構築してください。

【構成要件リスト】
{constituents_text}

【要求】
1. 重要度{importance_threshold}以上の要素を特定
2. これらをAND条件で組み合わせた検索式を作成
3. PatentField APIの全文検索（fulltext）形式で出力
4. ヒット件数の目標: 50-500件程度

【検索式の正しい例】
✓ 正: +論理回路 +トランジスタ +オフ電流
✓ 正: 論理回路 トランジスタ オフ電流 容量素子
✓ 正: (論理回路 OR フリップフロップ) +トランジスタ +オフ電流
✓ 正: +"酸化物半導体" +トランジスタ +チャネル

【検索式の誤った例】
✗ 誤: CL:論理回路 AND CL:トランジスタ ← コマンド検索構文（CL:）は使用不可
✗ 誤: ((論理回路 OR フリップフロップ) AND (オフ電流 OR リーク電流)) ← 過度なネスト
✗ 誤: トランジスタ AND オフ電流 ← ANDは`+`またはスペースで表現

【重要な制約】
- AND条件は`+`またはスペースで結合（`+A +B`または`A B`）
- OR条件は必要に応じて括弧でグループ化（`(A OR B)`）
- 基本はシンプルなスペース区切りのキーワード列挙を優先
- フィールド指定（CL:、AB:など）は使用しない（全文検索のため）

【出力フォーマット（JSON）】
{{
  "query": "+論理回路 +トランジスタ +オフ電流",
  "strategy": "重要度1.0の「オフ電流」を核として、重要度0.95の「論理回路」「トランジスタ」をAND条件で組み合わせ",
  "high_importance_items": ["1d", "1a", "1c"],
  "expected_hits": "100-300件"
}}

JSONのみを出力してください。"""

        print("検索式を構築中...")

        try:
            # Claude API呼び出し（リトライロジック付き）
            response = self._call_claude_with_retry(
                model=self.model,
                max_tokens=16000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # stop_reasonチェック
            if response.stop_reason == "max_tokens":
                logger.warning(f"検索式構築: 出力が最大トークン数で切り捨てられました")

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

各階層で以下の個数のキーワードを優先度順に並べ、日本語と英語の両方を出力してください：

- ドンピシャキーワード: 10-15個（同義語、類義語、技術的等価表現を含む）
- 上位概念キーワード: 15-20個（階層的に広い概念、関連分野を含む）
- 下位概念キーワード: 15-20個（具体的実装、技術的変種、応用例を含む）

各キーワードは以下の基準で選定してください：
1. 予備検索結果での頻出度が高い
2. 技術的に重要性が高い
3. 階層間で重複を避ける（ドンピシャと上位概念で同じ語は避ける）
4. 日本語と英語で自然な対応関係にある

化学系の特許の場合、以下の原則を沿ってキーワードを生成、予備検索の頻出度の優先度は下げる
1. 「名称」と「機能」の両面から攻める
化学物質は、**「物質名（構造）」で特定される場合と、「配合目的（機能）」**で特定される場合があります。
例: 界面活性剤を探す場合
構造: 「ドデシル硫酸ナトリウム」「SDS」「アルキル硫酸塩」
機能: 「界面活性剤」「乳化剤」「分散剤」「サーファクタント」
セオリ: 片方だけでは漏れるため、必ず両方の観点をリストアップする。
2. 「表記ゆれ」を徹底的に網羅する（シノニム展開）
化学物質名は、IUPAC名、慣用名、略称、商品名など多岐にわたります。
例: エタノール
Ethanol, Ethyl alcohol, EtOH, Alcohol C2, Hydroxyethane
セオリ: 略称や英語名も含めてOR条件で繋ぐ。
3. 「マーカッシュ構造」を具体化する
特許請求の範囲では「アルキル基」「ハロゲン原子」のように広く書かれます（マーカッシュ形式）。しかし、検索で「アルキル基」と入力しても、実施例の「メチル基」はヒットしないことが多いです。
セオリ: 請求項が上位概念（ジェネリック）でも、キーワードは実施例レベルの下位概念（具体例）まで展開する。

"""

        importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))
        user_prompt = f"""【キーワード抽出の目的】
特許先行文献調査において、関連する全ての技術的変種と類似概念を漏れなく発見するため、
包括的かつ多様なキーワードセットを構築します。

【各階層の目標】
- ドンピシャ: 構成要素の核心的な意味を表す10-15個の表現バリエーション
- 上位概念: より広い技術分野をカバーする15-20個の関連概念
- 下位概念: 具体的な実装や応用を示す15-20個の詳細表現

【構成要素】
番号: {constituent['構成要素番号']}
内容: {constituent['構成要素']}
重要度: {importance}

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
            # Claude API呼び出し（リトライロジック付き）
            response = self._call_claude_with_retry(
                model=self.model,
                max_tokens=16000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # stop_reasonチェック
            if response.stop_reason == "max_tokens":
                logger.warning(f"キーワード精錬[{constituent['構成要素番号']}]: 出力が最大トークン数で切り捨てられました")

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

    def validate_and_refine_keywords(
        self,
        constituent: Dict,
        donpicha_keywords: List[Dict]
    ) -> Dict:
        """
        ドンピシャキーワードの妥当性検証と改善

        Claude Sonnet 4.5により、特許検索に適さないキーワード
        （「式(XX)で表される」などの明細書特有表現）を検出し、
        適切な技術用語に置き換える。

        Args:
            constituent: 構成要素情報
            donpicha_keywords: 精錬されたドンピシャキーワードリスト

        Returns:
            {
                "evaluation": "OK" | "MINOR_ISSUES" | "MAJOR_ISSUES",
                "issues": ["問題点1", ...],
                "refined_keywords": [改善後のキーワード],
                "original_keywords": [元のキーワード],
                "tokens": トークン情報
            }
        """
        # キーワードリストをテキスト化
        keywords_text = "\n".join([
            f"{i+1}. {kw['keyword']} (優先度: {kw.get('priority', i+1)}, 頻出度: {kw.get('頻出度', 'N/A')})"
            for i, kw in enumerate(donpicha_keywords[:15])  # 最初の15個を検証
        ])

        system_prompt = """あなたは特許検索の専門家です。
生成されたドンピシャキーワードが、PatentFieldなどの特許データベース検索に適しているか評価してください。

【評価基準】

**問題あり（MAJOR_ISSUES）の例:**
❌ 「式(a4)で表される構造単位」← 特定の特許文書でのみ使用される明細書特有の表現
❌ 「式(II)で表される塩」← 明細書の記号表現でデータベースに存在しない
❌ 「a5構造単位」← 略語で意味不明
❌ 「特定構造単位の非含有」← 否定表現で検索困難

**問題あり（MINOR_ISSUES）の例:**
⚠️ 「フッ素含有構造単位」← やや抽象的だが検索可能
⚠️ 「ペルフルオロアルキル含有単位」← 専門的だが一般的な用語

**問題なし（OK）の例:**
✅ 「酸不安定基」「酸解離性基」「酸脱離性基」← 一般的な技術用語
✅ 「酸発生剤」「光酸発生剤」← 同義語を含む
✅ 「レジスト組成物」「フォトレジスト」← 広く使われる用語
✅ 「トランジスタ」「半導体素子」← 基本的な技術用語

【判定ルール】
1. 「式(XX)」「式（XX）」を含む場合は必ずMAJOR_ISSUES
2. 特定の特許文書でのみ定義される表現はMAJOR_ISSUES
3. 略語や記号のみの表現はMAJOR_ISSUES
4. 一般的な技術辞書に載っている用語はOK
5. 複数の同義語・類義語が含まれている場合はOK

【改善方針】
- 明細書特有の表現を一般的な技術用語に変換
- 「式(a4)で表される構造単位」→「フッ素含有樹脂構造単位」「疎水性構造単位」など
- 同義語・類義語を複数含める
- 検索範囲を適度に広げる（狭すぎず、広すぎず）

【出力フォーマット】
JSON形式で以下を出力:
{
  "evaluation": "OK" | "MINOR_ISSUES" | "MAJOR_ISSUES",
  "issues": ["問題点1", "問題点2", ...],
  "reasoning": "判定理由の簡潔な説明",
  "refined_keywords": [
    {"keyword": "改善後キーワード1", "priority": 1, "頻出度": 推定値, "改善理由": "理由"},
    {"keyword": "改善後キーワード2", "priority": 2, "頻出度": 推定値, "改善理由": "理由"},
    ...
  ]
}

**重要**: evaluationがOKの場合、refined_keywordsは空の配列[]でよい。
MINOR_ISSUESまたはMAJOR_ISSUESの場合のみ、改善されたキーワードを10-15個生成してください。"""

        importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))

        user_prompt = f"""【構成要素情報】
構成要素番号: {constituent['構成要素番号']}
構成要素: {constituent['構成要素']}
重要度: {importance}

【生成されたドンピシャキーワード】
{keywords_text}

【タスク】
このキーワードリストを評価し、特許データベース検索に適していない表現があれば指摘してください。
特に「式(XX)で表される」のような明細書特有の表現は、一般的な技術用語に置き換えてください。

問題がない場合は evaluation: "OK" を返してください。
問題がある場合は、改善されたキーワードリストを生成してください。

JSONのみを出力してください。"""

        print(f"      [検証] キーワード妥当性チェック中...")

        try:
            # Claude API呼び出し（リトライロジック付き）
            response = self._call_claude_with_retry(
                model=self.model,
                max_tokens=8000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # stop_reasonチェック
            if response.stop_reason == "max_tokens":
                logger.warning(f"キーワード検証[{constituent['構成要素番号']}]: 出力が最大トークン数で切り捨てられました")

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
            validation_result = json.loads(json_text)

            validation_result['tokens'] = tokens
            validation_result['original_keywords'] = donpicha_keywords

            # 結果を表示
            evaluation = validation_result['evaluation']
            if evaluation == 'OK':
                print(f"      ✅ 問題なし")
            elif evaluation == 'MINOR_ISSUES':
                print(f"      ⚠️ 軽微な問題あり: {', '.join(validation_result.get('issues', [])[:2])}")
            else:  # MAJOR_ISSUES
                print(f"      ❌ 重大な問題あり: {', '.join(validation_result.get('issues', [])[:2])}")
                print(f"      → キーワードを再生成しました")

            return validation_result

        except Exception as e:
            print(f"      ⚠️ キーワード検証エラー（元のキーワードを使用）: {e}")
            # エラーの場合は元のキーワードをそのまま使用
            return {
                "evaluation": "ERROR",
                "issues": [str(e)],
                "reasoning": "検証処理でエラーが発生したため、元のキーワードを使用",
                "refined_keywords": [],
                "original_keywords": donpicha_keywords,
                "tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            }

    async def refine_keywords_async(
        self,
        constituent: Dict,
        search_results: List[Dict]
    ) -> Dict:
        """
        キーワード精錬（Claude使用）- 非同期版

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

各階層で以下の個数のキーワードを優先度順に並べ、日本語と英語の両方を出力してください：

- ドンピシャキーワード: 10-15個（同義語、類義語、技術的等価表現を含む）
- 上位概念キーワード: 15-20個（階層的に広い概念、関連分野を含む）
- 下位概念キーワード: 15-20個（具体的実装、技術的変種、応用例を含む）

各キーワードは以下の基準で選定してください：
1. 予備検索結果での頻出度が高い
2. 技術的に重要性が高い
3. 階層間で重複を避ける（ドンピシャと上位概念で同じ語は避ける）
4. 日本語と英語で自然な対応関係にある

化学系の特許の場合、以下の原則を沿ってキーワードを生成、予備検索の頻出度の優先度は下げる
1. 「名称」と「機能」の両面から攻める
化学物質は、**「物質名（構造）」で特定される場合と、「配合目的（機能）」**で特定される場合があります。
例: 界面活性剤を探す場合
構造: 「ドデシル硫酸ナトリウム」「SDS」「アルキル硫酸塩」
機能: 「界面活性剤」「乳化剤」「分散剤」「サーファクタント」
セオリ: 片方だけでは漏れるため、必ず両方の観点をリストアップする。
2. 「表記ゆれ」を徹底的に網羅する（シノニム展開）
化学物質名は、IUPAC名、慣用名、略称、商品名など多岐にわたります。
例: エタノール
Ethanol, Ethyl alcohol, EtOH, Alcohol C2, Hydroxyethane
セオリ: 略称や英語名も含めてOR条件で繋ぐ。
3. 「マーカッシュ構造」を具体化する
特許請求の範囲では「アルキル基」「ハロゲン原子」のように広く書かれます（マーカッシュ形式）。しかし、検索で「アルキル基」と入力しても、実施例の「メチル基」はヒットしないことが多いです。
セオリ: 請求項が上位概念（ジェネリック）でも、キーワードは実施例レベルの下位概念（具体例）まで展開する。

"""

        importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))
        user_prompt = f"""【キーワード抽出の目的】
特許先行文献調査において、関連する全ての技術的変種と類似概念を漏れなく発見するため、
包括的かつ多様なキーワードセットを構築します。

【各階層の目標】
- ドンピシャ: 構成要素の核心的な意味を表す10-15個の表現バリエーション
- 上位概念: より広い技術分野をカバーする15-20個の関連概念
- 下位概念: 具体的な実装や応用を示す15-20個の詳細表現

【構成要素】
番号: {constituent['構成要素番号']}
内容: {constituent['構成要素']}
重要度: {importance}

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
            # Claude API呼び出し（リトライロジック付き）- 非同期版
            response = await self._call_claude_with_retry_async(
                model=self.model,
                max_tokens=16000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # stop_reasonチェック
            if response.stop_reason == "max_tokens":
                logger.warning(f"キーワード精錬[{constituent['構成要素番号']}]: 出力が最大トークン数で切り捨てられました")

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

    async def validate_and_refine_keywords_async(
        self,
        constituent: Dict,
        donpicha_keywords: List[Dict]
    ) -> Dict:
        """
        ドンピシャキーワードの妥当性検証と改善 - 非同期版

        Args:
            constituent: 構成要素情報
            donpicha_keywords: 精錬されたドンピシャキーワードリスト

        Returns:
            検証結果の辞書
        """
        # キーワードリストをテキスト化
        keywords_text = "\n".join([
            f"{i+1}. {kw['keyword']} (優先度: {kw.get('priority', i+1)}, 頻出度: {kw.get('頻出度', 'N/A')})"
            for i, kw in enumerate(donpicha_keywords[:15])  # 最初の15個を検証
        ])

        system_prompt = """あなたは特許検索の専門家です。
生成されたドンピシャキーワードが、PatentFieldなどの特許データベース検索に適しているか評価してください。

【評価基準】

**問題あり（MAJOR_ISSUES）の例:**
❌ 「式(a4)で表される構造単位」← 特定の特許文書でのみ使用される明細書特有の表現
❌ 「式(II)で表される塩」← 明細書の記号表現でデータベースに存在しない
❌ 「a5構造単位」← 略語で意味不明
❌ 「特定構造単位の非含有」← 否定表現で検索困難

**問題あり（MINOR_ISSUES）の例:**
⚠️ 「フッ素含有構造単位」← やや抽象的だが検索可能
⚠️ 「ペルフルオロアルキル含有単位」← 専門的だが一般的な用語

**問題なし（OK）の例:**
✅ 「酸不安定基」「酸解離性基」「酸脱離性基」← 一般的な技術用語
✅ 「酸発生剤」「光酸発生剤」← 同義語を含む
✅ 「レジスト組成物」「フォトレジスト」← 広く使われる用語
✅ 「トランジスタ」「半導体素子」← 基本的な技術用語

【判定ルール】
1. 「式(XX)」「式（XX）」を含む場合は必ずMAJOR_ISSUES
2. 特定の特許文書でのみ定義される表現はMAJOR_ISSUES
3. 略語や記号のみの表現はMAJOR_ISSUES
4. 一般的な技術辞書に載っている用語はOK
5. 複数の同義語・類義語が含まれている場合はOK

【改善方針】
- 明細書特有の表現を一般的な技術用語に変換
- 「式(a4)で表される構造単位」→「フッ素含有樹脂構造単位」「疎水性構造単位」など
- 同義語・類義語を複数含める
- 検索範囲を適度に広げる（狭すぎず、広すぎず）

【出力フォーマット】
JSON形式で以下を出力:
{
  "evaluation": "OK" | "MINOR_ISSUES" | "MAJOR_ISSUES",
  "issues": ["問題点1", "問題点2", ...],
  "reasoning": "判定理由の簡潔な説明",
  "refined_keywords": [
    {"keyword": "改善後キーワード1", "priority": 1, "頻出度": 推定値, "改善理由": "理由"},
    {"keyword": "改善後キーワード2", "priority": 2, "頻出度": 推定値, "改善理由": "理由"},
    ...
  ]
}

**重要**: evaluationがOKの場合、refined_keywordsは空の配列[]でよい。
MINOR_ISSUESまたはMAJOR_ISSUESの場合のみ、改善されたキーワードを10-15個生成してください。"""

        importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))

        user_prompt = f"""【構成要素情報】
構成要素番号: {constituent['構成要素番号']}
構成要素: {constituent['構成要素']}
重要度: {importance}

【生成されたドンピシャキーワード】
{keywords_text}

【タスク】
このキーワードリストを評価し、特許データベース検索に適していない表現があれば指摘してください。
特に「式(XX)で表される」のような明細書特有の表現は、一般的な技術用語に置き換えてください。

問題がない場合は evaluation: "OK" を返してください。
問題がある場合は、改善されたキーワードリストを生成してください。

JSONのみを出力してください。"""

        print(f"      [検証] キーワード妥当性チェック中...")

        try:
            # Claude API呼び出し（リトライロジック付き）- 非同期版
            response = await self._call_claude_with_retry_async(
                model=self.model,
                max_tokens=8000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # stop_reasonチェック
            if response.stop_reason == "max_tokens":
                logger.warning(f"キーワード検証[{constituent['構成要素番号']}]: 出力が最大トークン数で切り捨てられました")

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
            validation_result = json.loads(json_text)

            validation_result['tokens'] = tokens
            validation_result['original_keywords'] = donpicha_keywords

            # 結果を表示
            evaluation = validation_result['evaluation']
            if evaluation == 'OK':
                print(f"      ✅ 問題なし")
            elif evaluation == 'MINOR_ISSUES':
                print(f"      ⚠️ 軽微な問題あり: {', '.join(validation_result.get('issues', [])[:2])}")
            else:  # MAJOR_ISSUES
                print(f"      ❌ 重大な問題あり: {', '.join(validation_result.get('issues', [])[:2])}")
                print(f"      → キーワードを再生成しました")

            return validation_result

        except Exception as e:
            print(f"      ⚠️ キーワード検証エラー（元のキーワードを使用）: {e}")
            # エラーの場合は元のキーワードをそのまま使用
            return {
                "evaluation": "ERROR",
                "issues": [str(e)],
                "reasoning": "検証処理でエラーが発生したため、元のキーワードを使用",
                "refined_keywords": [],
                "original_keywords": donpicha_keywords,
                "tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            }

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

        # 重要度でフィルタ（構成要素の重要度 or 構成要件の重要度 両方に対応）
        target_constituents = [
            c for c in constituents
            if c.get('構成要素の重要度', c.get('構成要件の重要度', 0)) >= min_importance
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
        total_validation_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        validation_summary = []

        for constituent in target_constituents:
            keywords = self.refine_keywords(constituent, search_result.get('records', []))

            # トークンを集計
            tokens = keywords.pop('tokens')
            for key in total_refine_tokens:
                total_refine_tokens[key] += tokens[key]

            # ステップ3.5: ドンピシャキーワードの妥当性検証
            donpicha_keywords_jp = keywords.get('ドンピシャキーワード_日本語', [])

            if donpicha_keywords_jp:
                validation_result = self.validate_and_refine_keywords(
                    constituent,
                    donpicha_keywords_jp
                )

                # 検証トークンを集計
                validation_tokens = validation_result.get('tokens', {})
                for key in total_validation_tokens:
                    total_validation_tokens[key] += validation_tokens.get(key, 0)

                # 検証サマリーを記録
                validation_summary.append({
                    "構成要素番号": constituent['構成要素番号'],
                    "evaluation": validation_result.get('evaluation', 'ERROR'),
                    "issues": validation_result.get('issues', []),
                    "reasoning": validation_result.get('reasoning', '')
                })

                # 重大な問題がある場合は改善されたキーワードを使用
                if validation_result.get('evaluation') in ['MAJOR_ISSUES', 'MINOR_ISSUES']:
                    refined_kws = validation_result.get('refined_keywords', [])
                    if refined_kws:
                        keywords['ドンピシャキーワード_日本語'] = refined_kws
                        keywords['validation_applied'] = True
                        keywords['validation_result'] = {
                            "evaluation": validation_result['evaluation'],
                            "issues": validation_result.get('issues', []),
                            "reasoning": validation_result.get('reasoning', '')
                        }
                    else:
                        # 改善キーワードが空の場合は元のキーワードを保持
                        keywords['validation_applied'] = False
                else:
                    # 問題なしの場合は元のキーワードをそのまま使用
                    keywords['validation_applied'] = False

            # 結果に追加
            importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))
            keywords_list.append({
                "構成要素番号": constituent['構成要素番号'],
                "構成要素": constituent['構成要素'],
                "重要度": importance,
                "is_independent": constituent.get('is_independent', False),
                **keywords
            })

        # 処理時間
        processing_time = time.time() - start_time

        # 検証統計
        major_issues_count = sum(1 for v in validation_summary if v['evaluation'] == 'MAJOR_ISSUES')
        minor_issues_count = sum(1 for v in validation_summary if v['evaluation'] == 'MINOR_ISSUES')
        ok_count = sum(1 for v in validation_summary if v['evaluation'] == 'OK')

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
            "validation_summary": {
                "total_validated": len(validation_summary),
                "major_issues": major_issues_count,
                "minor_issues": minor_issues_count,
                "ok": ok_count,
                "details": validation_summary
            },
            "tokens": {
                "step1_構築": query_result['tokens'],
                "step3_精錬": total_refine_tokens,
                "step3.5_検証": total_validation_tokens,
                "total_tokens": (
                    query_result['tokens']['total_tokens'] +
                    total_refine_tokens['total_tokens'] +
                    total_validation_tokens['total_tokens']
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

    async def extract_keywords_async(
        self,
        constituent_json_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        min_importance: float = 0.7,
        importance_threshold: float = 0.9
    ) -> Dict:
        """
        メイン処理: 構成要件JSONからキーワード抽出（非同期・並列処理版）

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

        # 重要度でフィルタ（構成要素の重要度 or 構成要件の重要度 両方に対応）
        target_constituents = [
            c for c in constituents
            if c.get('構成要素の重要度', c.get('構成要件の重要度', 0)) >= min_importance
        ]
        print(f"抽出対象（重要度>={min_importance}）: {len(target_constituents)}個")

        # ステップ1: 検索式構築（同期処理）
        print("\n" + "="*60)
        print("ステップ1: 検索式構築")
        print("="*60)
        query_result = self.build_search_query(constituents, importance_threshold)

        print(f"検索式: {query_result['query']}")
        print(f"戦略: {query_result['strategy']}")

        # ステップ2: PatentField API予備検索（同期処理）
        print("\n" + "="*60)
        print("ステップ2: PatentField API予備検索")
        print("="*60)
        search_result = self.preliminary_search(query_result['query'], limit=50)

        # ステップ3: キーワード精錬（並列処理）
        print("\n" + "="*60)
        print("ステップ3: キーワード精錬（並列処理）")
        print("="*60)

        # 各構成要素のキーワード精錬と検証を並列実行
        async def process_constituent(constituent: Dict) -> Dict:
            """1つの構成要素を処理"""
            # キーワード精錬
            keywords = await self.refine_keywords_async(constituent, search_result.get('records', []))

            # トークン情報を取り出し
            refine_tokens = keywords.pop('tokens')

            # ドンピシャキーワードの妥当性検証
            donpicha_keywords_jp = keywords.get('ドンピシャキーワード_日本語', [])
            validation_result = None
            validation_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            if donpicha_keywords_jp:
                validation_result = await self.validate_and_refine_keywords_async(
                    constituent,
                    donpicha_keywords_jp
                )
                validation_tokens = validation_result.get('tokens', validation_tokens)

                # 重大な問題がある場合は改善されたキーワードを使用
                if validation_result.get('evaluation') in ['MAJOR_ISSUES', 'MINOR_ISSUES']:
                    refined_kws = validation_result.get('refined_keywords', [])
                    if refined_kws:
                        keywords['ドンピシャキーワード_日本語'] = refined_kws
                        keywords['validation_applied'] = True
                        keywords['validation_result'] = {
                            "evaluation": validation_result['evaluation'],
                            "issues": validation_result.get('issues', []),
                            "reasoning": validation_result.get('reasoning', '')
                        }
                    else:
                        keywords['validation_applied'] = False
                else:
                    keywords['validation_applied'] = False

            # 結果を構築
            importance = constituent.get('構成要素の重要度', constituent.get('構成要件の重要度', 0))
            result_item = {
                "構成要素番号": constituent['構成要素番号'],
                "構成要素": constituent['構成要素'],
                "重要度": importance,
                "is_independent": constituent.get('is_independent', False),
                **keywords
            }

            # 検証サマリー
            validation_summary_item = None
            if validation_result:
                validation_summary_item = {
                    "構成要素番号": constituent['構成要素番号'],
                    "evaluation": validation_result.get('evaluation', 'ERROR'),
                    "issues": validation_result.get('issues', []),
                    "reasoning": validation_result.get('reasoning', '')
                }

            return {
                "result": result_item,
                "refine_tokens": refine_tokens,
                "validation_tokens": validation_tokens,
                "validation_summary": validation_summary_item
            }

        # 全構成要素を並列処理
        print(f"並列処理開始: {len(target_constituents)}個の構成要素")
        tasks = [process_constituent(constituent) for constituent in target_constituents]
        processed_results = await asyncio.gather(*tasks)

        # 結果を集計
        keywords_list = []
        total_refine_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        total_validation_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        validation_summary = []

        for processed in processed_results:
            keywords_list.append(processed["result"])

            # トークン集計
            for key in total_refine_tokens:
                total_refine_tokens[key] += processed["refine_tokens"][key]
                total_validation_tokens[key] += processed["validation_tokens"][key]

            # 検証サマリー
            if processed["validation_summary"]:
                validation_summary.append(processed["validation_summary"])

        # 処理時間
        processing_time = time.time() - start_time

        # 検証統計
        major_issues_count = sum(1 for v in validation_summary if v['evaluation'] == 'MAJOR_ISSUES')
        minor_issues_count = sum(1 for v in validation_summary if v['evaluation'] == 'MINOR_ISSUES')
        ok_count = sum(1 for v in validation_summary if v['evaluation'] == 'OK')

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
            "validation_summary": {
                "total_validated": len(validation_summary),
                "major_issues": major_issues_count,
                "minor_issues": minor_issues_count,
                "ok": ok_count,
                "details": validation_summary
            },
            "tokens": {
                "step1_構築": query_result['tokens'],
                "step3_精錬": total_refine_tokens,
                "step3.5_検証": total_validation_tokens,
                "total_tokens": (
                    query_result['tokens']['total_tokens'] +
                    total_refine_tokens['total_tokens'] +
                    total_validation_tokens['total_tokens']
                )
            },
            "処理時間_秒": round(processing_time, 2),
            "model": self.model,
            "parallel_processing": True
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
        print(f"並列処理により処理時間: {processing_time:.2f}秒")

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

            # キーワード検証結果
            if 'validation_summary' in result:
                val_summary = result['validation_summary']
                print(f"\n【キーワード検証】")
                print(f"  検証数: {val_summary['total_validated']}個")
                print(f"  ✅ 問題なし: {val_summary['ok']}個")
                print(f"  ⚠️  軽微な問題: {val_summary['minor_issues']}個")
                print(f"  ❌ 重大な問題: {val_summary['major_issues']}個")

                # 重大な問題があった構成要素を表示
                if val_summary['major_issues'] > 0:
                    print(f"\n  重大な問題が検出された構成要素:")
                    for detail in val_summary['details']:
                        if detail['evaluation'] == 'MAJOR_ISSUES':
                            print(f"    - [{detail['構成要素番号']}] {', '.join(detail.get('issues', [])[:2])}")

            # トークン使用量
            tokens = result['tokens']
            print(f"\n【トークン使用量】")
            print(f"  ステップ1（検索式構築）: {tokens['step1_構築']['total_tokens']:,} tokens")
            print(f"  ステップ3（キーワード精錬）: {tokens['step3_精錬']['total_tokens']:,} tokens")
            if 'step3.5_検証' in tokens:
                print(f"  ステップ3.5（キーワード検証）: {tokens['step3.5_検証']['total_tokens']:,} tokens")
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
