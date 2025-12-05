#!/usr/bin/env python3
"""
特許検索システム性能テストランナー v2.1

改善点:
1. 複数番号タイプ対応の検証機能（pub_id/app_id/exam_id）
2. Claude API最適化（max_tokens=64000, temperature=0）
3. エラーハンドリング＆リトライロジック
4. 並列処理の最適化（ThreadPoolExecutor）
5. 階層型キャッシュシステム
"""

import json
import pandas as pd
import time
import pickle
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import requests
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
        logging.FileHandler('tests/performance_test/performance_test_v2_1.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HierarchicalCache:
    """階層型キャッシュシステム"""

    def __init__(self, cache_dir: str = "tests/performance_test/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 階層別キャッシュディレクトリ
        self.patent_data_cache = self.cache_dir / "patent_data"
        self.structure_cache = self.cache_dir / "structure"
        self.keywords_cache = self.cache_dir / "keywords"
        self.classification_cache = self.cache_dir / "classification"

        for cache_path in [self.patent_data_cache, self.structure_cache,
                           self.keywords_cache, self.classification_cache]:
            cache_path.mkdir(exist_ok=True)

    def get(self, cache_type: str, key: str):
        """キャッシュ取得"""
        cache_file = getattr(self, f"{cache_type}_cache") / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"キャッシュ読み込みエラー {key}: {e}")
                return None
        return None

    def set(self, cache_type: str, key: str, value):
        """キャッシュ保存"""
        cache_file = getattr(self, f"{cache_type}_cache") / f"{key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            logger.warning(f"キャッシュ保存エラー {key}: {e}")


class PerformanceTestRunnerV2_1:
    """性能テストランナー v2.1"""

    def __init__(
        self,
        patentfield_key_path: str = "../patentfield_key.json",
        claude_key_path: str = None,
        gemini_key_path: str = "../ttdc-in-house-dev-3e07247326cb.json",
        output_dir: str = "tests/performance_test",
        enable_parallel: bool = True,
        max_workers: int = 5
    ):
        """
        初期化

        Args:
            patentfield_key_path: PatentField APIキーファイル
            claude_key_path: Claude APIキー（環境変数ANTHROPIC_API_KEY使用）
            gemini_key_path: Gemini認証情報ファイル
            output_dir: 出力ディレクトリ
            enable_parallel: 並列処理を有効化
            max_workers: 並列ワーカー数
        """
        # 出力ディレクトリ作成
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "patent_texts").mkdir(exist_ok=True)

        # キャッシュシステム
        self.cache = HierarchicalCache()

        # PatentField API設定
        with open(patentfield_key_path, 'r') as f:
            pf_config = json.load(f)
            self.pf_api_key = pf_config['PATENTFIELD_API_KEY']
            self.pf_endpoint = pf_config['endpoint']

        self.pf_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.pf_api_key}'
        }

        # 認証情報パス
        self.gemini_credentials = gemini_key_path

        # 並列処理設定
        self.enable_parallel = enable_parallel
        self.max_workers = max_workers

        # メトリクス収集
        self.metrics = {
            'test_cases': [],
            'summary': {},
            'errors': []
        }

        # 料金レート（2025年11月、157円/USD）
        self.pricing = {
            'claude_sonnet4': {
                'input_per_1m': 471,
                'output_per_1m': 2355
            },
            'gemini_15_pro': {
                'input_per_1m': 196,
                'output_per_1m': 1570
            }
        }

        logger.info("✓ PerformanceTestRunner v2.1 初期化完了")
        logger.info(f"  並列処理: {'有効' if enable_parallel else '無効'} (ワーカー数: {max_workers})")

    # ============================================================
    # Step 1: データ準備
    # ============================================================

    def prepare_test_data(
        self,
        csv1: str = "tests/xy_data1.csv",
        csv2: str = "tests/xy_data2.csv",
        n_samples: int = 30
    ) -> pd.DataFrame:
        """テストデータを準備"""
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
    # Step 2: 特許データ取得（複数番号タイプ対応）
    # ============================================================

    @retry(
        retry=retry_if_exception_type((requests.exceptions.RequestException, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def _call_patentfield_api(self, payload: Dict) -> requests.Response:
        """リトライロジック付きPatentField API呼び出し"""
        return requests.post(
            self.pf_endpoint,
            headers=self.pf_headers,
            json=payload,
            timeout=30
        )

    def fetch_patent_multitype(self, pub_id: str) -> Dict:
        """
        複数の番号タイプで特許を検索

        Args:
            pub_id: 公開番号（例: JP2014007731A）

        Returns:
            特許データ辞書（複数のID情報を含む）
        """
        # キャッシュ確認
        cached = self.cache.get('patent_data', pub_id)
        if cached:
            logger.debug(f"  ✓ キャッシュヒット: {pub_id}")
            return cached

        epodoc = pub_id.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        # 3種類の番号タイプで順次試行
        number_types = ['pub_id', 'app_id', 'exam_id']

        for nt in number_types:
            try:
                payload = {
                    "numbers": [{"n": epodoc, "t": nt}],
                    "columns": [
                        "app_doc_id", "pub_id", "app_id", "exam_id",
                        "app_claims", "grant_claims",
                        "description", "app_description"
                    ]
                }

                response = self._call_patentfield_api(payload)

                if response.status_code == 200:
                    data = response.json()
                    records = data.get('records', [])

                    if len(records) > 0:
                        record = records[0]

                        # 優先順位: app_claims > grant_claims
                        claims = record.get('app_claims', '')
                        if not claims:
                            claims = record.get('grant_claims', '')

                        description = record.get('app_description', '')
                        if not description:
                            description = record.get('description', '')

                        result = {
                            'pub_id': pub_id,
                            'original_pub_id': pub_id,
                            'matched_type': nt,
                            'app_doc_id': record.get('app_doc_id', ''),
                            'matched_pub_id': record.get('pub_id', ''),
                            'matched_app_id': record.get('app_id', ''),
                            'matched_exam_id': record.get('exam_id', ''),
                            'claims': claims,
                            'description': description,
                            'status': 'success'
                        }

                        logger.info(f"  ✓ 成功 (タイプ: {nt}): {record.get('app_doc_id', 'N/A')}")
                        logger.info(f"    請求の範囲: {len(claims)}文字, 詳細な説明: {len(description)}文字")

                        # キャッシュ保存
                        self.cache.set('patent_data', pub_id, result)
                        return result

            except Exception as e:
                logger.warning(f"  番号タイプ {nt} での検索失敗: {e}")
                continue

        # 全てのタイプで失敗
        result = {
            'pub_id': pub_id,
            'status': 'not_found',
            'error': '全ての番号タイプで検索失敗'
        }

        logger.error(f"  ✗ 失敗: {pub_id} が見つかりません")
        return result

    def fetch_batch_patent_data(self, pub_ids: List[str]) -> Dict[str, Dict]:
        """
        バッチで特許データ取得（並列処理対応）

        Args:
            pub_ids: 公開番号リスト

        Returns:
            {pub_id: patent_data}の辞書
        """
        logger.info("=" * 80)
        logger.info("Step 2: 特許データ取得")
        logger.info("=" * 80)

        results = {}

        if self.enable_parallel:
            # 並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_id = {
                    executor.submit(self.fetch_patent_multitype, pid): pid
                    for pid in pub_ids
                }

                for i, future in enumerate(as_completed(future_to_id), 1):
                    pid = future_to_id[future]
                    logger.info(f"[{i}/{len(pub_ids)}] {pid} 取得中...")

                    try:
                        patent_data = future.result()
                        results[pid] = patent_data
                    except Exception as e:
                        logger.error(f"  ✗ エラー: {e}")
                        results[pid] = {
                            'pub_id': pid,
                            'status': 'error',
                            'error': str(e)
                        }

                    time.sleep(0.1)  # API制限考慮
        else:
            # 逐次処理
            for i, pub_id in enumerate(pub_ids, 1):
                logger.info(f"[{i}/{len(pub_ids)}] {pub_id} 取得中...")
                patent_data = self.fetch_patent_multitype(pub_id)
                results[pub_id] = patent_data
                time.sleep(0.5)

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
            検索結果辞書
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
            metrics['tokens_claude_input'] += len(patent_data['claims'] + patent_data['description']) // 4
            metrics['tokens_claude_output'] += len(json.dumps(structure_result)) // 4
            logger.info(f"  ✓ 完了 ({metrics['time_structure']:.1f}秒)")

            # キーワード抽出
            logger.info("  ステップ2: キーワード抽出...")
            t2 = time.time()

            structure_file = self.output_dir / f"{pub_id}_structure.json"
            with open(structure_file, 'w', encoding='utf-8') as f:
                json.dump(structure_result, f, ensure_ascii=False, indent=2)

            keyword_extractor = PatentKeywordExtractor(
                self.gemini_credentials,
                "../patentfield_key.json"
            )
            keywords_result = keyword_extractor.extract_keywords(str(structure_file))

            metrics['time_keyword'] = time.time() - t2
            metrics['tokens_claude_input'] += len(json.dumps(structure_result)) // 4
            metrics['tokens_claude_output'] += len(json.dumps(keywords_result)) // 4
            logger.info(f"  ✓ 完了 ({metrics['time_keyword']:.1f}秒)")

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
            metrics['tokens_gemini_input'] += len(json.dumps(structure_result)) // 4
            metrics['tokens_gemini_output'] += len(json.dumps(classification_result)) // 4
            logger.info(f"  ✓ 完了 ({metrics['time_classification']:.1f}秒)")

            # PatentField検索
            logger.info("  ステップ4: PatentField検索...")
            t4 = time.time()

            keywords_file = self.output_dir / f"{pub_id}_keywords.json"
            with open(keywords_file, 'w', encoding='utf-8') as f:
                json.dump(keywords_result, f, ensure_ascii=False, indent=2)

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

            search_results = search_result.get('unique_patent_ids', [])

            metrics['total_time'] = time.time() - start_time

            logger.info(f"\n✓ パイプライン完了: {len(search_results)}件ヒット")
            logger.info(f"  総処理時間: {metrics['total_time']:.1f}秒\n")

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
    # Step 4: 結果検証（複数番号タイプ対応）
    # ============================================================

    def verify_result_multitype(
        self,
        search_results: List[str],
        himotuki_patent: str
    ) -> Dict:
        """
        複数IDタイプで検証

        Args:
            search_results: 検索結果の特許IDリスト
            himotuki_patent: 紐づいた特許番号

        Returns:
            検証結果辞書
        """
        # himotuki特許のマルチタイプ情報を取得
        himotuki_data = self.fetch_patent_multitype(himotuki_patent)

        if himotuki_data['status'] != 'success':
            return {
                'found': False,
                'rank': None,
                'total_results': len(search_results),
                'reason': f'himotuki特許 {himotuki_patent} が見つかりません',
                'searched_ids': []
            }

        # 検索すべきID候補（優先順位順）
        search_ids = [
            himotuki_data.get('app_doc_id'),
            himotuki_data.get('matched_pub_id'),
            himotuki_data.get('matched_app_id'),
            himotuki_data.get('matched_exam_id'),
            himotuki_patent  # 元の番号も
        ]

        # Noneや空文字列を除外
        search_ids = [sid for sid in search_ids if sid]

        # いずれかのIDが検索結果に含まれているか確認
        for search_id in search_ids:
            if search_id in search_results:
                rank = search_results.index(search_id) + 1
                logger.info(f"  ✓ 紐づいた特許発見: {search_id} (順位: {rank}/{len(search_results)})")
                return {
                    'found': True,
                    'rank': rank,
                    'matched_id': search_id,
                    'matched_type': himotuki_data.get('matched_type'),
                    'total_results': len(search_results),
                    'searched_ids': search_ids
                }

        logger.info(f"  ✗ 紐づいた特許未発見")
        logger.debug(f"    検索対象ID: {search_ids}")

        return {
            'found': False,
            'rank': None,
            'total_results': len(search_results),
            'searched_ids': search_ids
        }

    # ============================================================
    # Step 5: コスト計算
    # ============================================================

    def calculate_cost(self, metrics: Dict) -> Dict:
        """料金計算"""
        claude_input_cost = (
            metrics['tokens_claude_input'] / 1_000_000
        ) * self.pricing['claude_sonnet4']['input_per_1m']

        claude_output_cost = (
            metrics['tokens_claude_output'] / 1_000_000
        ) * self.pricing['claude_sonnet4']['output_per_1m']

        claude_cost = claude_input_cost + claude_output_cost

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
        logger.info("特許検索システム性能テスト v2.1 開始")
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

            # 結果検証（マルチタイプ対応）
            verification = self.verify_result_multitype(
                pipeline_result['search_results'],
                himotuki
            )

            # コスト計算
            if pipeline_result['status'] == 'success':
                cost = self.calculate_cost(pipeline_result['metrics'])
            else:
                cost = {'claude_cost': 0, 'gemini_cost': 0, 'total_cost': 0}

            # 記録
            test_case = {
                'test_id': idx + 1,
                'syutugan': syutugan,
                'himotuki': himotuki,
                'found': verification['found'],
                'rank': verification['rank'],
                'matched_id': verification.get('matched_id'),
                'matched_type': verification.get('matched_type'),
                'searched_ids': verification.get('searched_ids', []),
                'total_results': verification['total_results'],
                'status': pipeline_result['status'],
                'metrics': pipeline_result.get('metrics', {}),
                'cost': cost
            }

            self.metrics['test_cases'].append(test_case)

            # 結果表示
            if verification['found']:
                logger.info(f"✓ 成功: 紐づいた特許を発見（順位: {verification['rank']}/{verification['total_results']}）")
                logger.info(f"  マッチID: {verification.get('matched_id')} (タイプ: {verification.get('matched_type')})")
            else:
                logger.info(f"✗ 失敗: 紐づいた特許が見つかりませんでした")

            if cost['total_cost'] > 0:
                logger.info(f"  コスト: {cost['total_cost']:.2f}円")

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
            'version': 'v2.1',
            'total_test_cases': len(df_test),
            'successful_tests': len(successful_tests),
            'found_count': found_count,
            'recall': round(recall, 3),
            'total_time': round(total_test_time, 2),
            'avg_time_per_case': round(avg_time, 2),
            'total_cost_jpy': round(total_cost, 2),
            'avg_cost_per_case': round(total_cost / len(df_test), 2),
            'parallel_enabled': self.enable_parallel,
            'max_workers': self.max_workers
        }

        # 結果表示
        logger.info(f"\n性能テスト結果サマリー (v2.1):")
        logger.info(f"  テストケース数: {self.metrics['summary']['total_test_cases']}")
        logger.info(f"  成功: {self.metrics['summary']['successful_tests']}")
        logger.info(f"  紐づいた特許発見: {found_count}/{len(successful_tests)}")
        logger.info(f"  Recall: {recall:.1%}")
        logger.info(f"  総処理時間: {total_test_time:.1f}秒")
        logger.info(f"  平均処理時間: {avg_time:.1f}秒/件")
        logger.info(f"  総コスト: {total_cost:.2f}円")
        logger.info(f"  平均コスト: {total_cost / len(df_test):.2f}円/件")

        # 結果保存
        result_file = self.output_dir / "test_results_v2_1.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)

        logger.info(f"\n✓ テスト結果保存: {result_file}")

        return self.metrics


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(
        description='特許検索システム性能テスト v2.1'
    )
    parser.add_argument(
        '-n', '--samples',
        type=int,
        default=30,
        help='テストサンプル数 (default: 30)'
    )
    parser.add_argument(
        '--no-parallel',
        action='store_true',
        help='並列処理を無効化'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='並列ワーカー数 (default: 5)'
    )

    args = parser.parse_args()

    # テスト実行
    runner = PerformanceTestRunnerV2_1(
        enable_parallel=not args.no_parallel,
        max_workers=args.workers
    )
    results = runner.run_test(n_samples=args.samples)

    print("\n" + "=" * 80)
    print("性能テスト完了 (v2.1)")
    print("=" * 80)
    print(f"Recall: {results['summary']['recall']:.1%}")
    print(f"総コスト: {results['summary']['total_cost_jpy']:.2f}円")
    print(f"並列処理: {'有効' if results['summary']['parallel_enabled'] else '無効'}")
    print("=" * 80)


if __name__ == '__main__':
    main()
