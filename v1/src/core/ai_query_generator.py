"""
AI-Driven Query Generator
Generates optimized search queries using Claude Sonnet 4.5 after manual iterations fail
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AIGeneratedQuery:
    """AI生成クエリ"""
    query_string: str  # 生成された検索クエリ文字列
    reasoning: str  # AI の推論プロセス
    confidence: float  # 信頼度 (0.0-1.0)
    suggested_adjustments: List[str]  # 提案された調整


class AIQueryGenerator:
    """AI駆動型クエリ生成クラス（Claude Sonnet 4.5使用）"""

    def __init__(self, ai_client, max_ai_attempts: int = 10):
        """
        初期化

        Args:
            ai_client: ClaudeClient または GeminiClient インスタンス
            max_ai_attempts: AI生成クエリの最大試行回数（デフォルト: 10）
        """
        self.ai_client = ai_client
        self.max_ai_attempts = max_ai_attempts

    def generate_optimized_query(self,
                                components: List[Any],
                                keywords_list: List[Any],
                                classifications_list: List[Any],
                                iteration_details: List[Dict[str, Any]],
                                target_min_hits: int,
                                target_max_hits: int) -> Tuple[Optional[AIGeneratedQuery], Optional[Any]]:
        """
        AI（Claude Sonnet 4.5）を使用して最適化されたクエリを生成

        Args:
            components: 構成要素リスト
            keywords_list: キーワードリスト
            classifications_list: 分類コードリスト
            iteration_details: 過去の反復詳細情報
            target_min_hits: 目標最小ヒット件数
            target_max_hits: 目標最大ヒット件数

        Returns:
            (AIGeneratedQuery, トークン使用量) または (None, None)（生成失敗時）
        """
        logger.info("Generating optimized query using AI (Claude Sonnet 4.5)...")

        # プロンプトを作成
        prompt = self._create_query_generation_prompt(
            components, keywords_list, classifications_list,
            iteration_details, target_min_hits, target_max_hits
        )

        try:
            # AI（Claude Sonnet 4.5）でクエリ生成
            response, token_usage = self.ai_client.generate_content(
                prompt,
                temperature=0.3,  # 創造性と精度のバランス
                max_output_tokens=4096  # 十分な出力長
            )

            # レスポンスをパース
            ai_query = self._parse_ai_response(response)

            logger.info(f"AI generated query with confidence: {ai_query.confidence}")
            logger.info(f"AI reasoning: {ai_query.reasoning[:200]}...")
            logger.info(f"Token usage for AI query generation: {token_usage.to_dict()}")

            return ai_query, token_usage

        except Exception as e:
            logger.error(f"Failed to generate AI query: {e}")
            return None, None

    def _create_query_generation_prompt(self,
                                       components: List[Any],
                                       keywords_list: List[Any],
                                       classifications_list: List[Any],
                                       iteration_details: List[Dict[str, Any]],
                                       target_min_hits: int,
                                       target_max_hits: int) -> str:
        """AIクエリ生成用のプロンプトを作成"""

        # 構成要素情報のサマリー
        components_summary = []
        for comp, keywords, classification in zip(components[:10], keywords_list[:10], classifications_list[:10]):
            comp_info = {
                "id": comp.構成要素番号,
                "text": comp.構成要素[:100],  # 最初の100文字
                "importance": comp.構成要素の重要度,
                "primary_keywords": keywords.一次検索キーワード[:3],
                "cpc_codes": classification.一次特定最終CPC[:3]
            }
            components_summary.append(comp_info)

        # イテレーション履歴のサマリー（最後の5回）
        recent_iterations = iteration_details[-5:] if len(iteration_details) > 5 else iteration_details
        iteration_summary = []
        for iteration in recent_iterations:
            iter_info = {
                "iteration": iteration["iteration"],
                "adjustment_type": iteration["adjustment_type"],
                "keyword_level": iteration["keyword_expansion_level"],
                "importance_threshold": iteration["importance_threshold"],
                "hits": iteration["total_hits"],
                "query_snippet": iteration["search_query"][:150]  # 最初の150文字
            }
            iteration_summary.append(iter_info)

        # プロンプト作成
        prompt = f"""
