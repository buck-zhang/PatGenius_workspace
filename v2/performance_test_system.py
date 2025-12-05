#!/usr/bin/env python3
"""
特許構成要件分割・検索システムの性能テスト

combined_data.csvを使用して、本願特許と紐づき特許の検出精度を評価する。

処理フロー:
1. CSVから上位N件を抽出
2. 各本願特許の請求の範囲・詳細な説明をPatentField APIで取得
3. 構成要件分割（Claude Sonnet 4.5）
4. キーワード抽出（Claude Sonnet 4.5）
5. 特許分類抽出（Claude Sonnet 4.5 + OpenSearch）
6. 構成要素ごと検索（PatentField API）
7. 紐づき特許の検出確認
8. 精度、処理時間、トークン数、コストを記録

更新: 2025-11-29 - AsyncIO対応
"""

import sys
import json
import time
import csv
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import requests

# 自モジュールのインポート
from patent_structure_analyzer import PatentStructureAnalyzer
from patent_keyword_extractor import PatentKeywordExtractor
from patent_classification_extractor import PatentClassificationExtractor
from patent_search_executor_per_component import PerComponentSearchExecutor


class PerformanceTestSystem:
    """性能テストシステム"""

    def __init__(
        self,
        google_credentials_path: str,
        patentfield_key_path: str = "../patentfield_key.json",
        output_dir: str = "tests/performance_test/results"
    ):
        """
        初期化

        Args:
            google_credentials_path: Google Cloud認証情報
            patentfield_key_path: PatentField APIキー
            output_dir: 結果出力ディレクトリ
        """
        self.google_credentials_path = google_credentials_path
        self.patentfield_key_path = patentfield_key_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # PatentField API設定
        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        # トークン数とコストの集計
        self.total_tokens = {
            'structure_analysis': {'prompt': 0, 'completion': 0, 'total': 0},
            'keyword_extraction': {'prompt': 0, 'completion': 0, 'total': 0},
            'classification_extraction': {'prompt': 0, 'completion': 0, 'total': 0}
        }

        # Claude Sonnet 4.5の料金（2025年1月時点、USD）
        # https://www.anthropic.com/pricing
        self.pricing = {
            'prompt_tokens': 3.00 / 1_000_000,  # $3.00 per MTok
            'completion_tokens': 15.00 / 1_000_000  # $15.00 per MTok
        }
        self.usd_to_jpy = 150  # 為替レート（概算）

        print(f"性能テストシステム初期化完了")
        print(f"出力ディレクトリ: {self.output_dir}")

    def load_test_data(
        self,
        csv_path: str,
        limit: int = 30,
        row_index: Optional[int] = None
    ) -> List[Dict]:
        """
        CSVからテストデータを読み込み

        Args:
            csv_path: CSVファイルパス
            limit: 抽出件数（row_indexが指定されていない場合）
            row_index: 特定の行番号（1始まり、指定時は該当行のみ読み込み）

        Returns:
            テストデータリスト
        """
        print(f"\n{'='*80}")
        print(f"テストデータ読み込み: {csv_path}")
        if row_index is not None:
            print(f"モード: 単一行指定 (行番号: {row_index})")
        else:
            print(f"モード: 複数行 (上位{limit}件)")
        print(f"{'='*80}")

        test_data = []

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                current_index = i + 1

                # 特定行指定モード
                if row_index is not None:
                    if current_index == row_index:
                        test_data.append({
                            'index': current_index,
                            'syutugan': row['syutugan'],
                            'himotuki': row['himotuki'],
                            'category': row.get('category', ''),
                            'koukaibi': row.get('koukaibi', '')
                        })
                        break  # 該当行のみで終了
                # 通常モード（上位limit件）
                else:
                    if i >= limit:
                        break
                    test_data.append({
                        'index': current_index,
                        'syutugan': row['syutugan'],
                        'himotuki': row['himotuki'],
                        'category': row.get('category', ''),
                        'koukaibi': row.get('koukaibi', '')
                    })

        if not test_data and row_index is not None:
            raise ValueError(f"行番号 {row_index} がCSVファイルに存在しません")

        print(f"読み込み完了: {len(test_data)}件")
        for i, data in enumerate(test_data[:5], 1):
            print(f"  {i}. 本願: {data['syutugan']}, 紐づき: {data['himotuki']}")
        if len(test_data) > 5:
            print(f"  ... 他{len(test_data)-5}件")

        return test_data

    def fetch_patent_text(self, patent_id: str) -> Optional[Dict]:
        """
        PatentField APIで特許の請求の範囲・詳細な説明を取得

        Args:
            patent_id: 特許番号（例: JP2013224028A）

        Returns:
            {'claims': '...', 'description': '...', 'patent_id': '...'}
        """
        # 特許番号の正規化（末尾のA/B/Cを除去）
        # 例: JP2013224028A → JP2013224028
        normalized_id = re.sub(r'([A-Z])$', '', patent_id)

        print(f"    特許番号: {patent_id} → 正規化: {normalized_id}")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        # numbers検索方式（公式推奨）
        # pub_idとapp_doc_idの両方に対応するため、特許番号をそのまま使用
        # PatentField APIが自動的に適切な番号種別を判定する
        payload = {
            "numbers": [
                {"n": normalized_id, "t": "pub_id"}  # 正規化した番号で検索
            ],
            "columns": ["pub_id", "app_doc_id", "claims", "description"],
            "limit": 1
        }

        try:
            response = requests.post(
                self.pf_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )

            # HTTPステータスコードを確認
            if response.status_code == 404:
                print(f"  ❌ {patent_id}: PatentField APIが404エラーを返しました")
                print(f"     検索特許番号: {patent_id}")
                print(f"     → この特許はPatentField DBに存在しない可能性があります")
                print(f"     （または番号フォーマットが不正です）")
                return None

            response.raise_for_status()

            data = response.json()
            records = data.get('records', [])

            if not records:
                print(f"  ⚠️ {patent_id}: 検索結果0件（特許は存在するがデータが空）")
                return None

            record = records[0]
            return {
                'patent_id': patent_id,
                'claims': record.get('claims', ''),
                'description': record.get('description', '')
            }

        except requests.exceptions.HTTPError as e:
            print(f"  ❌ {patent_id}: HTTPエラー - {e}")
            print(f"     ステータスコード: {response.status_code}")
            print(f"     レスポンス: {response.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            print(f"  ❌ {patent_id}: タイムアウト（60秒超過）")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {patent_id}: リクエストエラー - {e}")
            return None
        except Exception as e:
            print(f"  ❌ {patent_id}: 予期しないエラー - {type(e).__name__}: {e}")
            return None

    async def run_full_pipeline(
        self,
        patent_text: Dict,
        output_prefix: str
    ) -> Tuple[Optional[Dict], Dict]:
        """
        構成要件分割から検索までの一連の処理を実行（非同期版）

        Args:
            patent_text: 特許テキスト
            output_prefix: 出力ファイルのプレフィックス

        Returns:
            (検索結果, トークン情報)
        """
        patent_id = patent_text['patent_id']
        claims = patent_text['claims']
        description = patent_text['description']

        print(f"\n  [1/4] 構成要件分割")

        # 1. 構成要件分割（非同期）
        analyzer = PatentStructureAnalyzer(
            credentials_path=self.google_credentials_path
        )

        structure_result = await analyzer.analyze(
            patent_text=f"【請求の範囲】\n{claims}\n\n【詳細な説明】\n{description}"
        )

        if structure_result['status'] != 'success':
            print(f"    ✗ 構成要件分割失敗")
            return None, {}

        # トークン集計
        tokens_structure = structure_result.get('tokens', {})
        self.total_tokens['structure_analysis']['prompt'] += tokens_structure.get('input_tokens', 0)
        self.total_tokens['structure_analysis']['completion'] += tokens_structure.get('output_tokens', 0)
        self.total_tokens['structure_analysis']['total'] += (
            tokens_structure.get('input_tokens', 0) + tokens_structure.get('output_tokens', 0)
        )

        # 構成要件保存
        structure_file = self.output_dir / f"{output_prefix}_structure.json"
        with open(structure_file, 'w', encoding='utf-8') as f:
            json.dump(structure_result, f, ensure_ascii=False, indent=2)

        print(f"    ✓ 完了 ({structure_file.name})")

        print(f"  [2/4] キーワード抽出")

        # 2. キーワード抽出（非同期版を使用）
        extractor = PatentKeywordExtractor(
            credentials_path=self.google_credentials_path,
            patentfield_key_path=self.patentfield_key_path
        )

        keyword_result = await extractor.extract_keywords_async(
            constituent_json_path=str(structure_file)
        )

        # トークン集計
        tokens_keyword = keyword_result.get('tokens', {})
        # キーワード抽出は複数ステップあるため、total_tokensを使用
        total_kw_tokens = tokens_keyword.get('total_tokens', 0)
        # 概算: 入力と出力を3:7で分ける（経験則）
        self.total_tokens['keyword_extraction']['prompt'] += int(total_kw_tokens * 0.5)
        self.total_tokens['keyword_extraction']['completion'] += int(total_kw_tokens * 0.5)
        self.total_tokens['keyword_extraction']['total'] += total_kw_tokens

        # キーワード保存
        keyword_file = self.output_dir / f"{output_prefix}_keywords.json"
        with open(keyword_file, 'w', encoding='utf-8') as f:
            json.dump(keyword_result, f, ensure_ascii=False, indent=2)

        print(f"    ✓ 完了 ({keyword_file.name})")

        print(f"  [3/4] 特許分類抽出")

        # 3. 特許分類抽出
        classifier = PatentClassificationExtractor(
            credentials_path=self.google_credentials_path,
            patentfield_key_path=self.patentfield_key_path
        )

        classification_result = classifier.extract(
            input_file=str(structure_file)
        )

        # トークン集計
        tokens_classification = classification_result.get('usage', {})
        self.total_tokens['classification_extraction']['prompt'] += tokens_classification.get('input_tokens', 0)
        self.total_tokens['classification_extraction']['completion'] += tokens_classification.get('output_tokens', 0)
        self.total_tokens['classification_extraction']['total'] += (
            tokens_classification.get('input_tokens', 0) + tokens_classification.get('output_tokens', 0)
        )

        # 分類保存
        classification_file = self.output_dir / f"{output_prefix}_classifications.json"
        with open(classification_file, 'w', encoding='utf-8') as f:
            json.dump(classification_result, f, ensure_ascii=False, indent=2)

        print(f"    ✓ 完了 ({classification_file.name})")

        print(f"  [4/4] 構成要素ごと検索")

        # 4. 検索実行
        search_executor = PerComponentSearchExecutor(
            keywords_file=str(keyword_file),
            classifications_file=str(classification_file),
            patentfield_key_path=self.patentfield_key_path,
            google_credentials_path=self.google_credentials_path
        )

        search_result = search_executor.execute_full_search(
            use_independent_only=True,  # 独立請求項のみ使用
            max_workers=5,
            output_file=str(self.output_dir / f"{output_prefix}_search_result.json")
        )

        print(f"    ✓ 完了 ({len(search_result['merged_patent_ids'])}件取得)")

        # トークン情報をまとめる
        token_info = {
            'structure_analysis': tokens_structure,
            'keyword_extraction': tokens_keyword,
            'classification_extraction': tokens_classification
        }

        return search_result, token_info

    def check_himotuki_detection(
        self,
        search_result: Dict,
        himotuki_id: str
    ) -> bool:
        """
        紐づき特許が検索結果に含まれているか確認

        Args:
            search_result: 検索結果
            himotuki_id: 紐づき特許番号

        Returns:
            True if detected
        """
        # 番号の正規化（末尾のA/B/Cなどのsuffixを除去）
        himotuki_normalized = re.sub(r'([A-Z])$', '', himotuki_id)

        merged_ids = search_result.get('merged_patent_ids', [])

        for patent_id in merged_ids:
            if himotuki_normalized in patent_id:
                return True

        return False

    async def run_performance_test(
        self,
        csv_path: str,
        limit: int = 30,
        row_index: Optional[int] = None
    ) -> Dict:
        """
        性能テスト実行

        Args:
            csv_path: テストデータCSV
            limit: テスト件数（row_indexが指定されていない場合）
            row_index: 特定の行番号（1始まり、指定時は該当行のみテスト）

        Returns:
            テスト結果サマリー
        """
        print(f"\n{'#'*80}")
        print(f"# 性能テスト開始")
        if row_index is not None:
            print(f"# テストモード: 単一行 (行番号: {row_index})")
        else:
            print(f"# テストモード: 複数行 (上位{limit}件)")
        print(f"{'#'*80}")

        start_time = time.time()

        # テストデータ読み込み
        test_data = self.load_test_data(csv_path, limit, row_index)

        results = []
        success_count = 0
        detection_count = 0

        for data in test_data:
            index = data['index']
            syutugan = data['syutugan']
            himotuki = data['himotuki']

            print(f"\n{'='*80}")
            print(f"テスト {index}/{len(test_data)}: {syutugan}")
            print(f"{'='*80}")

            test_start_time = time.time()

            # 特許テキスト取得
            print(f"  特許テキスト取得: {syutugan}")
            patent_text = self.fetch_patent_text(syutugan)

            if not patent_text:
                results.append({
                    'index': index,
                    'syutugan': syutugan,
                    'himotuki': himotuki,
                    'status': 'fetch_failed',
                    'detected': False,
                    'elapsed_time': 0
                })
                continue

            # 一連の処理実行（非同期）
            try:
                # 出力ファイル名のプレフィックス（末尾のA/B/Cを除去）
                normalized_syutugan = re.sub(r'([A-Z])$', '', syutugan)
                output_prefix = f"test_{index:03d}_{normalized_syutugan}"

                search_result, token_info = await self.run_full_pipeline(
                    patent_text=patent_text,
                    output_prefix=output_prefix
                )

                if search_result:
                    # 紐づき特許の検出確認
                    detected = self.check_himotuki_detection(search_result, himotuki)

                    test_elapsed_time = time.time() - test_start_time

                    results.append({
                        'index': index,
                        'syutugan': syutugan,
                        'himotuki': himotuki,
                        'status': 'success',
                        'detected': detected,
                        'search_result_count': search_result['total_unique_patents'],
                        'elapsed_time': test_elapsed_time,
                        'token_info': token_info
                    })

                    success_count += 1
                    if detected:
                        detection_count += 1
                        print(f"  ✅ 紐づき特許検出: {himotuki}")
                    else:
                        print(f"  ❌ 紐づき特許未検出: {himotuki}")

                else:
                    results.append({
                        'index': index,
                        'syutugan': syutugan,
                        'himotuki': himotuki,
                        'status': 'pipeline_failed',
                        'detected': False,
                        'elapsed_time': time.time() - test_start_time
                    })

            except Exception as e:
                print(f"  ✗ エラー: {e}")
                results.append({
                    'index': index,
                    'syutugan': syutugan,
                    'himotuki': himotuki,
                    'status': 'error',
                    'detected': False,
                    'error': str(e),
                    'elapsed_time': time.time() - test_start_time
                })

        total_elapsed_time = time.time() - start_time

        # 精度計算
        accuracy = detection_count / success_count if success_count > 0 else 0

        # コスト計算
        cost_info = self.calculate_cost()

        # サマリー
        summary = {
            'test_date': datetime.now().isoformat(),
            'test_count': len(test_data),
            'success_count': success_count,
            'detection_count': detection_count,
            'accuracy': accuracy,
            'total_elapsed_time': total_elapsed_time,
            'average_time_per_test': total_elapsed_time / len(test_data) if test_data else 0,
            'total_tokens': self.total_tokens,
            'cost_info': cost_info,
            'results': results
        }

        # 結果保存（JSON）
        summary_file = self.output_dir / f"performance_test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # MD形式レポート生成
        md_report_file = self.generate_md_report(summary, summary_file)

        print(f"\n{'#'*80}")
        print(f"# 性能テスト完了")
        print(f"{'#'*80}")
        print(f"テスト件数: {len(test_data)}")
        print(f"成功: {success_count}")
        print(f"検出: {detection_count}")
        print(f"精度: {accuracy*100:.1f}%")
        print(f"総処理時間: {total_elapsed_time:.2f}秒")
        print(f"平均処理時間: {total_elapsed_time/len(test_data):.2f}秒/件")
        print(f"総コスト: ¥{cost_info['total_cost_jpy']:.2f}")
        print(f"結果保存: {summary_file}")
        print(f"MDレポート: {md_report_file}")
        print(f"{'#'*80}")

        return summary

    def calculate_cost(self) -> Dict:
        """
        トークン数からコストを計算

        Returns:
            コスト情報
        """
        total_prompt_tokens = sum(
            self.total_tokens[key]['prompt']
            for key in self.total_tokens
        )
        total_completion_tokens = sum(
            self.total_tokens[key]['completion']
            for key in self.total_tokens
        )

        # USD計算
        prompt_cost_usd = total_prompt_tokens * self.pricing['prompt_tokens']
        completion_cost_usd = total_completion_tokens * self.pricing['completion_tokens']
        total_cost_usd = prompt_cost_usd + completion_cost_usd

        # JPY計算
        total_cost_jpy = total_cost_usd * self.usd_to_jpy

        return {
            'total_prompt_tokens': total_prompt_tokens,
            'total_completion_tokens': total_completion_tokens,
            'total_tokens': total_prompt_tokens + total_completion_tokens,
            'prompt_cost_usd': prompt_cost_usd,
            'completion_cost_usd': completion_cost_usd,
            'total_cost_usd': total_cost_usd,
            'total_cost_jpy': total_cost_jpy,
            'usd_to_jpy_rate': self.usd_to_jpy
        }

    def generate_md_report(self, summary: Dict, summary_file: Path) -> str:
        """
        MD形式のレポートを生成

        Args:
            summary: テスト結果サマリー
            summary_file: JSONサマリーファイルパス

        Returns:
            MDファイルパス
        """
        # MDファイル名を生成
        md_file = summary_file.with_suffix('.md')

        # レポート内容を構築
        report_lines = []
        report_lines.append(f"# 性能テスト結果レポート")
        report_lines.append(f"")
        report_lines.append(f"**実行日時**: {summary['test_date']}")
        report_lines.append(f"")
        report_lines.append(f"---")
        report_lines.append(f"")

        # サマリー統計
        report_lines.append(f"## 📊 サマリー統計")
        report_lines.append(f"")
        report_lines.append(f"| 指標 | 値 |")
        report_lines.append(f"|------|------|")
        report_lines.append(f"| テスト件数 | {summary['test_count']}件 |")
        report_lines.append(f"| 成功件数 | {summary['success_count']}件 |")
        report_lines.append(f"| 検出件数 | {summary['detection_count']}件 |")
        report_lines.append(f"| **検出精度** | **{summary['accuracy']*100:.1f}%** |")
        report_lines.append(f"| 総処理時間 | {summary['total_elapsed_time']:.2f}秒 ({summary['total_elapsed_time']/60:.1f}分) |")
        report_lines.append(f"| 平均処理時間 | {summary['average_time_per_test']:.2f}秒/件 |")
        report_lines.append(f"")

        # コスト情報
        cost_info = summary['cost_info']
        report_lines.append(f"## 💰 コスト情報")
        report_lines.append(f"")
        report_lines.append(f"| 項目 | 値 |")
        report_lines.append(f"|------|------|")
        report_lines.append(f"| 総トークン数 | {cost_info['total_tokens']:,} tokens |")
        report_lines.append(f"| プロンプトトークン | {cost_info['total_prompt_tokens']:,} tokens |")
        report_lines.append(f"| 完了トークン | {cost_info['total_completion_tokens']:,} tokens |")
        report_lines.append(f"| **総コスト（USD）** | **${cost_info['total_cost_usd']:.4f}** |")
        report_lines.append(f"| **総コスト（JPY）** | **¥{cost_info['total_cost_jpy']:.2f}** |")
        report_lines.append(f"| 為替レート | {cost_info['usd_to_jpy_rate']} JPY/USD |")
        report_lines.append(f"")

        # 個別テスト結果
        report_lines.append(f"## 📋 個別テスト結果")
        report_lines.append(f"")

        for result in summary['results']:
            index = result['index']
            syutugan = result['syutugan']
            himotuki = result['himotuki']
            status = result['status']
            detected = result.get('detected', False)

            # 正規化した特許番号（末尾のA/B/C除去）
            normalized_id = re.sub(r'([A-Z])$', '', syutugan)

            report_lines.append(f"### Test #{index}: {syutugan}")
            report_lines.append(f"")
            report_lines.append(f"- **本願特許**: {syutugan}")
            report_lines.append(f"- **紐づき特許**: {himotuki}")
            report_lines.append(f"- **ステータス**: {status}")
            report_lines.append(f"- **検出結果**: {'✅ 検出成功' if detected else '❌ 未検出'}")

            if status == 'success':
                search_count = result.get('search_result_count', 0)
                elapsed_time = result.get('elapsed_time', 0)
                report_lines.append(f"- **検索結果件数**: {search_count}件")
                report_lines.append(f"- **処理時間**: {elapsed_time:.2f}秒")

            # 関連ファイルへのリンク
            report_lines.append(f"")
            report_lines.append(f"**関連ファイル**:")
            report_lines.append(f"")

            # ファイル名のプレフィックス
            file_prefix = f"test_{index:03d}_{normalized_id}"

            # 各ファイルへのリンク（相対パス）
            structure_file = f"{file_prefix}_structure.json"
            keywords_file = f"{file_prefix}_keywords.json"
            classifications_file = f"{file_prefix}_classifications.json"
            search_result_file = f"{file_prefix}_search_result.json"

            report_lines.append(f"- [構成要件分割結果]({structure_file})")
            report_lines.append(f"- [キーワード抽出結果]({keywords_file})")
            report_lines.append(f"- [特許分類抽出結果]({classifications_file})")
            report_lines.append(f"- [検索結果]({search_result_file})")
            report_lines.append(f"")

        # JSONサマリーファイルへのリンク
        report_lines.append(f"---")
        report_lines.append(f"")
        report_lines.append(f"## 📄 詳細データ")
        report_lines.append(f"")
        report_lines.append(f"- [JSON形式のサマリーファイル]({summary_file.name})")
        report_lines.append(f"")

        # MDファイルに書き込み
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        return str(md_file)


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(description='性能テストシステム')
    parser.add_argument('--csv', default='tests/performance_test/combined_data.csv', help='テストデータCSV')
    parser.add_argument('--limit', type=int, default=30, help='テスト件数（--row未指定時）')
    parser.add_argument('--row', type=int, help='特定の行番号を指定（1始まり、指定時は該当行のみテスト）')
    parser.add_argument('--credentials', default='../ttdc-in-house-dev-3e07247326cb.json', help='Google Cloud認証情報')
    parser.add_argument('--pf-key', default='../patentfield_key.json', help='PatentField APIキー')

    args = parser.parse_args()

    # テスト実行（非同期）
    system = PerformanceTestSystem(
        google_credentials_path=args.credentials,
        patentfield_key_path=args.pf_key
    )

    summary = asyncio.run(system.run_performance_test(
        csv_path=args.csv,
        limit=args.limit,
        row_index=args.row
    ))

    print("\n✅ 性能テスト完了")


if __name__ == '__main__':
    main()
