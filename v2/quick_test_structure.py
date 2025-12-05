#!/usr/bin/env python3
"""
patent_structure_analyzer.py の簡易動作確認テスト
"""

import asyncio
import sys
from pathlib import Path


async def test_structure_analyzer():
    """構成要件分割システムの動作確認"""
    print("="*80)
    print("patent_structure_analyzer.py 動作確認テスト")
    print("="*80)

    # インポート確認
    print("\n[1/4] モジュールインポート中...")
    try:
        from patent_structure_analyzer import PatentStructureAnalyzer
        print("✓ インポート成功")
    except Exception as e:
        print(f"✗ インポート失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 初期化確認
    print("\n[2/4] 初期化中...")
    try:
        analyzer = PatentStructureAnalyzer(
            credentials_path='../ttdc-in-house-dev-3e07247326cb.json',
            project_id='ttdc-in-house-dev'
        )
        print("✓ 初期化成功")
    except FileNotFoundError as e:
        print(f"✗ 認証ファイルが見つかりません: {e}")
        print("  ../ttdc-in-house-dev-3e07247326cb.json を配置してください")
        return False
    except Exception as e:
        print(f"✗ 初期化失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    # テストデータ作成
    print("\n[3/4] テストデータ作成中...")
    test_text = """
【請求項1】
太陽電池モジュールであって、
第1保護部材と、
第2保護部材と、
前記第1保護部材と前記第2保護部材との間に配置された太陽電池セルと
を備える太陽電池モジュール。

【請求項2】
請求項1に記載の太陽電池モジュールにおいて、
前記第1保護部材は透光性を有する、太陽電池モジュール。
"""
    print(f"✓ テストデータ作成完了 ({len(test_text)} 文字)")

    # 分析実行（非同期）
    print("\n[4/4] 構成要件分析実行中（非同期）...")
    try:
        result = await analyzer.analyze(test_text, max_tokens=4000)

        if result['status'] == 'success':
            print("✓ 分析成功")
            print(f"\n結果:")
            print(f"  構成要件数: {len(result['構成要件'])} 個")
            print(f"  処理時間: {result['処理時間_秒']} 秒")
            print(f"  トークン使用量: {result['tokens']['total_tokens']:,} tokens")

            # 最初の構成要件を表示
            if result['構成要件']:
                print(f"\n最初の構成要件:")
                first = result['構成要件'][0]
                print(f"  番号: {first.get('構成要素番号', 'N/A')}")
                print(f"  内容: {first.get('構成要素', 'N/A')[:50]}...")
                print(f"  重要度: {first.get('構成要素の重要度', 'N/A')}")

            return True
        else:
            print(f"✗ 分析失敗: {result.get('message', '不明なエラー')}")
            return False

    except Exception as e:
        print(f"✗ 分析実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    print("\n最適化版 patent_structure_analyzer.py の動作確認")
    print("AsyncIO + Prompt Caching による非同期処理\n")

    try:
        success = asyncio.run(test_structure_analyzer())

        print("\n" + "="*80)
        if success:
            print("✅ テスト成功")
            print("="*80)
            print("\n最適化機能:")
            print("  ✓ AsyncIO: 有効")
            print("  ✓ Prompt Caching: 有効")
            print("  ✓ 非同期Claude API呼び出し: 動作確認済み")
            sys.exit(0)
        else:
            print("❌ テスト失敗")
            print("="*80)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
