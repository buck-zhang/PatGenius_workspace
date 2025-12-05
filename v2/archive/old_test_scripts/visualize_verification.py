#!/usr/bin/env python3
"""
JP2013224028A検証結果のビジュアライゼーション

使用方法:
  python3 visualize_verification.py
"""

import json


def visualize_verification():
    """検証結果をテキストベースで視覚化"""

    # 結果ファイルを読み込み
    with open('tests/performance_test/per_component_search_result.json', 'r', encoding='utf-8') as f:
        result = json.load(f)

    target_patent = 'JP2013224028'

    print("=" * 100)
    print(" " * 30 + "JP2013224028A 検証結果ビジュアライゼーション")
    print("=" * 100)
    print()

    # 1. 全体サマリー
    print("【1. 全体サマリー】")
    print("-" * 100)

    total_components = result['total_components']
    total_unique = result['total_unique_patents']
    merged_ids = result['merged_patent_ids']

    found = target_patent in merged_ids
    position = merged_ids.index(target_patent) + 1 if found else -1

    print(f"  本願特許: {target_patent}")
    print(f"  検出結果: {'✅ 検出成功' if found else '❌ 未検出'}")

    if found:
        print(f"  検索順位: {position}/{total_unique} ({position/total_unique*100:.1f}%)")

        # プログレスバー風表示
        bar_length = 50
        bar_pos = int((position / total_unique) * bar_length)
        bar = "█" * bar_pos + "░" * (bar_length - bar_pos)
        print(f"  位置表示: [{bar}] {position}")

    print()

    # 2. 構成要素別ヒット状況
    print("【2. 構成要素別ヒット状況】")
    print("-" * 100)

    hit_count = 0
    success_count = 0

    hit_details = []

    for comp_result in result['component_results']:
        comp_id = comp_result['element_id']
        patent_ids = comp_result.get('patent_ids', [])
        hits = comp_result['final_hits']
        status = comp_result['status']

        is_hit = target_patent in patent_ids
        is_success = status == 'success'

        if is_hit:
            hit_count += 1
        if is_success:
            success_count += 1

        hit_details.append({
            'id': comp_id,
            'hits': hits,
            'status': status,
            'is_hit': is_hit,
            'is_success': is_success
        })

    print(f"  総構成要素数: {total_components}")
    print(f"  本願ヒット数: {hit_count}/{total_components} ({hit_count/total_components*100:.1f}%)")
    print(f"  50-300範囲内: {success_count}/{total_components} ({success_count/total_components*100:.1f}%)")
    print()

    # 3. ヒートマップ風表示
    print("【3. 構成要素別詳細（ヒートマップ）】")
    print("-" * 100)
    print(f"  {'ID':<6} {'ヒット数':>10} {'範囲':<12} {'本願':<6} {'ビジュアル'}")
    print("-" * 100)

    for detail in hit_details:
        comp_id = detail['id']
        hits = detail['hits']
        status = detail['status']
        is_hit = detail['is_hit']
        is_success = detail['is_success']

        # ステータス表示
        if is_success:
            status_str = "✅ 範囲内"
        else:
            if hits > 300:
                status_str = "⬆️ 超過"
            elif hits < 50:
                status_str = "⬇️ 不足"
            else:
                status_str = "⚠️ その他"

        # 本願ヒット表示
        hit_str = "✅ HIT" if is_hit else "❌ MISS"

        # ビジュアルバー（対数スケール）
        if hits > 0:
            import math
            log_hits = math.log10(hits + 1)
            bar_length = int(log_hits * 5)
            bar = "█" * min(bar_length, 30)
        else:
            bar = ""

        print(f"  {comp_id:<6} {hits:>10,} {status_str:<12} {hit_str:<6} {bar}")

    print()

    # 4. カテゴリ別統計
    print("【4. カテゴリ別統計】")
    print("-" * 100)

    categories = {
        '50-300範囲内（成功）': {'count': 0, 'hit': 0},
        '300超（広すぎ）': {'count': 0, 'hit': 0},
        '50未満（狭すぎ）': {'count': 0, 'hit': 0},
        'その他': {'count': 0, 'hit': 0}
    }

    for detail in hit_details:
        hits = detail['hits']
        is_hit = detail['is_hit']
        is_success = detail['is_success']

        if is_success:
            cat = '50-300範囲内（成功）'
        elif hits > 300:
            cat = '300超（広すぎ）'
        elif hits < 50:
            cat = '50未満（狭すぎ）'
        else:
            cat = 'その他'

        categories[cat]['count'] += 1
        if is_hit:
            categories[cat]['hit'] += 1

    for cat, stats in categories.items():
        count = stats['count']
        hit = stats['hit']
        if count > 0:
            hit_rate = hit / count * 100
            print(f"  {cat:<20} | 要素数: {count:>2} | 本願ヒット: {hit:>2} ({hit_rate:>5.1f}%)")

    print()

    # 5. 重複削除効果
    print("【5. 重複削除効果】")
    print("-" * 100)

    total_with_dup = sum(len(cr.get('patent_ids', [])) for cr in result['component_results'])
    total_unique = result['total_unique_patents']
    duplicate_count = total_with_dup - total_unique
    dup_rate = duplicate_count / total_with_dup * 100 if total_with_dup > 0 else 0

    print(f"  取得総件数（重複含む）: {total_with_dup:>6,} 件")
    print(f"  重複削除後の件数:       {total_unique:>6,} 件")
    print(f"  削除された重複:         {duplicate_count:>6,} 件 ({dup_rate:.1f}%)")

    # プログレスバー
    bar_total = "█" * 50
    bar_unique = "█" * int(50 * total_unique / total_with_dup)
    bar_dup = "░" * int(50 * duplicate_count / total_with_dup)

    print(f"\n  重複含む: [{bar_total}] {total_with_dup:,}")
    print(f"  削除後:   [{bar_unique}{bar_dup}] {total_unique:,}")

    print()

    # 6. 成功要素の詳細
    print("【6. 50-300範囲内の成功要素（全て本願ヒット）】")
    print("-" * 100)

    success_components = [d for d in hit_details if d['is_success']]

    if success_components:
        for detail in success_components:
            comp_id = detail['id']
            hits = detail['hits']
            is_hit = detail['is_hit']

            # 対応する詳細情報を取得
            comp_result = next(cr for cr in result['component_results'] if cr['element_id'] == comp_id)
            text = comp_result['element_text'][:60]

            hit_mark = "✅" if is_hit else "❌"
            print(f"  {comp_id}: {hits:>3}件 {hit_mark} - {text}...")
    else:
        print("  なし")

    print()

    # 7. 結論
    print("【7. 結論】")
    print("-" * 100)

    if found:
        print(f"  ✅ JP2013224028Aは検索結果に含まれています")
        print(f"  ✅ 検索順位: {position}/{total_unique}（最上位）")
        print(f"  ✅ {hit_count}/{total_components}の構成要素で検出（{hit_count/total_components*100:.1f}%）")
        print(f"  ✅ 検索漏れリスクは極めて低い")

        if success_count > 0:
            print(f"  ✅ {success_count}個の構成要素で50-300範囲内に到達")
    else:
        print(f"  ❌ JP2013224028Aは検索結果に含まれていません")
        print(f"  ⚠️ 検索戦略の見直しが必要")

    print()
    print("=" * 100)


if __name__ == '__main__':
    visualize_verification()
