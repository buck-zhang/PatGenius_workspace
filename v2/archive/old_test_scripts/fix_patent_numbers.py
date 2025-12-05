#!/usr/bin/env python3
"""
特許番号の末尾「A」自動除去ツール

日本特許の公開番号はJP○○○○○○○○○○形式であり、末尾の「A」は不要。
PatentField APIで検索する際は「A」を除去する必要がある。
"""

import re

def normalize_patent_number(patent_number: str) -> str:
    """
    特許番号を正規化（末尾のAを除去）

    Args:
        patent_number: 特許番号（例: JP2014089440A）

    Returns:
        正規化された特許番号（例: JP2014089440）

    Examples:
        >>> normalize_patent_number("JP2014089440A")
        'JP2014089440'
        >>> normalize_patent_number("JP2014089440")
        'JP2014089440'
        >>> normalize_patent_number("JP2011032263A")
        'JP2011032263'
    """
    # 末尾のAを除去（JPで始まり、数字が続き、末尾がAの場合）
    pattern = r'^(JP\d+)A$'
    match = re.match(pattern, patent_number)

    if match:
        return match.group(1)
    else:
        return patent_number


def test_normalization():
    """正規化のテスト"""
    test_cases = [
        ("JP2014089440A", "JP2014089440"),
        ("JP2014089440", "JP2014089440"),
        ("JP2011032263A", "JP2011032263"),
        ("JP2012040876A", "JP2012040876"),
        ("JP2013224028A", "JP2013224028"),
    ]

    print("特許番号正規化テスト")
    print("="*60)

    for input_num, expected in test_cases:
        result = normalize_patent_number(input_num)
        status = "✓" if result == expected else "✗"
        print(f"{status} {input_num:20s} → {result:20s} (期待: {expected})")


if __name__ == '__main__':
    test_normalization()
