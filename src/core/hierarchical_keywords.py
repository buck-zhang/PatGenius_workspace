"""
階層的キーワードシステム
Hierarchical Keyword System

キーワードを3つの階層に分類して、検索範囲に応じて適切なレベルを使用します。
- Level 1 (Broad): 上位概念（記憶装置、半導体、回路）
- Level 2 (Medium): 中位概念（トランジスタ、メモリセル、電荷保持）
- Level 3 (Narrow): 詳細概念（酸化物半導体、容量素子、オフ電流）
"""

from typing import List, Dict, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class HierarchicalKeyword:
    """階層的キーワードデータクラス"""
    broad: List[str]      # Level 1: 上位概念
    medium: List[str]     # Level 2: 中位概念
    narrow: List[str]     # Level 3: 詳細概念


class HierarchicalKeywordSystem:
    """階層的キーワードシステム"""

    # 技術領域ごとの階層的キーワード定義
    KEYWORD_HIERARCHY = {
        # ========================================
        # メモリ・記憶装置関連
        # ========================================
        "memory_storage": HierarchicalKeyword(
            broad=[
                "記憶", "memory", "storage",
                "データ保持", "data retention",
                "情報記憶", "information storage"
            ],
            medium=[
                "メモリ", "メモリセル", "memory cell",
                "記憶装置", "storage device", "memory device",
                "データ記憶", "data storage",
                "不揮発性メモリ", "non-volatile memory",
                "揮発性メモリ", "volatile memory"
            ],
            narrow=[
                "フラッシュメモリ", "flash memory",
                "DRAM", "SRAM", "MRAM",
                "ReRAM", "PRAM",
                "記憶容量", "storage capacity",
                "メモリアレイ", "memory array"
            ]
        ),

        # ========================================
        # 半導体・トランジスタ関連
        # ========================================
        "semiconductor_transistor": HierarchicalKeyword(
            broad=[
                "半導体", "semiconductor",
                "電子素子", "electronic device",
                "能動素子", "active device"
            ],
            medium=[
                "トランジスタ", "transistor",
                "薄膜トランジスタ", "TFT", "thin film transistor",
                "電界効果トランジスタ", "FET", "field effect transistor",
                "半導体素子", "semiconductor element"
            ],
            narrow=[
                "酸化物半導体", "oxide semiconductor",
                "IGZO", "In-Ga-Zn-O",
                "酸化物TFT", "oxide TFT",
                "金属酸化物半導体", "metal oxide semiconductor",
                "アモルファス酸化物", "amorphous oxide"
            ]
        ),

        # ========================================
        # 回路・スイッチング関連
        # ========================================
        "circuit_switching": HierarchicalKeyword(
            broad=[
                "回路", "circuit",
                "電気回路", "electrical circuit",
                "スイッチング", "switching"
            ],
            medium=[
                "論理回路", "logic circuit",
                "フリップフロップ", "flip-flop", "FF",
                "シフトレジスタ", "shift register", "SR",
                "ラッチ回路", "latch circuit",
                "スイッチ回路", "switch circuit"
            ],
            narrow=[
                "CMOS回路", "CMOS circuit",
                "インバータ回路", "inverter circuit",
                "Dフリップフロップ", "D flip-flop",
                "ダイナミックラッチ", "dynamic latch",
                "パストランジスタ", "pass transistor"
            ]
        ),

        # ========================================
        # 容量・電荷保持関連
        # ========================================
        "capacitor_charge": HierarchicalKeyword(
            broad=[
                "電荷", "charge", "electric charge",
                "保持", "retention", "holding",
                "蓄積", "accumulation", "storage"
            ],
            medium=[
                "容量素子", "capacitor",
                "記憶容量", "storage capacitor",
                "保持容量", "retention capacitor",
                "電荷保持", "charge retention",
                "キャパシタ", "capacitance"
            ],
            narrow=[
                "蓄積容量", "storage capacity",
                "保持キャパシタ", "holding capacitor",
                "ノード容量", "node capacitance",
                "寄生容量", "parasitic capacitance",
                "カップリング容量", "coupling capacitance"
            ]
        ),

        # ========================================
        # リーク電流・特性関連
        # ========================================
        "leakage_characteristics": HierarchicalKeyword(
            broad=[
                "電流", "current",
                "リーク", "leakage", "leak",
                "特性", "characteristics"
            ],
            medium=[
                "オフ電流", "off current", "off-state current",
                "リーク電流", "leakage current",
                "サブスレッショルド電流", "subthreshold current",
                "低リーク", "low leakage"
            ],
            narrow=[
                "100zA以下", "ultra-low leakage",
                "ゼプトアンペア", "zeptoampere", "zA",
                "極低リーク", "extremely low leakage",
                "サブアトアンペア", "sub-attoampere"
            ]
        ),

        # ========================================
        # 表示装置関連
        # ========================================
        "display": HierarchicalKeyword(
            broad=[
                "表示", "display",
                "画像表示", "image display",
                "ディスプレイ", "display device"
            ],
            medium=[
                "表示装置", "display device",
                "液晶表示", "LCD", "liquid crystal display",
                "有機EL", "OLED", "organic EL",
                "画素回路", "pixel circuit"
            ],
            narrow=[
                "駆動回路", "driver circuit", "driving circuit",
                "走査線駆動回路", "scan line driver",
                "信号線駆動回路", "signal line driver",
                "画素スイッチ", "pixel switch",
                "ゲートドライバ", "gate driver"
            ]
        ),

        # ========================================
        # データ制御・信号処理関連
        # ========================================
        "data_control": HierarchicalKeyword(
            broad=[
                "データ", "data",
                "信号", "signal",
                "制御", "control"
            ],
            medium=[
                "データ制御", "data control",
                "信号処理", "signal processing",
                "データ転送", "data transfer",
                "書き込み", "write", "writing",
                "読み出し", "read", "reading"
            ],
            narrow=[
                "データ線", "data line",
                "ビット線", "bit line", "BL",
                "ワード線", "word line", "WL",
                "選択信号", "selection signal",
                "制御信号", "control signal"
            ]
        ),

        # ========================================
        # 構造・材料関連
        # ========================================
        "structure_material": HierarchicalKeyword(
            broad=[
                "構造", "structure",
                "材料", "material",
                "層", "layer"
            ],
            medium=[
                "半導体層", "semiconductor layer",
                "絶縁層", "insulating layer", "insulation layer",
                "導電層", "conductive layer",
                "ゲート絶縁膜", "gate insulating film",
                "チャネル層", "channel layer"
            ],
            narrow=[
                "酸化物半導体層", "oxide semiconductor layer",
                "In-Ga-Zn-O層", "IGZO layer",
                "ゲート酸化膜", "gate oxide",
                "層間絶縁膜", "interlayer insulating film",
                "金属配線", "metal wiring"
            ]
        ),

        # ========================================
        # 電極・配線関連
        # ========================================
        "electrode_wiring": HierarchicalKeyword(
            broad=[
                "電極", "electrode",
                "配線", "wiring", "wire",
                "接続", "connection"
            ],
            medium=[
                "ゲート電極", "gate electrode", "gate",
                "ソース電極", "source electrode", "source",
                "ドレイン電極", "drain electrode", "drain",
                "配線層", "wiring layer",
                "導電層", "conductive layer"
            ],
            narrow=[
                "金属電極", "metal electrode",
                "透明電極", "transparent electrode",
                "画素電極", "pixel electrode",
                "共通電極", "common electrode",
                "Al配線", "aluminum wiring"
            ]
        ),

        # ========================================
        # 動作・機能関連
        # ========================================
        "operation_function": HierarchicalKeyword(
            broad=[
                "動作", "operation",
                "機能", "function",
                "駆動", "drive", "driving"
            ],
            medium=[
                "スイッチング動作", "switching operation",
                "オンオフ制御", "on-off control",
                "データ保持動作", "data retention operation",
                "書き込み動作", "write operation",
                "読み出し動作", "read operation"
            ],
            narrow=[
                "高速スイッチング", "high-speed switching",
                "低消費電力動作", "low power operation",
                "リフレッシュ動作", "refresh operation",
                "プリチャージ動作", "precharge operation",
                "イコライズ動作", "equalize operation"
            ]
        )
    }

    @staticmethod
    def get_keywords_by_level(level: int = 2, domains: List[str] = None) -> List[str]:
        """
        指定された階層レベルのキーワードを取得

        Args:
            level: 階層レベル (1=broad, 2=medium, 3=narrow)
            domains: 対象とする技術領域リスト（Noneの場合は全領域）

        Returns:
            キーワードリスト
        """
        keywords = []

        # 対象領域を決定
        target_domains = domains if domains else list(HierarchicalKeywordSystem.KEYWORD_HIERARCHY.keys())

        for domain in target_domains:
            if domain not in HierarchicalKeywordSystem.KEYWORD_HIERARCHY:
                logger.warning(f"Unknown domain: {domain}")
                continue

            hierarchy = HierarchicalKeywordSystem.KEYWORD_HIERARCHY[domain]

            if level == 1:
                keywords.extend(hierarchy.broad)
            elif level == 2:
                keywords.extend(hierarchy.medium)
            elif level == 3:
                keywords.extend(hierarchy.narrow)

        # 重複削除
        return list(dict.fromkeys(keywords))

    @staticmethod
    def expand_keywords_hierarchical(base_keywords: List[str],
                                    current_level: int = 2,
                                    target_level: int = 2) -> List[str]:
        """
        基本キーワードを階層的に拡張

        Args:
            base_keywords: 基本キーワードリスト
            current_level: 現在の階層レベル
            target_level: 目標階層レベル（1=broad, 2=medium, 3=narrow）

        Returns:
            拡張されたキーワードリスト
        """
        if current_level == target_level:
            return base_keywords

        expanded = list(base_keywords)

        # キーワードを各技術領域にマッピング
        for keyword in base_keywords:
            for domain, hierarchy in HierarchicalKeywordSystem.KEYWORD_HIERARCHY.items():
                # どの階層にキーワードが含まれているか確認
                if keyword in hierarchy.narrow:
                    # narrow → medium → broad へ拡張
                    if target_level <= 2:
                        expanded.extend(hierarchy.medium)
                    if target_level <= 1:
                        expanded.extend(hierarchy.broad)
                elif keyword in hierarchy.medium:
                    # medium → broad or narrow
                    if target_level <= 1:
                        expanded.extend(hierarchy.broad)
                    elif target_level >= 3:
                        expanded.extend(hierarchy.narrow)
                elif keyword in hierarchy.broad:
                    # broad → medium → narrow
                    if target_level >= 2:
                        expanded.extend(hierarchy.medium)
                    if target_level >= 3:
                        expanded.extend(hierarchy.narrow)

        # 重複削除して返す
        return list(dict.fromkeys(expanded))

    @staticmethod
    def build_hierarchical_keyword_query(keywords: List[str],
                                        hierarchy_level: int = 2,
                                        max_keywords: int = 10) -> str:
        """
        階層的キーワード検索式を生成

        Args:
            keywords: キーワードリスト
            hierarchy_level: 階層レベル (1=broad, 2=medium, 3=narrow)
            max_keywords: 使用する最大キーワード数

        Returns:
            検索式文字列
        """
        # 階層レベルに応じて拡張
        expanded_keywords = HierarchicalKeywordSystem.expand_keywords_hierarchical(
            keywords, current_level=3, target_level=hierarchy_level
        )

        # 重複削除と制限
        unique_keywords = list(dict.fromkeys(expanded_keywords))[:max_keywords]

        # OR条件で結合
        if unique_keywords:
            return " OR ".join([f'"{kw}"' for kw in unique_keywords])
        else:
            return ""

    @staticmethod
    def get_domain_suggestions(keywords: List[str]) -> Dict[str, float]:
        """
        キーワードから関連する技術領域を推定

        Args:
            keywords: キーワードリスト

        Returns:
            {domain: relevance_score} の辞書
        """
        domain_scores = {}

        for domain, hierarchy in HierarchicalKeywordSystem.KEYWORD_HIERARCHY.items():
            score = 0.0
            all_domain_keywords = hierarchy.broad + hierarchy.medium + hierarchy.narrow

            for keyword in keywords:
                if keyword in all_domain_keywords:
                    # narrow=3点, medium=2点, broad=1点
                    if keyword in hierarchy.narrow:
                        score += 3.0
                    elif keyword in hierarchy.medium:
                        score += 2.0
                    elif keyword in hierarchy.broad:
                        score += 1.0

            if score > 0:
                domain_scores[domain] = score

        return domain_scores

    @staticmethod
    def get_all_domains() -> List[str]:
        """全ての技術領域を取得"""
        return list(HierarchicalKeywordSystem.KEYWORD_HIERARCHY.keys())


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("階層的キーワードシステムのテスト")
    print("=" * 80)

    # テスト1: レベル別キーワード取得
    print("\n【テスト1】レベル別キーワード取得（memory_storage領域）")
    print("-" * 80)
    for level in [1, 2, 3]:
        keywords = HierarchicalKeywordSystem.get_keywords_by_level(
            level=level, domains=["memory_storage"]
        )
        level_names = {1: "Broad (上位概念)", 2: "Medium (中位概念)", 3: "Narrow (詳細概念)"}
        print(f"\nLevel {level} - {level_names[level]}:")
        print(f"  {keywords[:5]}...")  # 最初の5つのみ表示

    # テスト2: 階層的拡張
    print("\n【テスト2】階層的キーワード拡張")
    print("-" * 80)
    base_keywords = ["酸化物半導体", "容量素子", "オフ電流"]
    print(f"基本キーワード: {base_keywords}")

    for target_level in [1, 2, 3]:
        expanded = HierarchicalKeywordSystem.expand_keywords_hierarchical(
            base_keywords, current_level=3, target_level=target_level
        )
        level_names = {1: "Broad", 2: "Medium", 3: "Narrow"}
        print(f"\nTarget Level {target_level} ({level_names[target_level]}):")
        print(f"  拡張後: {len(expanded)}個のキーワード")
        print(f"  例: {expanded[:5]}...")

    # テスト3: 検索式生成
    print("\n【テスト3】階層的検索式生成")
    print("-" * 80)
    test_keywords = ["メモリセル", "トランジスタ", "電荷保持"]

    for level in [1, 2, 3]:
        query = HierarchicalKeywordSystem.build_hierarchical_keyword_query(
            test_keywords, hierarchy_level=level, max_keywords=10
        )
        level_names = {1: "Broad", 2: "Medium", 3: "Narrow"}
        print(f"\nLevel {level} ({level_names[level]}):")
        print(f"  {query[:150]}...")

    # テスト4: 技術領域推定
    print("\n【テスト4】技術領域推定")
    print("-" * 80)
    test_keywords = ["IGZO", "メモリセル", "フリップフロップ", "液晶表示"]
    domain_scores = HierarchicalKeywordSystem.get_domain_suggestions(test_keywords)
    print(f"入力キーワード: {test_keywords}")
    print(f"\n推定される技術領域:")
    for domain, score in sorted(domain_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {domain:30} : {score:.1f}点")

    print("\n" + "=" * 80)
    print("✓ 階層的キーワードシステムのテスト完了")
    print("=" * 80)
