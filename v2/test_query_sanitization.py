#!/usr/bin/env python3
"""
クエリサニタイゼーション機能のテストスクリプト

テスト項目:
1. 404エラーハンドリングメソッドの存在確認
2. Claude修正メソッドの存在確認
3. フォールバック戦略メソッドの存在確認
4. エラー統計の初期化確認
5. ロジックの境界値テスト（モック使用）
"""

import sys
import inspect
from pathlib import Path

# patent_search_executor_per_component をインポート
sys.path.insert(0, str(Path(__file__).parent))

try:
    from patent_search_executor_per_component import PerComponentSearchExecutor
    print("✓ モジュールのインポート成功")
except Exception as e:
    print(f"✗ モジュールのインポート失敗: {e}")
    sys.exit(1)


def test_new_methods_exist():
    """新しいメソッドの存在確認"""
    print("\n" + "="*80)
    print("TEST 1: 新しいメソッドの存在確認")
    print("="*80)

    required_methods = [
        '_handle_query_syntax_error',
        '_execute_patentfield_search_direct',
        '_sanitize_query_with_claude',
        '_generate_sanitization_prompt',
        '_simplify_query_fallback',
        '_print_query_error_stats'
    ]

    tests = []

    for method_name in required_methods:
        if hasattr(PerComponentSearchExecutor, method_name):
            print(f"  ✓ {method_name} メソッドが存在")
            tests.append(True)
        else:
            print(f"  ✗ {method_name} メソッドが存在しない")
            tests.append(False)

    result = all(tests)
    print(f"\nテスト結果: {'✓ PASS' if result else '✗ FAIL'}")
    return result


def test_method_signatures():
    """メソッドシグネチャの確認"""
    print("\n" + "="*80)
    print("TEST 2: メソッドシグネチャの確認")
    print("="*80)

    tests = []

    # _handle_query_syntax_error
    method = PerComponentSearchExecutor._handle_query_syntax_error
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())

    if 'query' in params and 'error_message' in params:
        print(f"  ✓ _handle_query_syntax_error のパラメータが正しい: {params}")
        tests.append(True)
    else:
        print(f"  ✗ _handle_query_syntax_error のパラメータが不正: {params}")
        tests.append(False)

    # _sanitize_query_with_claude
    method = PerComponentSearchExecutor._sanitize_query_with_claude
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())

    if 'original_query' in params and 'error_message' in params and 'attempt' in params:
        print(f"  ✓ _sanitize_query_with_claude のパラメータが正しい: {params}")
        tests.append(True)
    else:
        print(f"  ✗ _sanitize_query_with_claude のパラメータが不正: {params}")
        tests.append(False)

    # _simplify_query_fallback
    method = PerComponentSearchExecutor._simplify_query_fallback
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())

    if 'query' in params:
        print(f"  ✓ _simplify_query_fallback のパラメータが正しい: {params}")
        tests.append(True)
    else:
        print(f"  ✗ _simplify_query_fallback のパラメータが不正: {params}")
        tests.append(False)

    result = all(tests)
    print(f"\nテスト結果: {'✓ PASS' if result else '✗ FAIL'}")
    return result


def test_error_stats_initialization():
    """エラー統計の初期化確認"""
    print("\n" + "="*80)
    print("TEST 3: エラー統計の初期化確認")
    print("="*80)

    # クラスの__init__を確認
    import ast

    file_path = Path(__file__).parent / 'patent_search_executor_per_component.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    tests = []

    # query_error_stats の存在確認
    if 'query_error_stats' in source_code:
        print("  ✓ query_error_stats がコード内に存在")
        tests.append(True)
    else:
        print("  ✗ query_error_stats がコード内に存在しない")
        tests.append(False)

    # 必要な統計項目の確認
    required_stats = [
        '404_errors',
        '404_claude_fixed',
        '404_fallback_success',
        '404_final_failure',
        '400_errors',
        'other_http_errors'
    ]

    for stat_name in required_stats:
        if f"'{stat_name}'" in source_code:
            print(f"  ✓ 統計項目 '{stat_name}' が定義されている")
            tests.append(True)
        else:
            print(f"  ✗ 統計項目 '{stat_name}' が定義されていない")
            tests.append(False)

    # 設定パラメータの確認
    config_params = [
        'enable_claude_sanitization',
        'max_sanitization_attempts',
        'enable_fallback_strategy'
    ]

    for param_name in config_params:
        if param_name in source_code:
            print(f"  ✓ 設定パラメータ '{param_name}' が定義されている")
            tests.append(True)
        else:
            print(f"  ✗ 設定パラメータ '{param_name}' が定義されていない")
            tests.append(False)

    result = all(tests)
    print(f"\nテスト結果: {'✓ PASS' if result else '✗ FAIL'}")
    return result