あなたは特許先行技術調査の専門家です。これまでの検索結果を分析し、目標ヒット件数（{target_min_hits}～{target_max_hits}件）を達成するための最適な検索クエリを生成してください。

# 構成要素情報（上位10個）

{self._format_components_for_prompt(components_summary)}

# これまでの検索履歴（最近5回の反復）

{self._format_iterations_for_prompt(iteration_summary)}

# 検索クエリ構文

Google Patents の検索クエリでは以下の構文が使用できます：

**重要: CPC分類コードの構文ルール**
- サブクラスレベルワイルドカード: cpc=G11C (小文字、引用符なし)
  例: cpc=G11C, cpc=H10D
- 特定分類コード（完全一致）: CPC="G11C11/00" (大文字、引用符あり)
  例: CPC="G11C11/56", CPC="H10D30/00"

**その他の構文**
- キーワード: "キーワード" （ダブルクォートで囲む）
- 論理演算子: AND, OR
- グルーピング: 括弧 () を使用

# 要求事項

1. **目標ヒット件数**: {target_min_hits}～{target_max_hits}件を目指してください
2. **過去の失敗パターンを分析**: 上記の検索履歴を分析し、なぜ目標を達成できなかったかを考察してください
3. **最適なクエリを生成**: 以下の要素を適切に組み合わせた検索クエリを作成してください
   - 重要な構成要素のFI/CPCコード（最大5個）
   - 重要なキーワード（各構成要素から最大5個）
   - 適切な論理演算子（AND, OR）
4. **信頼度を評価**: 生成したクエリが目標ヒット件数を達成できる可能性を0.0～1.0で評価してください

# 出力形式

以下のJSON形式で出力してください：

```json
{{
  "query_string": "生成された検索クエリ文字列",
  "reasoning": "このクエリを選んだ理由と、過去の失敗パターンの分析結果（200文字以内）",
  "confidence": 0.75,
  "suggested_adjustments": [
    "ヒット数が多すぎる場合の調整案1",
    "ヒット数が少なすぎる場合の調整案2"
  ]
}}
```

# 重要な注意事項

- FI/CPCコードは必ずダブルクォートで囲み、FI="コード" または CPC="コード" の形式で記述してください
- バックスラッシュ（\\）は使用しないでください（Google Patents APIは非対応）
- クエリの長さが長すぎないように注意してください（目安: 500文字以内）
- JSON形式のみを出力してください（説明文やマークダウンは不要です）

JSON形式のみを出力してください：
"""
        return prompt

    def _format_components_for_prompt(self, components_summary: List[Dict[str, Any]]) -> str:
        """構成要素情報をプロンプト用にフォーマット"""
        formatted = []
        for comp in components_summary:
            formatted.append(f"""
構成要素ID: {comp['id']}
  テキスト: {comp['text']}
  重要度: {comp['importance']}
  主要キーワード: {', '.join(comp['primary_keywords'])}
  CPCコード: {', '.join(comp['cpc_codes'])}
""")
        return "\n".join(formatted)

    def _format_iterations_for_prompt(self, iteration_summary: List[Dict[str, Any]]) -> str:
        """イテレーション履歴をプロンプト用にフォーマット"""
        formatted = []
        for iter_info in iteration_summary:
            formatted.append(f"""
Iteration {iter_info['iteration']}:
  調整タイプ: {iter_info['adjustment_type']}
  キーワードレベル: {iter_info['keyword_level']}
  重要度閾値: {iter_info['importance_threshold']}
  ヒット数: {iter_info['hits']}件
  クエリ（抜粋）: {iter_info['query_snippet']}...
""")
        return "\n".join(formatted)

    def _parse_ai_response(self, response: str) -> AIGeneratedQuery:
        """AIレスポンスをパースしてAIGeneratedQueryに変換"""
        import json

        try:
            # JSONブロックを抽出
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

            ai_query = AIGeneratedQuery(
                query_string=data.get("query_string", ""),
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.5)),
                suggested_adjustments=data.get("suggested_adjustments", [])
            )

            return ai_query

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response: {response}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise
