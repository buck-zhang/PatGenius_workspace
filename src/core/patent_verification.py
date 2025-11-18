"""
特許検索結果の検証ツール
Patent Search Result Verification Tool
"""

import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)


class PatentVerificationTool:
    """特許検索結果を検証し、特定の特許が含まれるか確認するツール"""

    def __init__(self, google_patents_api_url: str):
        """
        初期化

        Args:
            google_patents_api_url: Google Patents APIのURL
        """
        self.google_patents_api_url = google_patents_api_url

    def verify_target_patent(self,
                            target_patent_number: str,
                            search_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        ターゲット特許が検索結果に含まれているか検証

        Args:
            target_patent_number: 検証対象の特許番号 (例: JP2011171723A)
            search_result: 検索結果

        Returns:
            検証結果の辞書
        """
        patents = search_result.get("patents", [])
        patent_numbers = [p.get("patent_number", "") for p in patents]

        is_found = target_patent_number in patent_numbers

        if is_found:
            logger.info(f"✅ Target patent {target_patent_number} found in search results")
            return {
                "found": True,
                "message": f"ターゲット特許 {target_patent_number} が検索結果に含まれています"
            }
        else:
            logger.warning(f"❌ Target patent {target_patent_number} NOT found in search results")

            # 原因分析を実行
            analysis = self._analyze_why_not_found(target_patent_number, search_result)

            return {
                "found": False,
                "message": f"ターゲット特許 {target_patent_number} が検索結果に含まれていません",
                "analysis": analysis,
                "suggestions": self._generate_suggestions(analysis)
            }

    def _analyze_why_not_found(self,
                              target_patent_number: str,
                              search_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        ターゲット特許が見つからなかった原因を分析

        Args:
            target_patent_number: ターゲット特許番号
            search_result: 検索結果

        Returns:
            分析結果の辞書
        """
        # ターゲット特許の情報を取得
        try:
            response = requests.post(
                f"{self.google_patents_api_url}/search",
                json={
                    "keywords": [target_patent_number],
                    "max_results": 1
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("patents"):
                return {
                    "error": "ターゲット特許の情報を取得できませんでした"
                }

            target_patent = data["patents"][0]
            target_cpc = target_patent.get("cpc_codes", [])

            # 検索クエリで使用されたCPCコードと比較
            search_query = search_result.get("search_query", "")
            used_cpc = self._extract_cpc_from_query(search_query)

            # 共通CPCコードを確認
            common_cpc = list(set(target_cpc) & set(used_cpc))

            return {
                "target_cpc_codes": target_cpc[:10],
                "search_cpc_codes": used_cpc,
                "common_cpc_codes": common_cpc,
                "cpc_overlap_rate": len(common_cpc) / max(len(target_cpc), 1) if target_cpc else 0
            }

        except Exception as e:
            logger.error(f"Failed to analyze target patent: {e}")
            return {
                "error": str(e)
            }

    def _extract_cpc_from_query(self, query: str) -> List[str]:
        """
        検索クエリからCPCコードを抽出

        Args:
            query: 検索クエリ文字列

        Returns:
            CPCコードのリスト
        """
        import re
        cpc_pattern = r'CPC="([^"]+)"'
        matches = re.findall(cpc_pattern, query)
        return matches


    def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """
        改善提案を生成

        Args:
            analysis: 分析結果

        Returns:
            改善提案のリスト
        """
        suggestions = []

        if "error" in analysis:
            suggestions.append("ターゲット特許の情報取得に失敗しました。特許番号を確認してください。")
            return suggestions

        cpc_overlap_rate = analysis.get("cpc_overlap_rate", 0)

        if cpc_overlap_rate == 0:
            suggestions.append("⚠️ 検索クエリのCPCコードとターゲット特許のCPCコードに重複がありません")
            suggestions.append("💡 予備検索で取得するCPCコードの数を増やしてください (3個 → 10個)")
            suggestions.append("💡 リコール重視モードを使用してください")
        elif cpc_overlap_rate < 0.3:
            suggestions.append("⚠️ CPCコードの重複率が低いです（{:.1%}）".format(cpc_overlap_rate))
            suggestions.append("💡 階層的検索戦略を使用してください（上位分類を含める）")
        else:
            suggestions.append("ℹ️ CPCコードは部分的に一致しています（{:.1%}）".format(cpc_overlap_rate))
            suggestions.append("💡 キーワードマッチングの条件を緩和してください（AND → OR）")

        # ターゲット特許のCPCを表示
        target_cpc = analysis.get("target_cpc_codes", [])
        if target_cpc:
            suggestions.append(f"📊 ターゲット特許のCPCコード（上位10個）: {', '.join(target_cpc[:10])}")

        # 検索クエリで使用されたCPCを表示
        search_cpc = analysis.get("search_cpc_codes", [])
        if search_cpc:
            suggestions.append(f"📊 検索クエリのCPCコード: {', '.join(search_cpc)}")

        # 共通CPCを表示
        common_cpc = analysis.get("common_cpc_codes", [])
        if common_cpc:
            suggestions.append(f"✅ 共通CPCコード: {', '.join(common_cpc)}")
        else:
            suggestions.append("❌ 共通CPCコードなし - CPCコードの拡張が必要です")

        return suggestions