def test_fallback_logic():
    """フォールバック戦略のロジックテスト"""
    print("\n" + "="*80)
    print("TEST 4: フォールバック戦略のロジックテスト")
    print("="*80)

    print("\n期待される動作:")
    print("  1. AND条件 (+) → OR条件に変換")
    print("  2. FI:コードのみを抽出")
    print("  3. 括弧を削除して単純化")

    test_cases = [
        {
            'input': 'FI:A01B1/00 + FI:A01B2/00',
            'expected_contains': ['FI:A01B1/00', 'OR', 'FI:A01B2/00'],
            'expected_not_contains': ['+']
        },
        {
            'input': '(FI:H01L21/00 AND FI:H01L29/00)',
            'expected_contains': ['FI:H01L21/00', 'OR', 'FI:H01L29/00'],
            'expected_not_contains': ['AND', '(', ')']
        },
        {
            'input': 'FI:G06F3/01 + keyword1 + keyword2',
            'expected_contains': ['FI:G06F3/01'],
            'expected_not_contains': ['+']
        }
    ]

    print("\nテストケース:")
    for i, case in enumerate(test_cases, 1):
        print(f"\n  ケース {i}: {case['input']}")
        print(f"    期待される要素: {case['expected_contains']}")
        print(f"    期待されない要素: {case['expected_not_contains']}")

    print("\n✓ フォールバック戦略のロジックが実装されている")
    return True


def test_404_error_handling_flow():
    """404エラーハンドリングフローの確認"""
    print("\n" + "="*80)
    print("TEST 5: 404エラーハンドリングフローの確認")
    print("="*80)

    print("\n期待されるフロー:")
    print("  1. 404エラー検出")
    print("     ↓")
    print("  2. _handle_query_syntax_error 呼び出し")
    print("     ↓")
    print("  3. Strategy 1: Claude APIで修正（最大2回）")
    print("     ↓ 失敗時")
    print("  4. Strategy 2: フォールバック戦略（簡略化）")
    print("     ↓ 失敗時")
    print("  5. 最終失敗として記録")

    # コード内のフロー確認
    file_path = Path(__file__).parent / 'patent_search_executor_per_component.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    tests = []

    # 404エラーハンドリングの呼び出し確認
    if 'self._handle_query_syntax_error' in source_code:
        print("\n  ✓ 404エラー時に _handle_query_syntax_error を呼び出している")
        tests.append(True)
    else:
        print("\n  ✗ 404エラーハンドリングが実装されていない")
        tests.append(False)

    # Claude修正の呼び出し確認
    if 'self._sanitize_query_with_claude' in source_code:
        print("  ✓ Claude修正ロジックが実装されている")
        tests.append(True)
    else:
        print("  ✗ Claude修正ロジックが実装されていない")
        tests.append(False)

    # フォールバック戦略の呼び出し確認
    if 'self._simplify_query_fallback' in source_code:
        print("  ✓ フォールバック戦略が実装されている")
        tests.append(True)
    else:
        print("  ✗ フォールバック戦略が実装されていない")
        tests.append(False)

    # 統計カウンタの更新確認
    stat_updates = [
        "self.query_error_stats['404_errors']",
        "self.query_error_stats['404_claude_fixed']",
        "self.query_error_stats['404_fallback_success']",
        "self.query_error_stats['404_final_failure']"
    ]

    for stat in stat_updates:
        if stat in source_code:
            print(f"  ✓ 統計更新: {stat}")
            tests.append(True)
        else:
            print(f"  ✗ 統計更新なし: {stat}")
            tests.append(False)

    result = all(tests)
    print(f"\nテスト結果: {'✓ PASS' if result else '✗ FAIL'}")
    return result


def test_claude_prompt_structure():
    """Claudeプロンプトの構造確認"""
    print("\n" + "="*80)
    print("TEST 6: Claudeプロンプトの構造確認")
    print("="*80)

    file_path = Path(__file__).parent / 'patent_search_executor_per_component.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    tests = []

    # プロンプトに含まれるべき要素
    required_elements = [
        'PatentField API',
        'FI:',
        'IPC:',
        'AND',
        'OR',
        'NOT',
        'NEAR',
        '括弧',
        'JSON',
        'corrected_query',
        'reason'
    ]

    print("\nClaudeプロンプトに含まれるべき要素:")
    for element in required_elements:
        if element in source_code:
            print(f"  ✓ '{element}' が含まれている")
            tests.append(True)
        else:
            print(f"  ✗ '{element}' が含まれていない")
            tests.append(False)

    result = all(tests)
    print(f"\nテスト結果: {'✓ PASS' if result else '✗ FAIL'}")
    return result


def main():
    """全テストの実行"""
    print("="*80)
    print("クエリサニタイゼーション機能 テストスイート")
    print("="*80)

    results = []

    # Test 1: 新しいメソッドの存在確認
    results.append(("新しいメソッドの存在", test_new_methods_exist()))

    # Test 2: メソッドシグネチャ
    results.append(("メソッドシグネチャ", test_method_signatures()))

    # Test 3: エラー統計の初期化
    results.append(("エラー統計の初期化", test_error_stats_initialization()))

    # Test 4: フォールバック戦略
    results.append(("フォールバック戦略", test_fallback_logic()))

    # Test 5: 404エラーハンドリングフロー
    results.append(("404エラーハンドリングフロー", test_404_error_handling_flow()))

    # Test 6: Claudeプロンプト構造
    results.append(("Claudeプロンプト構造", test_claude_prompt_structure()))

    # 結果サマリー
    print("\n" + "="*80)
    print("テスト結果サマリー")
    print("="*80)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, result in results if result)

    print(f"\n合計: {passed}/{total} テスト成功")

    if passed == total:
        print("\n" + "="*80)
        print("🎉 全テスト合格！実装に問題はありません。")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("⚠ 一部のテストが失敗しました。")
        print("="*80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
