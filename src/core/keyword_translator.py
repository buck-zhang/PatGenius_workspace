"""
キーワード翻訳モジュール
Keyword Translation Module

日本語キーワードと英語キーワードを統合して、より広範な検索を実現します。
"""

from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)


class KeywordTranslator:
    """キーワード翻訳・拡張クラス"""

    # 技術用語の日英対応辞書
    TECHNICAL_TERMS = {
        # 半導体・メモリ関連
        "酸化物半導体": ["oxide semiconductor", "oxide", "IGZO", "metal oxide"],
        "容量素子": ["capacitor", "storage capacitor", "holding capacitor", "retention capacitor"],
        "トランジスタ": ["transistor", "TFT", "thin film transistor"],
        "オフ電流": ["off current", "off-state current", "leakage current", "leakage"],
        "メモリ": ["memory", "storage"],
        "記憶": ["memory", "storage", "retention"],
        "記憶装置": ["memory device", "storage device"],
        "データ": ["data"],
        "電荷": ["charge", "electric charge"],
        "保持": ["retention", "holding", "maintaining"],
        "フリップフロップ": ["flip-flop", "FF"],
        "シフトレジスタ": ["shift register", "SR"],

        # 回路・素子関連
        "回路": ["circuit"],
        "素子": ["element", "device"],
        "配線": ["wiring", "wire", "interconnect"],
        "電極": ["electrode"],
        "絶縁膜": ["insulating film", "insulator", "insulation layer"],
        "半導体膜": ["semiconductor film", "semiconductor layer"],
        "ゲート": ["gate"],
        "ソース": ["source"],
        "ドレイン": ["drain"],
        "チャネル": ["channel"],

        # メモリセル・構造関連
        "メモリセル": ["memory cell", "storage cell"],
        "セル": ["cell"],
        "アレイ": ["array"],
        "ノード": ["node"],
        "ビット線": ["bit line", "BL"],
        "ワード線": ["word line", "WL"],
        "データ線": ["data line"],

        # 動作・機能関連
        "書き込み": ["write", "writing"],
        "読み出し": ["read", "reading"],
        "消去": ["erase", "erasing"],
        "選択": ["selection", "select"],
        "駆動": ["drive", "driving"],
        "制御": ["control", "controlling"],
        "スイッチング": ["switching"],

        # 材料関連
        "酸化物": ["oxide"],
        "シリコン": ["silicon", "Si"],
        "金属": ["metal"],
        "導電性": ["conductive", "conductivity"],
        "絶縁性": ["insulating", "insulation"],

        # 特性関連
        "低リーク": ["low leakage", "ultra-low leakage"],
        "高速": ["high speed", "fast"],
        "低消費電力": ["low power consumption", "low power"],
        "不揮発性": ["non-volatile", "nonvolatile"],
        "揮発性": ["volatile"],

        # 表示装置関連
        "表示装置": ["display device", "display"],
        "液晶": ["liquid crystal", "LCD"],
        "画素": ["pixel"],
        "走査線": ["scan line", "scanning line"],
        "信号線": ["signal line"],
    }

    @staticmethod
    def translate_keyword(japanese_keyword: str) -> List[str]:
        """
        日本語キーワードを英語に翻訳

        Args:
            japanese_keyword: 日本語キーワード

        Returns:
            英語キーワードのリスト
        """
        # 完全一致で検索
        if japanese_keyword in KeywordTranslator.TECHNICAL_TERMS:
            return KeywordTranslator.TECHNICAL_TERMS[japanese_keyword]

        # 部分一致で検索
        translations = []
        for jp_term, en_terms in KeywordTranslator.TECHNICAL_TERMS.items():
            if jp_term in japanese_keyword or japanese_keyword in jp_term:
                translations.extend(en_terms)

        # 重複削除して返す
        return list(set(translations))

    @staticmethod
    def expand_keywords_bilingual(japanese_keywords: List[str],
                                  max_translations_per_keyword: int = 2) -> List[str]:
        """
        日本語キーワードリストを英語キーワードで拡張

        Args:
            japanese_keywords: 日本語キーワードリスト
            max_translations_per_keyword: 各キーワードの最大翻訳数

        Returns:
            日本語+英語の統合キーワードリスト
        """
        expanded = []

        for jp_keyword in japanese_keywords:
            # 元の日本語キーワードを追加
            expanded.append(jp_keyword)

            # 英訳を追加
            translations = KeywordTranslator.translate_keyword(jp_keyword)
            if translations:
                # 最大翻訳数まで追加
                expanded.extend(translations[:max_translations_per_keyword])

        # 重複削除して返す
        return list(dict.fromkeys(expanded))  # 順序を保持しながら重複削除

    @staticmethod
    def build_bilingual_keyword_query(keywords: List[str],
                                     max_keywords: int = 5,
                                     max_translations_per_keyword: int = 2) -> str:
        """
        日英統合キーワード検索式を生成

        Args:
            keywords: キーワードリスト（日本語）
            max_keywords: 使用する最大キーワード数
            max_translations_per_keyword: 各キーワードの最大翻訳数

        Returns:
            検索式文字列（例: ("メモリ" OR "memory" OR "storage") OR ("トランジスタ" OR "transistor" OR "TFT")）
        """
        if not keywords:
            return ""

        keyword_groups = []

        for jp_keyword in keywords[:max_keywords]:
            # このキーワードのグループ（日本語 OR 英語1 OR 英語2 ...）
            group = [f'"{jp_keyword}"']

            # 英訳を追加
            translations = KeywordTranslator.translate_keyword(jp_keyword)
            if translations:
                for trans in translations[:max_translations_per_keyword]:
                    group.append(f'"{trans}"')

            # グループを括弧で囲んでOR結合
            if len(group) > 1:
                keyword_groups.append(f"({' OR '.join(group)})")
            else:
                keyword_groups.append(group[0])

        # 全グループをOR結合
        if keyword_groups:
            return " OR ".join(keyword_groups)
        else:
            return ""

    @staticmethod
    def add_term(japanese_term: str, english_terms: List[str]):
        """
        新しい技術用語を辞書に追加

        Args:
            japanese_term: 日本語用語
            english_terms: 英語用語のリスト
        """
        KeywordTranslator.TECHNICAL_TERMS[japanese_term] = english_terms
        logger.info(f"Added new term: {japanese_term} → {english_terms}")

    @staticmethod
    def get_all_terms() -> Dict[str, List[str]]:
        """
        全ての技術用語を取得

        Returns:
            技術用語辞書
        """
        return KeywordTranslator.TECHNICAL_TERMS.copy()


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("キーワード翻訳モジュールのテスト")
    print("=" * 80)

    # テスト1: 単一キーワードの翻訳
    print("\n【テスト1】単一キーワードの翻訳")
    print("-" * 80)
    test_keywords = ["酸化物半導体", "容量素子", "トランジスタ", "メモリセル"]
    for kw in test_keywords:
        translations = KeywordTranslator.translate_keyword(kw)
        print(f"{kw:15} → {translations}")

    # テスト2: バイリンガル拡張
    print("\n【テスト2】バイリンガル拡張")
    print("-" * 80)
    jp_keywords = ["酸化物半導体", "容量素子", "オフ電流"]
    expanded = KeywordTranslator.expand_keywords_bilingual(jp_keywords, max_translations_per_keyword=2)
    print(f"元のキーワード: {jp_keywords}")
    print(f"拡張後: {expanded}")

    # テスト3: 検索式生成
    print("\n【テスト3】バイリンガル検索式生成")
    print("-" * 80)
    query = KeywordTranslator.build_bilingual_keyword_query(jp_keywords, max_keywords=3, max_translations_per_keyword=2)
    print(f"検索式:\n{query}")

    # テスト4: 技術用語の数
    print("\n【テスト4】登録されている技術用語")
    print("-" * 80)
    all_terms = KeywordTranslator.get_all_terms()
    print(f"登録用語数: {len(all_terms)}")
    print(f"カテゴリ例:")
    print(f"  - 半導体・メモリ: 酸化物半導体, 容量素子, トランジスタ...")
    print(f"  - 回路・素子: 回路, 素子, 配線...")
    print(f"  - 動作・機能: 書き込み, 読み出し, 消去...")

    print("\n" + "=" * 80)
    print("✓ キーワード翻訳モジュールのテスト完了")
    print("=" * 80)
