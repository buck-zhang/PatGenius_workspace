#!/usr/bin/env python3
"""
PatentField特許検索実行システム

構成要件のキーワードと特許分類コードを統合し、PatentField APIで
検索漏れを最小化する戦略的検索を実行します。

検索戦略：
1. 各構成要素を軸にした個別検索
2. 軸 = 特許分類コード（FI + Fterm + IPC）のOR演算
3. 補強 = 他の構成要素のキーワードのAND演算
4. ヒット件数10-300件を目標に段階的調整
5. 全文データ（請求の範囲、詳細な説明、図面）取得
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import time


class PatentSearchExecutor:
    """特許検索実行システム"""

    def __init__(
        self,
        keywords_file: str,
        classifications_file: str,
        patentfield_key_path: str = "../patentfield_key.json"
    ):
        """
        初期化

        Args:
            keywords_file: キーワードJSONファイルパス
            classifications_file: 特許分類JSONファイルパス
            patentfield_key_path: PatentField APIキーファイルパス
        """
        # データ読み込み
        with open(keywords_file, 'r', encoding='utf-8') as f:
            self.keywords_data = json.load(f)

        with open(classifications_file, 'r', encoding='utf-8') as f:
            self.classifications_data = json.load(f)

        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        # 統合データ構築
        self.integrated_data = self._integrate_data()

        print("✓ PatentField API設定読み込み完了")
        print(f"✓ キーワードデータ読み込み完了: {len(self.keywords_data['keywords'])}要素")
        print(f"✓ 分類コードデータ読み込み完了: 4分類タイプ")
        print(f"✓ 統合データ構築完了: {len(self.integrated_data)}要素\n")

    def _integrate_data(self) -> Dict:
        """
        キーワードと分類コードを構成要素番号で統合

        Returns:
            統合データ辞書 {
                '1a': {
                    'element_text': '...',
                    'importance': 0.95,
                    'keywords': {
                        'ドンピシャ': [...],
                        '上位概念': [...],
                        '下位概念': [...]
                    },
                    'classifications': {
                        'FI': {'ドンピシャ': [...], ...},
                        'Fterm': {...},
                        'IPC': {...},
                        'CPC': {...}
                    }
                }
            }
        """
        integrated = {}

        # キーワードデータをベースに構築
        for kw_item in self.keywords_data['keywords']:
            element_id = kw_item['構成要素番号']

            integrated[element_id] = {
                'element_text': kw_item['構成要素'],
                'importance': kw_item['重要度'],
                'keywords': {
                    'ドンピシャ': [kw['keyword'] for kw in kw_item.get('ドンピシャキーワード_日本語', [])[:5]],
                    '上位概念': [kw['keyword'] for kw in kw_item.get('上位概念キーワード_日本語', [])[:5]],
                    '下位概念': [kw['keyword'] for kw in kw_item.get('下位概念キーワード_日本語', [])[:5]]
                },
                'classifications': {}
            }

        # 分類コードを統合（構成要素番号が明示されていないため、全要素に共通付与）
        # 実際には構成要素ごとに異なる分類を持つべきだが、現状のデータ構造では全体分類のみ
        classifications = self.classifications_data.get('classifications', {})

        for element_id in integrated.keys():
            integrated[element_id]['classifications'] = {}

            for class_type in ['FI', 'Fterm', 'IPC', 'CPC']:
                if class_type in classifications:
                    integrated[element_id]['classifications'][class_type] = {
                        'ドンピシャ': [
                            item['code']
                            for item in classifications[class_type].get('ドンピシャ', [])
                        ][:10],  # 上位10件
                        '上位概念': [
                            item['code']
                            for item in classifications[class_type].get('上位概念', [])
                        ][:5],
                        '下位概念': [
                            item['code']
                            for item in classifications[class_type].get('下位概念', [])
                        ][:5]
                    }

        return integrated

    def _build_classification_query(
        self,
        element_id: str,
        concept_level: str = 'ドンピシャ'
    ) -> str:
        """
        特許分類コードのOR演算クエリを構築

        Args:
            element_id: 構成要素番号
            concept_level: 'ドンピシャ' | '上位概念' | '下位概念'

        Returns:
            検索式（例：'FI:H01L27/108 OR FI:H01L29/786 OR Fterm:5F110AA06'）
        """
        element = self.integrated_data[element_id]
        classifications = element['classifications']

        query_parts = []

        # FI分類
        fi_codes = classifications.get('FI', {}).get(concept_level, [])
        for code in fi_codes[:5]:  # 最大5件
            query_parts.append(f'FI:{code}')

        # Fterm分類
        fterm_codes = classifications.get('Fterm', {}).get(concept_level, [])
        for code in fterm_codes[:5]:  # 最大5件
            query_parts.append(f'FT:{code}')

        # IPC分類
        ipc_codes = classifications.get('IPC', {}).get(concept_level, [])
        for code in ipc_codes[:3]:  # 最大3件
            query_parts.append(f'IPC:{code}')

        if not query_parts:
            return ""

        # OR演算で統合（括弧で囲む）
        return '(' + ' OR '.join(query_parts) + ')'

    def _build_keyword_query(
        self,
        element_ids: List[str],
        concept_level: str = 'ドンピシャ',
        max_keywords: int = 5
    ) -> str:
        """
        キーワードのOR演算クエリを構築

        Args:
            element_ids: キーワード抽出対象の構成要素番号リスト
            concept_level: 'ドンピシャ' | '上位概念' | '下位概念'
            max_keywords: 最大キーワード数

        Returns:
            検索式（例：'CL:(論理回路 OR トランジスタ OR 容量素子)'）
        """
        keywords = []

        for element_id in element_ids:
            element = self.integrated_data.get(element_id, {})
            kws = element.get('keywords', {}).get(concept_level, [])
            keywords.extend(kws)

        # 重複排除と上位選択
        unique_keywords = list(dict.fromkeys(keywords))[:max_keywords]

        if not unique_keywords:
            return ""

        # 全文検索（プレフィックスなし）でOR演算
        return '(' + ' OR '.join(unique_keywords) + ')'

    def _parse_classification_hierarchy(self, code: str, class_type: str) -> Dict:
        """
        分類コードの階層構造を解析

        IPC/FI階層構造:
        - B41J (セクション+クラス)
        - B41J2 (サブクラス)
        - B41J2/01 (メイングループ)
        - B41J2/14 (サブグループ1)
        - B41J2/14501 (サブグループ2, FIのみ)

        Args:
            code: 分類コード (例: "B41J2/14501")
            class_type: 'IPC' | 'FI' | 'Fterm'

        Returns:
            {
                'levels': ['B41J', 'B41J2', 'B41J2/14', 'B41J2/14501'],
                'current_level': 3,
                'base_code': 'B41J2/14501'
            }
        """
        if class_type == 'Fterm':
            # Ftermは階層構造が異なるため、そのまま返す
            return {
                'levels': [code],
                'current_level': 0,
                'base_code': code
            }

        # IPC/FI の階層パース
        levels = []

        # レベル0: セクション+クラス (B41J)
        if len(code) >= 4:
            levels.append(code[:4])

        # レベル1: サブクラス (B41J2)
        if len(code) >= 5:
            # B41J2 または B41J02 の形式
            subclass = code[:5] if code[4:5].isdigit() else code[:4] + code[4:5]
            levels.append(subclass)

        # レベル2以降: メイングループ/サブグループ (/)で分割
        if '/' in code:
            parts = code.split('/')
            base = parts[0]

            # メイングループ全体 (B41J2/01)
            if len(parts) > 1:
                main_group = base + '/' + parts[1].split('.')[0][:2]
                if main_group not in levels:
                    levels.append(main_group)

                # サブグループ (B41J2/14)
                if len(parts[1]) > 2:
                    sub_group = base + '/' + parts[1][:2]
                    if sub_group not in levels and sub_group != main_group:
                        levels.append(sub_group)

                # 完全なコード (B41J2/14501)
                if code not in levels:
                    levels.append(code)

        return {
            'levels': levels,
            'current_level': len(levels) - 1,
            'base_code': code
        }

    def _build_classification_query_with_wildcard(
        self,
        element_id: str,
        hierarchy_shift: int = 0,
        concept_level: str = 'ドンピシャ'
    ) -> str:
        """
        階層レベルを指定してワイルドカード付き分類コードクエリを構築

        Args:
            element_id: 構成要素番号
            hierarchy_shift: 階層シフト量
                - 負の値: 上位階層へ移動(拡大方向)
                - 正の値: 下位階層へ移動(縮小方向)
                - 0: 現在の階層
            concept_level: 'ドンピシャ' | '上位概念' | '下位概念'

        Returns:
            検索式 (例: '(FI:B41J2. OR IPC:B41J2/14.)')

        Examples:
            # 元のコード: B41J2/14501
            hierarchy_shift = -2: B41J2.  (2階層上がってワイルドカード)
            hierarchy_shift = -1: B41J2/14.  (1階層上がってワイルドカード)
            hierarchy_shift = 0: B41J2/14501  (元のまま)
            hierarchy_shift = +1: 使用不可(これより下位がない)
        """
        element = self.integrated_data[element_id]
        classifications = element['classifications']

        query_parts = []

        # FI分類
        fi_codes = classifications.get('FI', {}).get(concept_level, [])
        for code in fi_codes[:5]:
            hierarchy = self._parse_classification_hierarchy(code, 'FI')
            levels = hierarchy['levels']
            current_level = hierarchy['current_level']

            target_level = current_level + hierarchy_shift

            if target_level < 0:
                target_level = 0
            elif target_level >= len(levels):
                target_level = len(levels) - 1

            target_code = levels[target_level]

            # ワイルドカード付与（拡大方向の場合）
            if hierarchy_shift < 0 and not target_code.endswith('.'):
                target_code = target_code + '.'

            query_parts.append(f'FI:{target_code}')

        # IPC分類
        ipc_codes = classifications.get('IPC', {}).get(concept_level, [])
        for code in ipc_codes[:3]:
            hierarchy = self._parse_classification_hierarchy(code, 'IPC')
            levels = hierarchy['levels']
            current_level = hierarchy['current_level']

            target_level = current_level + hierarchy_shift

            if target_level < 0:
                target_level = 0
            elif target_level >= len(levels):
                target_level = len(levels) - 1

            target_code = levels[target_level]

            # ワイルドカード付与（拡大方向の場合）
            if hierarchy_shift < 0 and not target_code.endswith('.'):
                target_code = target_code + '.'

            query_parts.append(f'IPC:{target_code}')

        # Fterm分類（階層構造がないのでそのまま）
        fterm_codes = classifications.get('Fterm', {}).get(concept_level, [])
        for code in fterm_codes[:5]:
            query_parts.append(f'FT:{code}')

        if not query_parts:
            return ""

        # OR演算で統合
        return '(' + ' OR '.join(query_parts) + ')'

    def _build_search_query(
        self,
        axis_element_id: str,
        other_element_ids: List[str],
        concept_level: str = 'ドンピシャ',
        use_keywords: bool = True
    ) -> str:
        """
        検索式を構築

        戦略：
        - 軸の構成要素：特許分類のみ（FI + Fterm + IPC）
        - 他の構成要素：キーワードで補強（検索漏れ防止）

        Args:
            axis_element_id: 軸とする構成要素番号
            other_element_ids: 他の構成要素番号リスト
            concept_level: 概念レベル
            use_keywords: キーワード補強を使用するか

        Returns:
            検索式

        Raises:
            ValueError: 分類コードが見つからない場合（分類コードは必須）
        """
        # 軸：特許分類（必須）
        classification_query = self._build_classification_query(
            axis_element_id,
            concept_level
        )

        if not classification_query:
            raise ValueError(
                f"分類コードが見つかりません（分類コードは必須）: "
                f"構成要素={axis_element_id}, 概念レベル={concept_level}"
            )

        # 補強：他要素のキーワード
        if use_keywords and other_element_ids:
            keyword_query = self._build_keyword_query(
                other_element_ids,
                concept_level='ドンピシャ',  # 常にドンピシャキーワード
                max_keywords=3  # 絞り込み
            )

            if keyword_query:
                return f"{classification_query} AND {keyword_query}"

        return classification_query

    def _execute_patentfield_search(
        self,
        query: str,
        limit: int = 100
    ) -> Tuple[int, List[str]]:
        """
        PatentField APIで検索実行

        Args:
            query: 検索式
            limit: 最大取得件数

        Returns:
            (ヒット件数, 特許番号リスト)
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        payload = {
            "search_type": "expert",
            "q": query,
            "columns": ["pub_id"],  # まずは特許番号のみ取得
            "limit": limit
        }

        try:
            response = requests.post(
                self.pf_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            n_hits = data.get('n_hits', 0)

            patent_ids = [
                record['pub_id']
                for record in data.get('records', [])
            ]

            return n_hits, patent_ids

        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTPエラー: {e}")
            print(f"  レスポンス: {e.response.text[:200]}")
            return 0, []
        except Exception as e:
            print(f"  ✗ エラー: {e}")
            return 0, []

    def _search_with_adjustment(
        self,
        axis_element_id: str,
        other_element_ids: List[str],
        target_min: int = 10,
        target_max: int = 300,
        max_attempts: int = 10
    ) -> Dict:
        """
        適応的検索: ヒット件数に応じて動的に階層を調整

        ロジック:
        1. 初回: ドンピシャ分類 + ドンピシャキーワード (hierarchy_shift=0)
        2. <10件: 階層を1つ上げる(拡大) - 最大5回
        3. >300件: キーワード調整で縮小 - 最大5回
        4. 10-300件: 成功、終了

        Args:
            axis_element_id: 軸の構成要素
            other_element_ids: 他の構成要素
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数
            max_attempts: 最大試行回数

        Returns:
            検索結果辞書
        """
        element = self.integrated_data[axis_element_id]

        print(f"\n{'='*80}")
        print(f"構成要素 {axis_element_id}: {element['element_text'][:50]}...")
        print(f"{'='*80}")

        attempts = []
        hierarchy_shift = 0  # 初期: ドンピシャ階層
        expand_count = 0  # 拡大回数
        contract_count = 0  # 縮小回数
        use_keywords = True  # キーワード使用フラグ

        final_query = ""
        final_hits = 0
        final_patent_ids = []

        for attempt in range(max_attempts):
            # 検索式構築（ワイルドカード付き）
            classification_query = self._build_classification_query_with_wildcard(
                axis_element_id,
                hierarchy_shift,
                concept_level='ドンピシャ'
            )

            if not classification_query:
                print(f"  試行{attempt + 1}: 分類コードなし、スキップ")
                break

            keyword_query = ""
            if use_keywords and other_element_ids:
                keyword_query = self._build_keyword_query(
                    other_element_ids,
                    concept_level='ドンピシャ',
                    max_keywords=3
                )

            # 完全な検索式
            if keyword_query:
                query = f"{classification_query} AND {keyword_query}"
            else:
                query = classification_query

            # 戦略説明
            if attempt == 0:
                strategy = "ドンピシャ分類 + ドンピシャキーワード"
            elif expand_count > 0:
                strategy = f"拡大 階層+{abs(hierarchy_shift)} (拡大{expand_count}/5回目)"
            elif contract_count > 0:
                if not use_keywords:
                    strategy = f"縮小 キーワード除外 (縮小{contract_count}/5回目)"
                else:
                    strategy = f"縮小 キーワード調整 (縮小{contract_count}/5回目)"
            else:
                strategy = "現在の階層で検索"

            print(f"\n  試行{attempt + 1}: {strategy}")
            print(f"  階層シフト: {hierarchy_shift}")
            print(f"  検索式: {query[:150]}...")

            # 検索実行
            hits, patent_ids = self._execute_patentfield_search(query)

            attempts.append({
                'attempt': attempt + 1,
                'strategy': strategy,
                'hierarchy_shift': hierarchy_shift,
                'use_keywords': use_keywords,
                'query': query,
                'hits': hits,
                'expand_count': expand_count,
                'contract_count': contract_count
            })

            print(f"  ヒット件数: {hits}件")

            final_query = query
            final_hits = hits
            final_patent_ids = patent_ids

            # 目標範囲内なら終了
            if target_min <= hits <= target_max:
                print(f"  ✓ 目標範囲内（{target_min}-{target_max}件）に到達")
                break

            # 次回の戦略決定
            if hits < target_min and expand_count < 5:
                # 拡大: 階層を1つ上げる
                hierarchy_shift -= 1
                expand_count += 1
                print(f"  → 次回: 階層を1つ上げて拡大（拡大{expand_count}/5回目）")

            elif hits > target_max and contract_count < 5:
                # 縮小: キーワード調整
                if contract_count == 0 and use_keywords:
                    # 最初の縮小: キーワード除外
                    use_keywords = False
                    contract_count += 1
                    print(f"  → 次回: キーワードを除外して縮小（縮小{contract_count}/5回目）")
                else:
                    # これ以上縮小不可、現状維持
                    print(f"  → これ以上の縮小は不可、現状維持")
                    break

            else:
                # 試行上限到達 or これ以上調整不可
                print(f"  → 試行上限到達 or 調整不可、終了")
                break

        return {
            'element_id': axis_element_id,
            'element_text': element['element_text'],
            'importance': element['importance'],
            'attempts': attempts,
            'final_query': final_query,
            'final_hits': final_hits,
            'final_patent_ids': final_patent_ids[:target_max],  # 最大300件
            'status': 'success' if final_hits > 0 else 'no_results'
        }

    def fetch_full_patent_data(
        self,
        patent_id: str
    ) -> Optional[Dict]:
        """
        特許の全文データを取得（別エンドポイント使用）

        Args:
            patent_id: 特許番号（pub_id）

        Returns:
            特許データ辞書 or None
        """
        # PatentField全文取得API: GET /api/v1/patents/{name}
        base_url = self.pf_endpoint.replace('/patents/search', '')
        url = f"{base_url}/patents/{patent_id}"

        headers = {
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        params = {
            'id_type': 'pub_id'
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # 必要なフィールドを抽出
            return {
                'pub_id': patent_id,
                'app_doc_id': data.get('app_doc_id', ''),
                'title': data.get('title', ''),
                'abstract': data.get('abstract', ''),
                'claims': data.get('app_claims', data.get('grant_claims', '')),
                'description': data.get('description', ''),
                'drawings': data.get('drawings', [])
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  ⚠ 特許データなし: {patent_id}")
            else:
                print(f"  ✗ HTTPエラー: {e}")
            return None
        except Exception as e:
            print(f"  ✗ エラー: {e}")
            return None

    def execute(
        self,
        output_file: str,
        target_min: int = 10,
        target_max: int = 300,
        fetch_full_text: bool = False
    ) -> Dict:
        """
        検索実行

        Args:
            output_file: 出力ファイルパス
            target_min: 目標最小ヒット数
            target_max: 目標最大ヒット数
            fetch_full_text: 全文データ取得するか

        Returns:
            実行結果辞書
        """
        print("\n" + "="*80)
        print("PatentField特許検索実行")
        print("="*80)

        # 構成要素リスト（重要度順）
        elements = sorted(
            self.integrated_data.items(),
            key=lambda x: x[1]['importance'],
            reverse=True
        )

        element_ids = [e[0] for e in elements]

        print(f"\n検索対象構成要素: {len(element_ids)}個")
        print(f"目標ヒット件数: {target_min}-{target_max}件")
        print(f"全文データ取得: {'有効' if fetch_full_text else '無効'}\n")

        # 各構成要素を軸にした検索
        constituent_searches = []
        all_patent_ids = set()

        for i, axis_element_id in enumerate(element_ids[:10], 1):  # 上位10要素のみ
            other_element_ids = [
                eid for eid in element_ids
                if eid != axis_element_id
            ][:5]  # 他要素は5個まで

            result = self._search_with_adjustment(
                axis_element_id,
                other_element_ids,
                target_min,
                target_max
            )

            constituent_searches.append(result)
            all_patent_ids.update(result['final_patent_ids'])

            # API制限を考慮して待機
            time.sleep(0.5)

        print("\n" + "="*80)
        print("検索結果集計")
        print("="*80)

        successful = [s for s in constituent_searches if s['status'] == 'success']
        total_hits = sum(s['final_hits'] for s in successful)
        unique_patents = len(all_patent_ids)

        print(f"  成功した検索: {len(successful)}/{len(constituent_searches)}")
        print(f"  総ヒット件数: {total_hits}件")
        print(f"  ユニーク特許数: {unique_patents}件")

        # 全文データ取得（オプション）
        patents_data = []
        if fetch_full_text and all_patent_ids:
            print(f"\n全文データ取得中（{unique_patents}件）...")

            for i, patent_id in enumerate(list(all_patent_ids)[:100], 1):  # 最大100件
                if i % 10 == 0:
                    print(f"  進捗: {i}/{min(unique_patents, 100)}件")

                patent_data = self.fetch_full_patent_data(patent_id)
                if patent_data:
                    # どの構成要素検索にマッチしたか記録
                    matched_elements = [
                        s['element_id']
                        for s in constituent_searches
                        if patent_id in s['final_patent_ids']
                    ]
                    patent_data['matched_elements'] = matched_elements
                    patent_data['relevance_score'] = len(matched_elements) / len(element_ids)

                    patents_data.append(patent_data)

                time.sleep(0.3)  # API制限考慮

        # 結果構築
        result = {
            'status': 'success',
            'search_summary': {
                'total_searches': len(constituent_searches),
                'successful_searches': len(successful),
                'total_hits': total_hits,
                'unique_patents': unique_patents,
                'full_text_retrieved': len(patents_data),
                'target_range': f"{target_min}-{target_max}"
            },
            'constituent_searches': constituent_searches,
            'unique_patent_ids': list(all_patent_ids),
            'patents': patents_data
        }

        # 出力
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 結果を保存: {output_file}")

        return result


def main():
    """コマンドライン実行"""
    import argparse

    parser = argparse.ArgumentParser(
        description='PatentField特許検索実行システム',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python patent_search_executor.py \\
    tests/jp2014007731A_キーワード.json \\
    tests/jp2014007731A_COMPLETE_classification.json

  python patent_search_executor.py \\
    keywords.json classifications.json \\
    --output results.json \\
    --full-text \\
    --min-hits 20 --max-hits 200
        """
    )

    parser.add_argument(
        'keywords_file',
        help='キーワードJSONファイル'
    )
    parser.add_argument(
        'classifications_file',
        help='特許分類JSONファイル'
    )
    parser.add_argument(
        '-o', '--output',
        default='patent_search_results.json',
        help='出力ファイルパス'
    )
    parser.add_argument(
        '--patentfield-key',
        default='../patentfield_key.json',
        help='PatentField APIキーファイル'
    )
    parser.add_argument(
        '--min-hits',
        type=int,
        default=10,
        help='目標最小ヒット数 (default: 10)'
    )
    parser.add_argument(
        '--max-hits',
        type=int,
        default=300,
        help='目標最大ヒット数 (default: 300)'
    )
    parser.add_argument(
        '--full-text',
        action='store_true',
        help='全文データ（請求の範囲、詳細な説明、図面）を取得'
    )

    args = parser.parse_args()

    # 入力ファイル確認
    for filepath in [args.keywords_file, args.classifications_file, args.patentfield_key]:
        if not Path(filepath).exists():
            print(f"エラー: ファイルが見つかりません: {filepath}", file=sys.stderr)
            sys.exit(1)

    try:
        # 実行
        executor = PatentSearchExecutor(
            args.keywords_file,
            args.classifications_file,
            args.patentfield_key
        )

        executor.execute(
            args.output,
            target_min=args.min_hits,
            target_max=args.max_hits,
            fetch_full_text=args.full_text
        )

    except KeyboardInterrupt:
        print("\n\n処理を中断しました", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nエラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
