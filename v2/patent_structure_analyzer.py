#!/usr/bin/env python3
"""
特許構成要件分割システム
Claude Sonnet 4.5 (Vertex AI) を使用した自動構成要件分割

作成日: 2025年
対象: 特許審査における先行文献調査実務
"""

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Union, Optional
import sys

# Google Cloud / Vertex AI
from google.oauth2 import service_account
from anthropic import AnthropicVertex

# PDF処理
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("警告: PyMuPDF (fitz) がインストールされていません。PDF処理は利用できません。")
    print("インストール: pip install PyMuPDF")


class PatentStructureAnalyzer:
    """特許構成要件分割アナライザー"""

    def __init__(
        self,
        credentials_path: str,
        project_id: str = "ttdc-in-house-dev",
        region: str = "us-east5",
        model: str = "claude-sonnet-4-5@20250929"
    ):
        """
        初期化

        Args:
            credentials_path: サービスアカウントJSONファイルのパス
            project_id: Google Cloud プロジェクトID
            region: Vertex AIリージョン
            model: Claude モデル名
        """
        self.project_id = project_id
        self.region = region
        self.model = model

        # 認証情報の読み込み
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

        # Claude クライアントの初期化
        self.client = AnthropicVertex(
            project_id=self.project_id,
            region=self.region,
            credentials=self.credentials
        )

        # 分割ガイドの読み込み
        self.guide_content = self._load_guide()

    def _load_guide(self) -> str:
        """構成要件分割ガイドを読み込む"""
        guide_path = Path(__file__).parent / "特許検索のための構成要件分割ガイド.md"

        if not guide_path.exists():
            print(f"警告: 分割ガイドが見つかりません: {guide_path}")
            return ""

        with open(guide_path, 'r', encoding='utf-8') as f:
            return f.read()

    def load_patent_file(self, filepath: Union[str, Path]) -> str:
        """
        特許ファイルを読み込みテキストを抽出

        Args:
            filepath: ファイルパス（.txt, .pdf, .xml）

        Returns:
            抽出されたテキスト
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

        # 拡張子で処理を分岐
        ext = filepath.suffix.lower()

        if ext == '.txt':
            return self._load_text(filepath)
        elif ext == '.pdf':
            return self._load_pdf(filepath)
        elif ext == '.xml':
            return self._load_xml(filepath)
        else:
            raise ValueError(f"サポートされていないファイル形式: {ext}")

    def _load_text(self, filepath: Path) -> str:
        """テキストファイルを読み込む"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_pdf(self, filepath: Path) -> str:
        """PDFファイルを読み込む"""
        if not PDF_AVAILABLE:
            raise RuntimeError("PyMuPDFがインストールされていません")

        doc = fitz.open(filepath)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text_parts.append(page.get_text())

        doc.close()

        return "\n\n".join(text_parts)

    def _load_xml(self, filepath: Path) -> str:
        """XMLファイルを読み込む"""
        tree = ET.parse(filepath)
        root = tree.getroot()

        # XMLの全テキストコンテンツを抽出
        text_parts = []

        def extract_text(element):
            if element.text:
                text_parts.append(element.text.strip())
            for child in element:
                extract_text(child)
                if child.tail:
                    text_parts.append(child.tail.strip())

        extract_text(root)

        return "\n".join([t for t in text_parts if t])

    def build_prompt(self, patent_text: str) -> tuple[str, str]:
        """
        Claude APIへのプロンプトを構築

        Args:
            patent_text: 特許全文テキスト

        Returns:
            (system_prompt, user_prompt) のタプル
        """
        # システムプロンプト：分割ガイドの内容
        system_prompt = f"""あなたは特許審査における先行文献調査の専門家です。
以下の「特許検索のための構成要件分割ガイド」に基づいて、特許の構成要件を分割・分析してください。

{self.guide_content}

【重要な分割の原則】
1. 発明全体と完全に一致する先行技術は稀であり、発明を小さな要素に分解することで、個々の要素や組み合わせを開示する文献を広く探し出せます
2. 新規性だけでなく進歩性（容易に思いつけたか否か）も重要です
3. 各構成要件が公知か、組み合わせが容易かを検討するため、発明を要素に分解します
4. 分割した構成要件ごとにキーワードや特許分類を検討することで、より的確な検索式を作成できます

【分割方法】（特許内容に応じて適切な方法を選択）
- クレームの文言に従う（接続詞や句読点で区切る）
- 機能的・構造的単位で区切る（部品・部材、役割・機能）
- 発明の課題解決手段を意識する（特徴部分は詳細に分割）
- 必須の構成か任意の構成かを見極める

【注意点】
- 細かすぎる分割は避ける（意味のある機能的・構造的まとまりを意識）
- 発明の一体性を念頭に置く（要素の組み合わせで効果を奏する）"""

        # ユーザープロンプト：特許全文と出力フォーマット指示
        user_prompt = f"""以下の特許データを分析し、構成要件を分割してください。

【特許全文】
{patent_text}

【出力要求】
1. 各請求項ごとに分析
2. 構成要素の番号付け：
   - 請求項: 1, 2, 3, ...
   - 請求項内の要素: a, b, c, ...
   - 例: 請求項1の要素a → "1a"
3. 各構成要素について以下を出力：
   - 構成要素番号: "1a", "1b", "2a" など
   - 構成要素: 要素のテキスト
   - 構成要素のサポート箇所: 明細書の該当箇所（段落番号など）
   - 構成要素の簡単説明: 要素の役割・機能の説明
   - 従属関係: 前後の構成要件との関係（記号で表記、例: "→1b, →1c"）
   - 構成要素の重要度: 0〜1の数値（1が最も重要）

【出力フォーマット（JSON配列）】
必ず以下のJSON形式で出力してください：

[
  {{
    "構成要素番号": "1a",
    "構成要素": "太陽電池モジュール",
    "構成要素のサポート箇所": "[0002]太陽電池モジュールは...",
    "構成要素の簡単説明": "発明の主体となる装置",
    "従属関係": "→1b, →1c",
    "構成要素の重要度": 0.9
  }},
  {{
    "構成要素番号": "1b",
    "構成要素": "第1保護部材",
    "構成要素のサポート箇所": "[0015]第1保護部材は透光性を有し...",
    "構成要素の簡単説明": "太陽光を透過させる保護層",
    "従属関係": "←1a, →1c",
    "構成要素の重要度": 0.7
  }}
]

JSON配列のみを出力し、他の説明文は含めないでください。"""

        return system_prompt, user_prompt

    def analyze(
        self,
        patent_text: str,
        max_tokens: int = 8000,
        temperature: float = 0.0
    ) -> Dict:
        """
        特許テキストを分析して構成要件を抽出

        Args:
            patent_text: 特許全文テキスト
            max_tokens: 最大トークン数
            temperature: 温度パラメータ（0.0で決定的）

        Returns:
            分析結果の辞書
        """
        start_time = time.time()

        # プロンプト構築
        system_prompt, user_prompt = self.build_prompt(patent_text)

        print("Claude API に送信中...")

        try:
            # Claude API呼び出し
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # レスポンスからテキストを抽出
            response_text = response.content[0].text

            # トークン使用量
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }

            # JSONパース
            # レスポンステキストからJSON部分を抽出
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("レスポンスにJSON配列が含まれていません")

            json_text = response_text[json_start:json_end]
            構成要件リスト = json.loads(json_text)

            # 処理時間
            processing_time = time.time() - start_time

            # 結果を構造化
            result = {
                "status": "success",
                "構成要件": 構成要件リスト,
                "tokens": usage,
                "処理時間_秒": round(processing_time, 2),
                "model": self.model,
                "raw_response": response_text  # デバッグ用
            }

            return result

        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "error_type": "JSON_PARSE_ERROR",
                "message": f"JSONパースエラー: {str(e)}",
                "raw_response": response_text if 'response_text' in locals() else None
            }

        except Exception as e:
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e)
            }

    def analyze_file(
        self,
        input_filepath: Union[str, Path],
        output_filepath: Optional[Union[str, Path]] = None,
        max_tokens: int = 8000
    ) -> Dict:
        """
        ファイルから特許データを読み込んで分析

        Args:
            input_filepath: 入力ファイルパス
            output_filepath: 出力ファイルパス（Noneの場合は自動生成）
            max_tokens: 最大トークン数

        Returns:
            分析結果の辞書
        """
        input_filepath = Path(input_filepath)

        # ファイル読み込み
        print(f"ファイル読み込み中: {input_filepath}")
        patent_text = self.load_patent_file(input_filepath)

        print(f"テキスト抽出完了: {len(patent_text)} 文字")

        # 分析実行
        result = self.analyze(patent_text, max_tokens=max_tokens)

        # ファイル情報を追加
        result["input_file"] = str(input_filepath)

        # 出力ファイルパスの決定
        if output_filepath is None:
            output_filepath = input_filepath.parent / f"{input_filepath.stem}_構成要件.json"
        else:
            output_filepath = Path(output_filepath)

        # 結果を保存
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n結果を保存しました: {output_filepath}")

        return result

    def print_summary(self, result: Dict):
        """分析結果のサマリーを表示"""
        print("\n" + "="*60)
        print("構成要件分割 - 分析結果サマリー")
        print("="*60)

        if result['status'] == 'success':
            print(f"✓ 分析成功")
            print(f"\n構成要件数: {len(result['構成要件'])} 個")

            # トークン使用量
            tokens = result['tokens']
            print(f"\nトークン使用量:")
            print(f"  入力: {tokens['input_tokens']:,} tokens")
            print(f"  出力: {tokens['output_tokens']:,} tokens")
            print(f"  合計: {tokens['total_tokens']:,} tokens")

            print(f"\n処理時間: {result['処理時間_秒']} 秒")
            print(f"モデル: {result['model']}")

            # 構成要件の一覧
            print(f"\n構成要件一覧:")
            for i, item in enumerate(result['構成要件'][:10], 1):  # 最初の10個
                print(f"  {i}. [{item['構成要素番号']}] {item['構成要素'][:50]}...")
                print(f"     重要度: {item['構成要素の重要度']}")

            if len(result['構成要件']) > 10:
                print(f"  ... 他 {len(result['構成要件']) - 10} 個")

        else:
            print(f"✗ 分析失敗")
            print(f"エラータイプ: {result['error_type']}")
            print(f"エラーメッセージ: {result['message']}")


def main():
    """メイン実行関数（コマンドライン用）"""
    import argparse

    parser = argparse.ArgumentParser(
        description='特許構成要件分割システム（Claude Sonnet 4.5 via Vertex AI）'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='入力ファイル（.txt, .pdf, .xml）'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='出力ファイル（デフォルト: 入力ファイル名_構成要件.json）'
    )
    parser.add_argument(
        '-c', '--credentials',
        type=str,
        default='../ttdc-in-house-dev-3e07247326cb.json',
        help='サービスアカウントJSONファイル'
    )
    parser.add_argument(
        '-p', '--project',
        type=str,
        default='ttdc-in-house-dev',
        help='Google Cloud プロジェクトID'
    )
    parser.add_argument(
        '-m', '--max-tokens',
        type=int,
        default=8000,
        help='最大トークン数'
    )

    args = parser.parse_args()

    # アナライザー初期化
    analyzer = PatentStructureAnalyzer(
        credentials_path=args.credentials,
        project_id=args.project
    )

    # 分析実行
    result = analyzer.analyze_file(
        input_filepath=args.input_file,
        output_filepath=args.output,
        max_tokens=args.max_tokens
    )

    # サマリー表示
    analyzer.print_summary(result)

    # 終了コード
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
