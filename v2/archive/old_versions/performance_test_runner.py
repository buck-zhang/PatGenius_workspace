#!/usr/bin/env python3
"""
特許検索システム性能テストランナー v2.0

30件のプロトタイプテストを実行し、Recall、処理時間、コストを計測します。
"""

import json
import pandas as pd
import time
from pathlib import Path
from typing import Dict, List, Tuple
import requests
from datetime import datetime
import logging

# 既存システムのインポート
from patent_structure_analyzer import PatentStructureAnalyzer
from patent_keyword_extractor import PatentKeywordExtractor
from patent_classification_extractor import PatentClassificationExtractor
from patent_search_executor import PatentSearchExecutor


# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/performance_test/performance_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """性能テストランナー"""

    def __init__(
        self,
        patentfield_key_path: str = "../patentfield_key.json",
        claude_key_path: str = None,  # 環境変数から取得
        gemini_key_path: str = "../ttdc-in-house-dev-3e07247326cb.json",
        output_dir: str = "tests/performance_test"
    ):
        """
        初期化

        Args:
            patentfield_key_path: PatentField APIキーファイル
            claude_key_path: Claude APIキー（環境変数ANTHROPIC_API_KEY使用）
            gemini_key_path: Gemini認証情報ファイル
            output_dir: 出力ディレクトリ
        """
        # 出力ディレクトリ作成
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "patent_texts").mkdir(exist_ok=True)

        # PatentField API設定
        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        # 認証情報パス
        self.gemini_credentials = gemini_key_path

        # メトリクス収集
        self.metrics = {
            'test_cases': [],
            'summary': {},
            'errors': []
        }

        # 料金レート（2025年11月、157円/USD）
        self.pricing = {
            'claude_sonnet4': {
                'input_per_1m': 471,   # 円
                'output_per_1m': 2355  # 円
            },
            'gemini_15_pro': {
                'input_per_1m': 196,   # 円
                'output_per_1m': 1570  # 円
            }
        }

        logger.info("✓ PerformanceTestRunner初期化完了")

    # ============================================================
    # Step 1: データ準備
    # ============================================================

    def prepare_test_data(
        self,
        csv1: str = "tests/xy_data1.csv",
        csv2: str = "tests/xy_data2.csv",
        n_samples: int = 30
    ) -> pd.DataFrame:
        """
        テストデータを準備

        Args:
            csv1: CSVファイル1
            csv2: CSVファイル2
            n_samples: サンプル数

        Returns:
            テストデータのDataFrame
        """
        logger.info("=" * 80)
        logger.info("Step 1: テストデータ準備")
        logger.info("=" * 80)

        # CSV読み込み
        df1 = pd.read_csv(csv1)
        df2 = pd.read_csv(csv2)
        logger.info(f"✓ CSV1読み込み: {len(df1)}行")
        logger.info(f"✓ CSV2読み込み: {len(df2)}行")

        # 縦結合
        df_combined = pd.concat([df1, df2], ignore_index=True)
        logger.info(f"✓ 結合完了: {len(df_combined)}行")

        # 保存
        combined_path = self.output_dir / "combined_data.csv"
        df_combined.to_csv(combined_path, index=False, encoding='utf-8')
        logger.info(f"✓ 結合データ保存: {combined_path}")

        # 上位N件抽出
        df_test = df_combined.head(n_samples)
        test_path = self.output_dir / f"test_data_{n_samples}.csv"
        df_test.to_csv(test_path, index=False, encoding='utf-8')
        logger.info(f"✓ テストデータ抽出: {len(df_test)}件")
        logger.info(f"✓ テストデータ保存: {test_path}\n")

        return df_test

    # ============================================================
    # Step 2: 特許データ取得
    # ============================================================

    def fetch_patent_data(self, pub_id: str) -> Dict:
        """
        PatentField APIから特許データ取得（numbersパラメータ使用）

        Args:
            pub_id: 公開番号（例: JP2014007731A）

        Returns:
            {
                'pub_id': 'JP...',
                'claims': '請求の範囲',
                'description': '詳細な説明',
                'status': 'success'/'not_found'/'error'
            }
        """
        # キャッシュ確認
        cache_file = self.output_dir / "patent_texts" / f"{pub_id}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # PatentField SEARCH API呼び出し（numbersパラメータ使用）
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        # 公開番号(pub_id)をEPODOC形式に変換（JP2013224028A → JP2013224028）
        # PatentField APIはEPODOC形式を期待
        epodoc_number = pub_id.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        payload = {
            "numbers": [
                {"n": epodoc_number, "t": "pub_id"}  # pub_idタイプで検索（公開番号）
            ],
            "columns": [
                "app_doc_id",
                "app_claims",
                "grant_claims",
                "description",
                "app_description"
            ]
        }

        try:
            response = requests.post(
                self.pf_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])

                if len(records) > 0:
                    record = records[0]
                    # app_claimsとapp_descriptionを優先、なければgrant_claims/descriptionを使用
                    claims = record.get('app_claims', '')
                    if not claims:
                        claims = record.get('grant_claims', '')

                    description = record.get('app_description', '')
                    if not description:
                        description = record.get('description', '')

                    result = {
                        'pub_id': pub_id,
                        'claims': claims,
                        'description': description,
                        'status': 'success'
                    }
                    logger.info(f"  ✓ 成功: 請求の範囲 {len(claims)}文字, 詳細な説明 {len(description)}文字")
                else:
                    result = {
                        'pub_id': pub_id,
                        'claims': '',
                        'description': '',
                        'status': 'not_found'
                    }
                    logger.warning(f"  ⚠ 特許データが見つかりません: {pub_id}")
            else:
                result = {
                    'pub_id': pub_id,
                    'claims': '',
                    'description': '',
                    'status': 'error',
                    'error_code': response.status_code
                }
                logger.error(f"  ✗ APIエラー: HTTP {response.status_code}")

            # キャッシュ保存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            logger.error(f"✗ {pub_id}取得エラー: {e}")
            return {
                'pub_id': pub_id,
                'claims': '',
                'description': '',
                'status': 'error',
                'error': str(e)
            }

    def fetch_batch_patent_data(self, pub_ids: List[str]) -> Dict[str, Dict]:
        """
        バッチで特許データ取得

        Args:
            pub_ids: 公開番号リスト

        Returns:
            {pub_id: patent_data}の辞書
        """
        logger.info("=" * 80)
        logger.info("Step 2: 特許データ取得")
        logger.info("=" * 80)

        results = {}
        for i, pub_id in enumerate(pub_ids, 1):
            logger.info(f"[{i}/{len(pub_ids)}] {pub_id} 取得中...")
            patent_data = self.fetch_patent_data(pub_id)
            results[pub_id] = patent_data

            if patent_data['status'] == 'success':
                logger.info(f"  ✓ 成功: 請求の範囲 {len(patent_data['claims'])}文字")
            else:
                logger.warning(f"  ⚠ {patent_data['status']}")

            time.sleep(0.5)  # API制限考慮

        success_count = sum(1 for p in results.values() if p['status'] == 'success')
        logger.info(f"\n✓ データ取得完了: {success_count}/{len(pub_ids)}件成功\n")

        return results

    # ============================================================
    # Step 3: 検索パイプライン実行
    # ============================================================

    def run_search_pipeline(self, pub_id: str, patent_data: Dict) -> Dict:
        """
        検索パイプライン実行

        Args:
            pub_id: 公開番号
            patent_data: 特許データ

        Returns:
            {
                'pub_id': 'JP...',
                'search_results': [patent_ids],
                'metrics': {処理時間、トークン使用量}
            }
        """
        logger.info(f"{'='*80}")
        logger.info(f"検索パイプライン実行: {pub_id}")
        logger.info(f"{'='*80}")

        if patent_data['status'] != 'success':
            return {
                'pub_id': pub_id,
                'search_results': [],
                'metrics': {},
                'status': 'skipped',
                'reason': patent_data['status']
            }

        metrics = {
            'pub_id': pub_id,
            'tokens_claude_input': 0,
            'tokens_claude_output': 0,
            'tokens_gemini_input': 0,
            'tokens_gemini_output': 0
        }

        start_time = time.time()

        try:
            # 構成要件分割
            logger.info("  ステップ1: 構成要件分割...")
            t1 = time.time()

            analyzer = PatentStructureAnalyzer(self.gemini_credentials)
            structure_result = analyzer.analyze(
                patent_data['claims'] + "\n\n" + patent_data['description']
            )

            metrics['time_structure'] = time.time() - t1
            # Claudeトークン（構成要件分割）
            # 実際のトークン数はAPIレスポンスから取得すべきだが、
            # 概算として文字数 / 4
            step1_input = len(patent_data['claims'] + patent_data['description']) // 4
            step1_output = len(json.dumps(structure_result)) // 4
            metrics['tokens_claude_input'] += step1_input
            metrics['tokens_claude_output'] += step1_output
            logger.info(f"  ✓ 完了 ({metrics['time_structure']:.1f}秒)")
            logger.info(f"    トークン: 入力={step1_input:,} / 出力={step1_output:,} / 合計={step1_input + step1_output:,}")

            # キーワード抽出
            logger.info("  ステップ2: キーワード抽出...")
            t2 = time.time()

            # 構成要件データを一時保存
            structure_file = self.output_dir / f"{pub_id}_structure.json"
            with open(structure_file, 'w', encoding='utf-8') as f:
                json.dump(structure_result, f, ensure_ascii=False, indent=2)

            keyword_extractor = PatentKeywordExtractor(
                self.gemini_credentials,
                "../patentfield_key.json"
            )
            keywords_result = keyword_extractor.extract_keywords(str(structure_file))

            metrics['time_keyword'] = time.time() - t2
            step2_input = len(json.dumps(structure_result)) // 4
            step2_output = len(json.dumps(keywords_result)) // 4
            metrics['tokens_claude_input'] += step2_input
            metrics['tokens_claude_output'] += step2_output
            logger.info(f"  ✓ 完了 ({metrics['time_keyword']:.1f}秒)")
            logger.info(f"    トークン: 入力={step2_input:,} / 出力={step2_output:,} / 合計={step2_input + step2_output:,}")

            # 分類コード抽出
            logger.info("  ステップ3: 分類コード抽出...")
            t3 = time.time()

            classification_extractor = PatentClassificationExtractor(
                self.gemini_credentials
            )

            classification_file = self.output_dir / f"{pub_id}_classification.json"
            classification_result = classification_extractor.extract(
                str(structure_file),
                str(classification_file),
                min_importance=0.8
            )

            metrics['time_classification'] = time.time() - t3
            step3_input = len(json.dumps(structure_result)) // 4
            step3_output = len(json.dumps(classification_result)) // 4
            metrics['tokens_gemini_input'] += step3_input
            metrics['tokens_gemini_output'] += step3_output
            logger.info(f"  ✓ 完了 ({metrics['time_classification']:.1f}秒)")
            logger.info(f"    トークン(Gemini): 入力={step3_input:,} / 出力={step3_output:,} / 合計={step3_input + step3_output:,}")

            # PatentField検索
            logger.info("  ステップ4: PatentField検索...")
            t4 = time.time()

            # キーワードと分類データを一時保存
            keywords_file = self.output_dir / f"{pub_id}_keywords.json"
            classification_file = self.output_dir / f"{pub_id}_classification.json"

            with open(keywords_file, 'w', encoding='utf-8') as f:
                json.dump(keywords_result, f, ensure_ascii=False, indent=2)
            with open(classification_file, 'w', encoding='utf-8') as f:
                json.dump(classification_result, f, ensure_ascii=False, indent=2)

            search_executor = PatentSearchExecutor(
                str(keywords_file),
                str(classification_file),
                "../patentfield_key.json"
            )

            search_output = self.output_dir / f"{pub_id}_search_results.json"
            search_result = search_executor.execute(
                str(search_output),
                target_min=10,
                target_max=300,
                fetch_full_text=False
            )

            metrics['time_search'] = time.time() - t4
            logger.info(f"  ✓ 完了 ({metrics['time_search']:.1f}秒)")

            # 検索結果から特許IDリスト取得
            search_results = search_result.get('unique_patent_ids', [])

            metrics['total_time'] = time.time() - start_time

            # トークン総計
            total_tokens_claude = metrics['tokens_claude_input'] + metrics['tokens_claude_output']
            total_tokens_gemini = metrics['tokens_gemini_input'] + metrics['tokens_gemini_output']

            logger.info(f"\n✓ パイプライン完了: {len(search_results)}件ヒット")
            logger.info(f"  総処理時間: {metrics['total_time']:.1f}秒")
            logger.info(f"  総トークン: Claude={total_tokens_claude:,} / Gemini={total_tokens_gemini:,}\n")

            return {
                'pub_id': pub_id,
                'search_results': search_results,
                'metrics': metrics,
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"✗ エラー: {e}")
            import traceback
            traceback.print_exc()

            return {
                'pub_id': pub_id,
                'search_results': [],
                'metrics': metrics,
                'status': 'error',
                'error': str(e)
            }

    # ============================================================
    # Step 4: 結果検証
    # ============================================================

    def verify_result(
        self,
        search_results: List[str],
        himotuki_patent: str
    ) -> Dict:
        """
        検索結果に紐づいた特許が含まれているか検証

        番号形式の正規化:
        - search_results: EPODOC形式(JP2012040876)
        - himotuki_patent: 種別コード付き(JP2012040876A)
        → 両方から種別コードを除去して比較

        Args:
            search_results: 検索結果の特許IDリスト
            himotuki_patent: 紐づいた特許番号

        Returns:
            {
                'found': True/False,
                'rank': 順位 or None,
                'total_results': 総結果数
            }
        """
        # 種別コード(A,B,C等)を除去して正規化
        normalized_himotuki = himotuki_patent.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        normalized_results = [
            pid.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
            for pid in search_results
        ]

        if normalized_himotuki in normalized_results:
            rank = normalized_results.index(normalized_himotuki) + 1
            return {
                'found': True,
                'rank': rank,
                'total_results': len(search_results)
            }
        else:
            return {
                'found': False,
                'rank': None,
                'total_results': len(search_results)
            }

    # ============================================================
    # Step 5: コスト計算
    # ============================================================

    def calculate_cost(self, metrics: Dict) -> Dict:
        """
        料金計算

        Args:
            metrics: メトリクス辞書

        Returns:
            {
                'claude_cost': 円,
                'gemini_cost': 円,
                'total_cost': 円
            }
        """
        # Claude料金
        claude_input_cost = (
            metrics['tokens_claude_input'] / 1_000_000
        ) * self.pricing['claude_sonnet4']['input_per_1m']

        claude_output_cost = (
            metrics['tokens_claude_output'] / 1_000_000
        ) * self.pricing['claude_sonnet4']['output_per_1m']

        claude_cost = claude_input_cost + claude_output_cost

        # Gemini料金
        gemini_input_cost = (
            metrics['tokens_gemini_input'] / 1_000_000
        ) * self.pricing['gemini_15_pro']['input_per_1m']

        gemini_output_cost = (
            metrics['tokens_gemini_output'] / 1_000_000
        ) * self.pricing['gemini_15_pro']['output_per_1m']

        gemini_cost = gemini_input_cost + gemini_output_cost

        return {
            'claude_cost': round(claude_cost, 2),
            'gemini_cost': round(gemini_cost, 2),
            'total_cost': round(claude_cost + gemini_cost, 2)
        }

    # ============================================================
    # Step 6: メインテスト実行
    # ============================================================

    def run_test(self, n_samples: int = 30) -> Dict:
        """
        性能テスト実行

        Args:
            n_samples: テストサンプル数

        Returns:
            テスト結果辞書
        """
        logger.info("\n" + "=" * 80)
        logger.info("特許検索システム性能テスト開始")
        logger.info("=" * 80 + "\n")

        # Step 1: データ準備
        df_test = self.prepare_test_data(n_samples=n_samples)

        # Step 2: 特許データ取得
        pub_ids = df_test['syutugan'].tolist()
        patent_data_dict = self.fetch_batch_patent_data(pub_ids)

        # Step 3-5: 各テストケース実行
        logger.info("=" * 80)
        logger.info("Step 3-5: 検索パイプライン実行と検証")
        logger.info("=" * 80 + "\n")

        test_start = time.time()

        for idx, row in df_test.iterrows():
            syutugan = row['syutugan']
            himotuki = row['himotuki']

            logger.info(f"\n{'='*80}")
            logger.info(f"テストケース {idx + 1}/{len(df_test)}")
            logger.info(f"本願: {syutugan} → 紐づいた特許: {himotuki}")
            logger.info(f"{'='*80}")

            patent_data = patent_data_dict[syutugan]

            # 検索パイプライン実行
            pipeline_result = self.run_search_pipeline(syutugan, patent_data)

            # 結果検証
            verification = self.verify_result(
                pipeline_result['search_results'],
                himotuki
            )

            # コスト計算
            if pipeline_result['status'] == 'success':
                cost = self.calculate_cost(pipeline_result['metrics'])
            else:
                cost = {'claude_cost': 0, 'gemini_cost': 0, 'total_cost': 0}

            # トークン数と処理時間をトップレベルに展開
            if pipeline_result['status'] == 'success':
                m = pipeline_result['metrics']
                tokens_info = {
                    'tokens_claude_input': m.get('tokens_claude_input', 0),
                    'tokens_claude_output': m.get('tokens_claude_output', 0),
                    'tokens_gemini_input': m.get('tokens_gemini_input', 0),
                    'tokens_gemini_output': m.get('tokens_gemini_output', 0),
                    'tokens_total': (m.get('tokens_claude_input', 0) + m.get('tokens_claude_output', 0) +
                                   m.get('tokens_gemini_input', 0) + m.get('tokens_gemini_output', 0))
                }
                time_info = {
                    'time_structure_sec': round(m.get('time_structure', 0), 2),
                    'time_keyword_sec': round(m.get('time_keyword', 0), 2),
                    'time_classification_sec': round(m.get('time_classification', 0), 2),
                    'time_search_sec': round(m.get('time_search', 0), 2),
                    'time_total_sec': round(m.get('total_time', 0), 2)
                }
            else:
                tokens_info = {
                    'tokens_claude_input': 0,
                    'tokens_claude_output': 0,
                    'tokens_gemini_input': 0,
                    'tokens_gemini_output': 0,
                    'tokens_total': 0
                }
                time_info = {
                    'time_structure_sec': 0,
                    'time_keyword_sec': 0,
                    'time_classification_sec': 0,
                    'time_search_sec': 0,
                    'time_total_sec': 0
                }

            # 記録
            test_case = {
                'test_id': idx + 1,
                'syutugan': syutugan,
                'himotuki': himotuki,
                'found': verification['found'],
                'rank': verification['rank'],
                'total_results': verification['total_results'],
                'status': pipeline_result['status'],
                **tokens_info,  # トークン情報を展開
                **time_info,    # 処理時間情報を展開
                'cost_claude_jpy': round(cost.get('claude_cost', 0), 2),
                'cost_gemini_jpy': round(cost.get('gemini_cost', 0), 2),
                'cost_total_jpy': round(cost.get('total_cost', 0), 2),
                'metrics': pipeline_result.get('metrics', {}),  # 詳細メトリクスも保持
                'cost': cost  # 詳細コスト情報も保持
            }

            self.metrics['test_cases'].append(test_case)

            # 結果表示
            if verification['found']:
                logger.info(f"✓ 成功: 紐づいた特許を発見（順位: {verification['rank']}/{verification['total_results']}）")
            else:
                logger.info(f"✗ 失敗: 紐づいた特許が見つかりませんでした")

            if cost['total_cost'] > 0:
                logger.info(f"  コスト: {cost['total_cost']:.2f}円")

            if pipeline_result['status'] == 'success':
                m = pipeline_result['metrics']
                total_tokens = (m['tokens_claude_input'] + m['tokens_claude_output'] +
                                m['tokens_gemini_input'] + m['tokens_gemini_output'])
                logger.info(f"  総処理時間: {m['total_time']:.1f}秒 / 総トークン: {total_tokens:,}")

        total_test_time = time.time() - test_start

        # Step 6: サマリー計算
        logger.info("\n" + "=" * 80)
        logger.info("Step 6: 結果集計")
        logger.info("=" * 80)

        successful_tests = [tc for tc in self.metrics['test_cases'] if tc['status'] == 'success']
        found_count = sum(1 for tc in successful_tests if tc['found'])

        recall = found_count / len(successful_tests) if successful_tests else 0

        total_cost = sum(tc['cost']['total_cost'] for tc in self.metrics['test_cases'])
        avg_time = sum(tc['metrics'].get('total_time', 0) for tc in successful_tests) / len(successful_tests) if successful_tests else 0

        self.metrics['summary'] = {
            'total_test_cases': len(df_test),
            'successful_tests': len(successful_tests),
            'found_count': found_count,
            'recall': round(recall, 3),
            'total_time': round(total_test_time, 2),
            'avg_time_per_case': round(avg_time, 2),
            'total_cost_jpy': round(total_cost, 2),
            'avg_cost_per_case': round(total_cost / len(df_test), 2)
        }

        # 結果表示
        logger.info(f"\n性能テスト結果サマリー:")
        logger.info(f"  テストケース数: {self.metrics['summary']['total_test_cases']}")
        logger.info(f"  成功: {self.metrics['summary']['successful_tests']}")
        logger.info(f"  紐づいた特許発見: {found_count}/{len(successful_tests)}")
        logger.info(f"  Recall: {recall:.1%}")
        logger.info(f"  総処理時間: {total_test_time:.1f}秒")
        logger.info(f"  平均処理時間: {avg_time:.1f}秒/件")
        logger.info(f"  総コスト: {total_cost:.2f}円")
        logger.info(f"  平均コスト: {total_cost / len(df_test):.2f}円/件")

        # 結果保存
        result_file = self.output_dir / "test_results.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)

        logger.info(f"\n✓ テスト結果保存: {result_file}")

        return self.metrics


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(
        description='特許検索システム性能テスト v2.0'
    )
    parser.add_argument(
        '-n', '--samples',
        type=int,
        default=30,
        help='テストサンプル数 (default: 30)'
    )

    args = parser.parse_args()

    # テスト実行
    runner = PerformanceTestRunner()
    results = runner.run_test(n_samples=args.samples)

    print("\n" + "=" * 80)
    print("性能テスト完了")
    print("=" * 80)
    print(f"Recall: {results['summary']['recall']:.1%}")
    print(f"総コスト: {results['summary']['total_cost_jpy']:.2f}円")
    print("=" * 80)


if __name__ == '__main__':
    main()
