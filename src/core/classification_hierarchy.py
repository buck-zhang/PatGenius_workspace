"""
分類コードの階層的処理モジュール
Classification Code Hierarchical Processing Module

このモジュールは、CPC/FI分類コードの階層構造を活用して、
より柔軟で効果的な特許検索を実現します。

Hierarchy Levels:
- Level 0: Section (セクション) - 例: H, G
- Level 1: Class (クラス) - 例: H10, G11
- Level 2: Subclass (サブクラス) - 例: H10D, G11C
- Level 3: Maingroup (メイングループ) - 例: H10D30, G11C11
- Level 4: Full code (完全コード) - 例: H10D30/00, G11C11/56
"""

from typing import List, Set, Dict
import re


class ClassificationHierarchy:
    """分類コードの階層構造を管理するクラス"""

    @staticmethod
    def extract_hierarchy_levels(code: str) -> Dict[str, str]:
        """
        分類コードから各階層レベルを抽出

        Args:
            code: CPC/FI分類コード (例: "H10D30/00", "G11C11/56 220")

        Returns:
            階層レベルの辞書 {
                "section": "H",
                "class": "H10",
                "subclass": "H10D",
                "maingroup": "H10D30",
                "full": "H10D30/00"
            }
        """
        if not code:
            return {}

        # Clean up the code - remove trailing backslashes and extra spaces
        code = code.strip().replace("\\", "").strip()

        # CPC/FI形式の分類コードをパース
        # Pattern: Letter + 2-3 digits + Letter + digits + optional /digits + optional space + extra
        match = re.match(r'([A-H])(\d{2,3})([A-Z])(\d+)(?:/(\d+))?', code)

        if not match:
            return {}

        section, class_num, subclass_letter, maingroup_num, subgroup = match.groups()

        result = {
            "section": section,
            "class": f"{section}{class_num}",
            "subclass": f"{section}{class_num}{subclass_letter}",
            "maingroup": f"{section}{class_num}{subclass_letter}{maingroup_num}"
        }

        # Add full code if subgroup exists
        if subgroup:
            result["full"] = f"{section}{class_num}{subclass_letter}{maingroup_num}/{subgroup}"
        else:
            result["full"] = f"{section}{class_num}{subclass_letter}{maingroup_num}"

        return result

    @staticmethod
    def build_hierarchical_query(codes: List[str], level: int = 2) -> str:
        """
        指定された階層レベルで検索式を生成

        Args:
            codes: 分類コードのリスト
            level: 階層レベル
                0 = section (H*, G* など)
                1 = class (H10*, G11* など)
                2 = subclass (H10D*, G11C* など) - デフォルト
                3 = maingroup (H10D30*, G11C11* など)
                4 = full (完全一致)

        Returns:
            検索式文字列 (例: 'CPC="G11C*" OR CPC="H10D*"')
        """
        if not codes:
            return ""

        level_map = {
            0: "section",
            1: "class",
            2: "subclass",
            3: "maingroup",
            4: "full"
        }

        if level == 4:
            # 完全一致の場合
            unique_codes = set([code.strip().replace("\\", "").strip() for code in codes])
            return " OR ".join([f'CPC="{code}"' for code in sorted(unique_codes)])

        # 指定レベルの分類を抽出
        level_key = level_map.get(level)
        if not level_key:
            return ""

        level_codes = set()
        for code in codes:
            hierarchy = ClassificationHierarchy.extract_hierarchy_levels(code)
            if level_key in hierarchy:
                level_codes.add(hierarchy[level_key])

        # ワイルドカード検索式を生成
        if not level_codes:
            return ""

        # Sort for consistency
        sorted_codes = sorted(level_codes)

        # Google Patents syntax:
        # - Upper level classifications (section, class, subclass): use lowercase 'cpc=' without quotes
        # - Full codes with '/' (e.g., G11C11/00): use uppercase 'CPC="..."' with quotes
        # Levels 0-2 (section, class, subclass) use lowercase 'cpc='
        # Level 3 (maingroup) can still use '*' wildcard with CPC="..."
        if level in [0, 1, 2]:
            # Upper level classifications: cpc=CODE (lowercase, no quotes)
            return " OR ".join([f'cpc={code}' for code in sorted_codes])
        else:
            # Level 3 (maingroup): still use wildcard with CPC="..."
            return " OR ".join([f'CPC="{code}*"' for code in sorted_codes])

    @staticmethod
    def find_common_ancestors(codes: List[str]) -> Dict[str, Set[str]]:
        """
        複数の分類コードの共通祖先を見つける

        Args:
            codes: 分類コードのリスト

        Returns:
            各階層レベルでの共通コードのセット
        """
        hierarchies = [
            ClassificationHierarchy.extract_hierarchy_levels(code)
            for code in codes
        ]

        common = {
            "section": set(),
            "class": set(),
            "subclass": set(),
            "maingroup": set()
        }

        for h in hierarchies:
            for key in common.keys():
                if key in h:
                    common[key].add(h[key])

        return common

    @staticmethod
    def get_recommended_level(num_codes: int, target_hits: int = 100) -> int:
        """
        分類コードの数と目標ヒット数に基づいて推奨される階層レベルを返す

        Args:
            num_codes: 分類コードの数
            target_hits: 目標ヒット数

        Returns:
            推奨される階層レベル (0-4)
        """
        # If very few codes, use broader search
        if num_codes <= 2:
            return 1  # Class level
        elif num_codes <= 5:
            return 2  # Subclass level (default)
        elif num_codes <= 10:
            return 3  # Maingroup level
        else:
            return 4  # Full code

    @staticmethod
    def build_progressive_queries(codes: List[str]) -> Dict[str, str]:
        """
        段階的検索用のクエリを生成（Discovery → Refinement → Precision）

        Args:
            codes: 分類コードのリスト

        Returns:
            各段階のクエリを含む辞書
        """
        return {
            "discovery": ClassificationHierarchy.build_hierarchical_query(codes, level=1),
            "refinement": ClassificationHierarchy.build_hierarchical_query(codes, level=2),
            "precision": ClassificationHierarchy.build_hierarchical_query(codes, level=3)
        }


