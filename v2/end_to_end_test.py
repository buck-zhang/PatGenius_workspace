#!/usr/bin/env python3
"""
エンドツーエンド統合テスト

構成分割から拒絶理由通知作成までの一連の処理を実行する。

処理フロー:
1. 構成分割 (PatentStructureAnalyzer)
2. キーワード抽出 (PatentKeywordExtractor)
3. 分類コード抽出 (PatentClassificationExtractor)
4. 検索式作成・実行 (PerComponentSearchExecutor)
5. 構成対比 (NoveltyAssessmentEngine)
6. 構成対比表生成 (ComparisonTableGenerator)
7. 拒絶理由通知生成 (RejectionNoticeGenerator)

使用例:
    # サンプル特許XMLで実行
    python end_to_end_test.py tests/jp2014007731A.xml

    # テスト番号で実行（combined_data.csvから）
    python end_to_end_test.py --test-number 1
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ステップ1-4のモジュール
from patent_structure_analyzer import PatentStructureAnalyzer
from patent_keyword_extractor import PatentKeywordExtractor
from patent_classification_extractor import PatentClassificationExtractor
from patent_search_executor_per_component import PerComponentSearchExecutor

# ステップ5-7のモジュール
sys.path.insert(0, str(Path(__file__).parent / "src"))
from novelty_assessment_engine import NoveltyAssessmentEngine
from comparison_table_generator import ComparisonTableGenerator
from rejection_notice_generator import RejectionNoticeGenerator


class EndToEndTest:
    """エンドツーエンドテスト実行クラス"""

    def __init__(
        self,
        google_credentials_path: str = None,
        patentfield_key_path: str = None,
        output_base_dir: str = None
    ):
        """
        初期化

        Args:
            google_credentials_path: Google Cloud認証情報
            patentfield_key_path: PatentField APIキー
            output_base_dir: 結果出力ディレクトリ
        """
        # デフォルトパスの設定
        base_dir = Path(__file__).parent
        self.google_credentials_path = google_credentials_path or str(
            base_dir.parent / "ttdc-in-house-dev-3e07247326cb.json"
        )
        self.patentfield_key_path = patentfield_key_path or str(
            base_dir / "patentfield_key.json"
        )
        self.output_base_dir = Path(output_base_dir or base_dir / "end_to_end_results")
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        # Google Cloud プロジェクト設定
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "ttdc-in-house-dev")

        # 統計情報
        self.stats = {
            'start_time': None,
            'end_time': None,
            'steps_completed': [],
            'steps_failed': [],
            'total_time_seconds': 0,
            'step_times': {}
        }

        print(f"\n{'='*80}")
        print(f"エンドツーエンドテスト初期化")
        print(f"{'='*80}")
        print(f"認証情報: {self.google_credentials_path}")
        print(f"PatentField API: {self.patentfield_key_path}")
        print(f"出力先: {self.output_base_dir}")
        print(f"プロジェクトID: {self.project_id}")
        print(f"{'='*80}\n")

    async def run_full_pipeline(
        self,
        patent_xml_path: str = None,
        patent_id: str = None,
        test_name: str = None
    ) -> Dict:
        """
        全処理を実行

        Args:
            patent_xml_path: 特許XMLファイルパス（XMLから処理する場合）
            patent_id: 特許番号（PatentField APIから取得する場合）
            test_name: テスト名（出力ディレクトリ名に使用）

        Returns:
            実行結果サマリー
        """
        self.stats['start_time'] = time.time()

        # テスト名の決定
        if test_name is None:
            if patent_xml_path:
                test_name = Path(patent_xml_path).stem
            elif patent_id:
                test_name = patent_id
            else:
                test_name = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 出力ディレクトリの作成
        output_dir = self.output_base_dir / test_name
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*80}")
        print(f"エンドツーエンドテスト開始: {test_name}")
        print(f"{'='*80}\n")

        results = {
            'test_name': test_name,
            'output_dir': str(output_dir),
            'steps': {}
        }

        try:
            # ステップ1: 構成分割
            structure_result = await self._step1_structure_analysis(
                patent_xml_path, patent_id, output_dir
            )
            results['steps']['step1_structure'] = structure_result

            # ステップ2: キーワード抽出
            keyword_result = await self._step2_keyword_extraction(
                structure_result['output_file'], output_dir
            )
            results['steps']['step2_keywords'] = keyword_result

            # ステップ3: 分類コード抽出
            classification_result = await self._step3_classification_extraction(
                structure_result['output_file'], output_dir
            )
            results['steps']['step3_classifications'] = classification_result

            # ステップ4: 検索式作成・実行
            search_result = await self._step4_search_execution(
                structure_result['output_file'],
                keyword_result['output_file'],
                classification_result['output_file'],
                output_dir
            )
            results['steps']['step4_search'] = search_result

            # ステップ5: 構成対比
            novelty_result = await self._step5_novelty_assessment(
                structure_result['output_file'],
                search_result['output_file'],
                output_dir
            )
            results['steps']['step5_novelty'] = novelty_result

            # ステップ6: 構成対比表生成
            comparison_table_result = await self._step6_comparison_table(
                novelty_result['summary_file'],
                novelty_result['comparisons_dir'],
                structure_result['output_file'],
                output_dir
            )
            results['steps']['step6_comparison_table'] = comparison_table_result

            # ステップ7: 拒絶理由通知生成
            rejection_result = await self._step7_rejection_notice(
                comparison_table_result['markdown_file'],
                novelty_result['summary_file'],
                structure_result['output_file'],
                output_dir
            )
            results['steps']['step7_rejection'] = rejection_result

            # 統計情報の更新
            self.stats['end_time'] = time.time()
            self.stats['total_time_seconds'] = self.stats['end_time'] - self.stats['start_time']
            results['stats'] = self.stats

            # 結果サマリーの保存
            summary_file = output_dir / "end_to_end_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # 成功メッセージ
            print(f"\n{'='*80}")
            print(f"✅ エンドツーエンドテスト完了")
            print(f"{'='*80}")
            print(f"テスト名: {test_name}")
            print(f"総処理時間: {self.stats['total_time_seconds']:.1f}秒")
            print(f"完了ステップ: {len(self.stats['steps_completed'])}/7")
            print(f"結果サマリー: {summary_file}")
            print(f"{'='*80}\n")

            # ステップごとの処理時間を表示
            self._print_step_times()

            # 最終成果物のパスを表示
            self._print_final_outputs(results)

            return results

        except Exception as e:
            print(f"\n❌ エラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()

            self.stats['end_time'] = time.time()
            self.stats['total_time_seconds'] = self.stats['end_time'] - self.stats['start_time']
            results['stats'] = self.stats
            results['error'] = str(e)

            # エラー結果も保存
            error_file = output_dir / "end_to_end_error.json"
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            raise

    async def _step1_structure_analysis(
        self, patent_xml_path: Optional[str], patent_id: Optional[str], output_dir: Path
    ) -> Dict:
        """ステップ1: 構成分割"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ1: 構成分割")
        print(f"{'='*80}\n")

        analyzer = PatentStructureAnalyzer(
            credentials_path=self.google_credentials_path
        )

        if patent_xml_path:
            result = await analyzer.analyze_patent_from_file(patent_xml_path)
        elif patent_id:
            # PatentField APIから取得して分析
            # TODO: 実装する
            raise NotImplementedError("特許番号からの取得は未実装です")
        else:
            raise ValueError("patent_xml_pathまたはpatent_idのいずれかを指定してください")

        # 結果を保存
        output_file = output_dir / "structure.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        step_time = time.time() - step_start
        self.stats['step_times']['step1_structure'] = step_time
        self.stats['steps_completed'].append('step1_structure')

        print(f"✅ ステップ1完了 ({step_time:.1f}秒)")
        print(f"   構成要素数: {len(result.get('構成要件', []))}個")
        print(f"   出力ファイル: {output_file}\n")

        return {
            'output_file': str(output_file),
            'element_count': len(result.get('構成要件', [])),
            'time_seconds': step_time
        }

    async def _step2_keyword_extraction(self, structure_file: str, output_dir: Path) -> Dict:
        """ステップ2: キーワード抽出"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ2: キーワード抽出")
        print(f"{'='*80}\n")

        extractor = PatentKeywordExtractor(
            credentials_path=self.google_credentials_path,
            patentfield_key_path=self.patentfield_key_path
        )

        with open(structure_file, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)

        result = await extractor.extract_keywords_for_all_elements(
            structure_data['構成要件']
        )

        # 結果を保存
        output_file = output_dir / "keywords.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        step_time = time.time() - step_start
        self.stats['step_times']['step2_keywords'] = step_time
        self.stats['steps_completed'].append('step2_keywords')

        print(f"✅ ステップ2完了 ({step_time:.1f}秒)")
        print(f"   出力ファイル: {output_file}\n")

        return {
            'output_file': str(output_file),
            'time_seconds': step_time
        }

    async def _step3_classification_extraction(
        self, structure_file: str, output_dir: Path
    ) -> Dict:
        """ステップ3: 分類コード抽出"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ3: 分類コード抽出")
        print(f"{'='*80}\n")

        extractor = PatentClassificationExtractor(
            credentials_path=self.google_credentials_path,
            patentfield_key_path=self.patentfield_key_path
        )

        with open(structure_file, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)

        result = extractor.extract_all_elements_classifications(
            structure_data['構成要件']
        )

        # 結果を保存
        output_file = output_dir / "classifications.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        step_time = time.time() - step_start
        self.stats['step_times']['step3_classifications'] = step_time
        self.stats['steps_completed'].append('step3_classifications')

        print(f"✅ ステップ3完了 ({step_time:.1f}秒)")
        print(f"   出力ファイル: {output_file}\n")

        return {
            'output_file': str(output_file),
            'time_seconds': step_time
        }

    async def _step4_search_execution(
        self,
        structure_file: str,
        keyword_file: str,
        classification_file: str,
        output_dir: Path
    ) -> Dict:
        """ステップ4: 検索式作成・実行"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ4: 検索式作成・実行")
        print(f"{'='*80}\n")

        executor = PerComponentSearchExecutor(
            credentials_path=self.google_credentials_path,
            patentfield_key_path=self.patentfield_key_path
        )

        with open(structure_file, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)
        with open(keyword_file, 'r', encoding='utf-8') as f:
            keyword_data = json.load(f)
        with open(classification_file, 'r', encoding='utf-8') as f:
            classification_data = json.load(f)

        result = await executor.execute_search_per_component(
            structure_data['構成要件'],
            keyword_data,
            classification_data
        )

        # 結果を保存
        output_file = output_dir / "search_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        step_time = time.time() - step_start
        self.stats['step_times']['step4_search'] = step_time
        self.stats['steps_completed'].append('step4_search')

        print(f"✅ ステップ4完了 ({step_time:.1f}秒)")
        print(f"   検索結果件数: {len(result.get('merged_patent_ids', []))}件")
        print(f"   出力ファイル: {output_file}\n")

        return {
            'output_file': str(output_file),
            'result_count': len(result.get('merged_patent_ids', [])),
            'time_seconds': step_time
        }

    async def _step5_novelty_assessment(
        self, structure_file: str, search_file: str, output_dir: Path
    ) -> Dict:
        """ステップ5: 構成対比"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ5: 構成対比（進歩性判断）")
        print(f"{'='*80}\n")

        # 構成対比結果の出力先
        novelty_dir = output_dir / "novelty_assessment"
        novelty_dir.mkdir(exist_ok=True)

        engine = NoveltyAssessmentEngine(
            project_id=self.project_id,
            location="global",
            model_name="gemini-3-pro-preview",
            patentfield_key_path=self.patentfield_key_path,
            output_dir=str(novelty_dir),
            max_workers=5
        )

        # 構成対比実行
        summary = engine.assess_novelty(
            base_patent_structure_file=structure_file,
            search_result_file=search_file,
            limit=None  # 全件処理
        )

        step_time = time.time() - step_start
        self.stats['step_times']['step5_novelty'] = step_time
        self.stats['steps_completed'].append('step5_novelty')

        print(f"✅ ステップ5完了 ({step_time:.1f}秒)")
        print(f"   X文献: {summary['x_references']['count']}件")
        print(f"   Y文献: {summary['y_references']['count']}件")
        print(f"   結果ディレクトリ: {novelty_dir}\n")

        return {
            'summary_file': str(novelty_dir / "novelty_assessment_summary.json"),
            'comparisons_dir': str(novelty_dir),
            'x_references_count': summary['x_references']['count'],
            'y_references_count': summary['y_references']['count'],
            'time_seconds': step_time
        }

    async def _step6_comparison_table(
        self,
        summary_file: str,
        comparisons_dir: str,
        structure_file: str,
        output_dir: Path
    ) -> Dict:
        """ステップ6: 構成対比表生成"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ6: 構成対比表生成")
        print(f"{'='*80}\n")

        generator = ComparisonTableGenerator()

        # Excel形式
        excel_file = output_dir / "comparison_table.xlsx"
        generator.generate_comparison_table(
            assessment_summary_path=summary_file,
            comparison_results_dir=comparisons_dir,
            base_structure_path=structure_file,
            output_path=str(excel_file),
            format="excel"
        )

        # Markdown形式
        markdown_file = output_dir / "comparison_table.md"
        generator.generate_comparison_table(
            assessment_summary_path=summary_file,
            comparison_results_dir=comparisons_dir,
            base_structure_path=structure_file,
            output_path=str(markdown_file),
            format="markdown"
        )

        step_time = time.time() - step_start
        self.stats['step_times']['step6_comparison_table'] = step_time
        self.stats['steps_completed'].append('step6_comparison_table')

        print(f"✅ ステップ6完了 ({step_time:.1f}秒)")
        print(f"   Excel: {excel_file}")
        print(f"   Markdown: {markdown_file}\n")

        return {
            'excel_file': str(excel_file),
            'markdown_file': str(markdown_file),
            'time_seconds': step_time
        }

    async def _step7_rejection_notice(
        self,
        comparison_table_md: str,
        summary_file: str,
        structure_file: str,
        output_dir: Path
    ) -> Dict:
        """ステップ7: 拒絶理由通知生成"""
        step_start = time.time()
        print(f"\n{'='*80}")
        print(f"ステップ7: 拒絶理由通知生成")
        print(f"{'='*80}\n")

        rejection_dir = output_dir / "rejection_notice"
        rejection_dir.mkdir(exist_ok=True)

        generator = RejectionNoticeGenerator()

        result_files = generator.generate_rejection_notice(
            comparison_table_path=comparison_table_md,
            assessment_summary_path=summary_file,
            base_structure_path=structure_file,
            output_dir=str(rejection_dir)
        )

        step_time = time.time() - step_start
        self.stats['step_times']['step7_rejection'] = step_time
        self.stats['steps_completed'].append('step7_rejection')

        print(f"✅ ステップ7完了 ({step_time:.1f}秒)")
        for file_type, file_path in result_files.items():
            print(f"   {file_type}: {file_path}")
        print()

        return {
            'output_files': result_files,
            'time_seconds': step_time
        }

    def _print_step_times(self):
        """ステップごとの処理時間を表示"""
        print(f"\n{'='*80}")
        print(f"ステップごとの処理時間")
        print(f"{'='*80}")
        for step, step_time in self.stats['step_times'].items():
            print(f"  {step}: {step_time:.1f}秒")
        print(f"{'='*80}\n")

    def _print_final_outputs(self, results: Dict):
        """最終成果物のパスを表示"""
        print(f"\n{'='*80}")
        print(f"最終成果物")
        print(f"{'='*80}")

        if 'step6_comparison_table' in results['steps']:
            ct = results['steps']['step6_comparison_table']
            print(f"📊 構成対比表:")
            print(f"   Excel: {ct['excel_file']}")
            print(f"   Markdown: {ct['markdown_file']}")

        if 'step7_rejection' in results['steps']:
            rn = results['steps']['step7_rejection']
            print(f"\n📝 拒絶理由通知書:")
            for file_type, file_path in rn['output_files'].items():
                print(f"   {file_type}: {file_path}")

        print(f"{'='*80}\n")


async def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="エンドツーエンド統合テスト")
    parser.add_argument(
        "patent_xml",
        nargs="?",
        help="特許XMLファイルパス"
    )
    parser.add_argument(
        "--test-number",
        type=int,
        help="テスト番号（combined_data.csvから取得）"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="出力ディレクトリ"
    )

    args = parser.parse_args()

    # 入力チェック
    if not args.patent_xml and not args.test_number:
        print("エラー: 特許XMLファイルまたは--test-numberを指定してください")
        parser.print_help()
        sys.exit(1)

    # テスト実行
    tester = EndToEndTest(output_base_dir=args.output_dir)

    if args.patent_xml:
        # XMLファイルから実行
        await tester.run_full_pipeline(
            patent_xml_path=args.patent_xml
        )
    elif args.test_number:
        # combined_data.csvから実行
        # TODO: CSVから特許情報を取得して実行
        print("エラー: --test-numberオプションは未実装です")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
