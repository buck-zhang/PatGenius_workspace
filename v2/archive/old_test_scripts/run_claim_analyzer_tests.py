#!/usr/bin/env python3
"""
claim_analyzer.pyの簡易テストランナー

pytestなしで関数の動作を検証します。
"""

import json
import sys
from pathlib import Path
from claim_analyzer import identify_independent_claims, identify_core_elements


def test_identify_independent_claims():
    """独立請求項識別のテスト"""
    print("\n=== Test: identify_independent_claims ===")

    # Test 1: 基本テスト
    elements = [
        {'構成要素番号': '1a', 'claim_type': 'independent'},
        {'構成要素番号': '1b', 'claim_type': 'dependent'},
        {'構成要素番号': '2a', 'claim_type': 'independent'},
    ]
    result = identify_independent_claims(elements)
    expected = ['1a', '2a']
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 1 passed: 基本的な独立請求項抽出 - {result}")

    # Test 2: 独立請求項なし
    elements = [
        {'構成要素番号': '1b', 'claim_type': 'dependent'},
        {'構成要素番号': '1c', 'claim_type': 'dependent'},
    ]
    result = identify_independent_claims(elements)
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 2 passed: 独立請求項なし - {result}")

    # Test 3: 全て独立請求項
    elements = [
        {'構成要素番号': '1a', 'claim_type': 'independent'},
        {'構成要素番号': '2a', 'claim_type': 'independent'},
        {'構成要素番号': '3a', 'claim_type': 'independent'},
    ]
    result = identify_independent_claims(elements)
    expected = ['1a', '2a', '3a']
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 3 passed: 全て独立請求項 - {result}")

    # Test 4: 空リスト
    elements = []
    result = identify_independent_claims(elements)
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 4 passed: 空リスト - {result}")

    print("✓ identify_independent_claims: 全テストパス")


def test_identify_core_elements():
    """コア要素識別のテスト"""
    print("\n=== Test: identify_core_elements ===")

    # Test 1: 基本テスト
    elements = [
        {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
        {'構成要素番号': '1b', '構成要素の重要度': 0.95, 'is_core_element': False},
        {'構成要素番号': '1d', '構成要素の重要度': 1.0, 'is_core_element': True},
    ]
    result = identify_core_elements(elements)
    expected = ['1a', '1d']
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 1 passed: 基本的なコア要素抽出 - {result}")

    # Test 2: 重要度閾値チェック
    elements = [
        {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
        {'構成要素番号': '1b', '構成要素の重要度': 0.94, 'is_core_element': True},  # 閾値未満
        {'構成要素番号': '1c', '構成要素の重要度': 0.95, 'is_core_element': True},  # 閾値ちょうど
    ]
    result = identify_core_elements(elements, importance_threshold=0.95)
    expected = ['1a', '1c']
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 2 passed: 重要度閾値0.95 - {result}")

    # Test 3: コアフラグFalse
    elements = [
        {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
        {'構成要素番号': '1b', '構成要素の重要度': 1.0, 'is_core_element': False},
    ]
    result = identify_core_elements(elements)
    expected = ['1a']
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 3 passed: コアフラグFalse除外 - {result}")

    # Test 4: コア要素なし
    elements = [
        {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': False},
        {'構成要素番号': '1b', '構成要素の重要度': 0.95, 'is_core_element': False},
    ]
    result = identify_core_elements(elements)
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 4 passed: コア要素なし - {result}")

    # Test 5: 空リスト
    elements = []
    result = identify_core_elements(elements)
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✓ Test 5 passed: 空リスト - {result}")

    print("✓ identify_core_elements: 全テストパス")


def test_with_enhanced_json():
    """拡張JSONファイルとの統合テスト"""
    print("\n=== Test: Enhanced JSON Integration ===")

    json_path = Path('tests/test_構成要件_ENHANCED.json')
    if not json_path.exists():
        print(f"⚠ テストファイルが見つかりません: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    elements = data['構成要件']

    # 独立請求項の抽出テスト
    independent = identify_independent_claims(elements)
    print(f"  独立請求項: {independent}")
    assert '1a' in independent, "1a should be independent"
    assert '2a' in independent, "2a should be independent"
    assert '1b' not in independent, "1b should NOT be independent"
    print("  ✓ 独立請求項の抽出: 正常")

    # コア要素の抽出テスト
    core = identify_core_elements(elements)
    print(f"  コア要素: {core}")
    assert '1a' in core, "1a should be core (importance=1.0, is_core=True)"
    assert '1d' in core, "1d should be core (importance=1.0, is_core=True)"
    assert '1b' not in core, "1b should NOT be core (is_core=False)"
    assert '2a' not in core, "2a should NOT be core (is_core=False)"
    print("  ✓ コア要素の抽出: 正常")

    print("✓ Enhanced JSON統合テスト: 全テストパス")


def main():
    """全テスト実行"""
    print("=" * 80)
    print("claim_analyzer.py テスト実行")
    print("=" * 80)

    test_count = 0
    passed = 0

    try:
        test_identify_independent_claims()
        test_count += 1
        passed += 1
    except AssertionError as e:
        print(f"✗ identify_independent_claims テスト失敗: {e}")
        test_count += 1

    try:
        test_identify_core_elements()
        test_count += 1
        passed += 1
    except AssertionError as e:
        print(f"✗ identify_core_elements テスト失敗: {e}")
        test_count += 1

    try:
        test_with_enhanced_json()
        test_count += 1
        passed += 1
    except AssertionError as e:
        print(f"✗ Enhanced JSON統合テスト失敗: {e}")
        test_count += 1

    print("\n" + "=" * 80)
    print(f"テスト結果: {passed}/{test_count} passed")
    print("=" * 80)

    if passed == test_count:
        print("\n✓ 全テストパス！")
        return 0
    else:
        print(f"\n✗ {test_count - passed} 件のテストが失敗しました")
        return 1


if __name__ == '__main__':
    sys.exit(main())