class CPCLateralExpansion:
    """
    CPC分類コードの横方向展開（関連技術領域への拡張）

    特許検索のリコール向上のため、技術的に関連するCPCコードを追加します。
    例：メモリ技術（G11C）→ トランジスタ技術（H10D）→ 論理回路（H03K）
    """

    # 技術分野ごとの関連CPCマップ（共起頻度が高いCPCコードの組み合わせ）
    RELATED_CPC_MAP = {
        # メモリ・記憶装置 (Memory & Storage)
        "G11C": ["H10D86", "H10D30", "H03K3", "H03K19", "H10B41", "H10B12", "G06F12"],
        "G11C11": ["H10D86", "H10D30", "H03K3"],  # Specific memory types
        "G11C7": ["H10D86", "H03K3", "H03K19"],   # Memory readout circuits

        # 薄膜トランジスタ (Thin Film Transistors)
        "H10D86": ["G11C", "G11C11", "G09G3", "H10D30", "H10B41"],
        "H10D30": ["H10D86", "G11C", "G09G3", "H10B12"],

        # ディスプレイ (Display Devices)
        "G09G": ["H10D86", "H10D30", "G02F1", "H01L27"],
        "G09G3": ["H10D86", "H10D30", "G02F1"],  # Display control circuits

        # 論理回路・パルス技術 (Logic Circuits & Pulse Technology)
        "H03K": ["G11C", "G11C11", "H10D86", "H10B41"],
        "H03K3": ["G11C11", "H10D86", "H03K19"],  # Pulse circuits
        "H03K19": ["G11C7", "H10D86", "H03K3"],   # Logic circuits

        # 半導体メモリ構造 (Semiconductor Memory Structures)
        "H10B": ["G11C", "H10D86", "H10D30"],
        "H10B41": ["G11C", "G11C11", "H10D86", "H03K"],  # DRAM
        "H10B12": ["G11C", "H10D30"],  # SRAM

        # 半導体装置 (Semiconductor Devices)
        "H01L": ["H10D86", "H10D30", "G11C", "G09G"],
        "H01L27": ["G09G", "H10D86", "G11C"],  # Integrated circuits
        "H01L29": ["H10D86", "H10D30"],  # Transistor structures
    }

    @staticmethod
    def expand_cpc_codes(cpc_codes: List[str], max_expansion: int = 5) -> List[str]:
        """
        入力されたCPCコードに関連する技術領域のCPCコードを追加

        Args:
            cpc_codes: 元のCPCコードリスト
            max_expansion: 各CPCコードから追加する最大関連コード数

        Returns:
            拡張されたCPCコードリスト（元のコード + 関連コード）
        """
        if not cpc_codes:
            return []

        expanded = set(cpc_codes)  # 元のコードを保持

        for code in cpc_codes:
            # Extract subclass level (e.g., "G11C11/56" → "G11C11", "G11C")
            hierarchy = ClassificationHierarchy.extract_hierarchy_levels(code)

            # Try maingroup first, then subclass
            search_keys = []
            if "maingroup" in hierarchy:
                search_keys.append(hierarchy["maingroup"])
            if "subclass" in hierarchy:
                search_keys.append(hierarchy["subclass"])

            # Find related CPCs
            for key in search_keys:
                if key in CPCLateralExpansion.RELATED_CPC_MAP:
                    related = CPCLateralExpansion.RELATED_CPC_MAP[key]
                    # Add up to max_expansion related codes
                    for related_code in related[:max_expansion]:
                        expanded.add(related_code)
                    break  # Use the most specific match

        return sorted(list(expanded))

    @staticmethod
    def build_expanded_query(cpc_codes: List[str], hierarchy_level: int = 2,
                            enable_lateral: bool = True) -> str:
        """
        横方向展開を含む拡張検索式を生成

        Args:
            cpc_codes: CPCコードリスト
            hierarchy_level: 階層レベル (0-4)
            enable_lateral: 横方向展開を有効化

        Returns:
            拡張された検索式
        """
        if not cpc_codes:
            return ""

        # Lateral expansion if enabled
        if enable_lateral:
            expanded_codes = CPCLateralExpansion.expand_cpc_codes(cpc_codes, max_expansion=1)
        else:
            expanded_codes = cpc_codes

        # Build hierarchical query with expanded codes
        return ClassificationHierarchy.build_hierarchical_query(
            expanded_codes, level=hierarchy_level
        )


class HybridClassificationStrategy:
    """FIとCPCを統合した検索戦略"""

    @staticmethod
    def build_hybrid_query(
        fi_codes: List[str],
        cpc_codes: List[str],
        strategy: str = "inclusive",
        hierarchy_level: int = 2
    ) -> str:
        """
        FIとCPCを統合した検索式を生成

        Args:
            fi_codes: FIコードのリスト
            cpc_codes: CPCコードのリスト
            strategy: 統合戦略
                - "inclusive": FI OR CPC (広く検索、Recall重視)
                - "intersection": FI AND CPC (狭く検索、Precision重視)
                - "cpc_only": CPCのみ使用
                - "fi_only": FIのみ使用
            hierarchy_level: 分類コードの階層レベル

        Returns:
            統合された検索式
        """
        cpc_query = ClassificationHierarchy.build_hierarchical_query(
            cpc_codes, level=hierarchy_level
        ) if cpc_codes else ""

        fi_query = ClassificationHierarchy.build_hierarchical_query(
            fi_codes, level=hierarchy_level
        ) if fi_codes else ""

        if strategy == "cpc_only":
            return cpc_query
        elif strategy == "fi_only":
            return fi_query
        elif strategy == "inclusive":
            if cpc_query and fi_query:
                return f"({cpc_query}) OR ({fi_query})"
            return cpc_query or fi_query
        elif strategy == "intersection":
            if cpc_query and fi_query:
                return f"({cpc_query}) AND ({fi_query})"
            return cpc_query or fi_query
        else:
            return cpc_query or fi_query


# Example usage and testing
if __name__ == "__main__":
    # Test extraction
    test_codes = [
        "H10D30/00",
        "H10D86/00",
        "G11C11/56 220",
        "G11C19/00"
    ]

    print("=== Hierarchy Extraction Test ===")
    for code in test_codes:
        hierarchy = ClassificationHierarchy.extract_hierarchy_levels(code)
        print(f"{code}: {hierarchy}")

    print("\n=== Hierarchical Query Generation Test ===")
    for level in range(5):
        query = ClassificationHierarchy.build_hierarchical_query(test_codes, level=level)
        print(f"Level {level}: {query}")

    print("\n=== Progressive Queries Test ===")
    progressive = ClassificationHierarchy.build_progressive_queries(test_codes)
    for stage, query in progressive.items():
        print(f"{stage}: {query}")

    print("\n=== Common Ancestors Test ===")
    common = ClassificationHierarchy.find_common_ancestors(test_codes)
    print(f"Common ancestors: {common}")
