#!/usr/bin/env python3
"""
JP2014007731A 特許の構成要件分割デモ
Google Patents APIでPDFを取得 → テキスト抽出 → 構成要件分割
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path

from patent_component_analyzer import GeminiClient, PatentComponentAnalyzer, save_components_to_json


# ============================================================================
# Configuration
# ============================================================================

SERVICE_ACCOUNT_PATH = "/Volumes/T7/patgenius/zhang_opera/ttdc-in-house-dev-3e07247326cb.json"
GOOGLE_PATENTS_API_URL = "http://localhost:8001"
PATENT_NUMBER = "JP2014007731A"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Functions
# ============================================================================

def get_patent_pdf_url(patent_number: str) -> str:
    """
    Google Patents APIで特許番号からPDF URLを取得

    Args:
        patent_number: 特許番号（例: JP2014007731A）

    Returns:
        PDF URL
    """
    try:
        # Google Patents APIで検索
        response = requests.post(
            f"{GOOGLE_PATENTS_API_URL}/search",
            json={
                "keywords": [patent_number],
                "max_results": 1
            },
            timeout=60
        )
        response.raise_for_status()

        data = response.json()

        if data.get('patents') and len(data['patents']) > 0:
            patent = data['patents'][0]
            pdf_url = patent.get('pdf_url')

            if pdf_url:
                logger.info(f"PDF URL found: {pdf_url}")
                return pdf_url
            else:
                # PDFダウンロードAPIを使用
                logger.info("Using PDF download API...")
                download_response = requests.post(
                    f"{GOOGLE_PATENTS_API_URL}/download_pdf",
                    json={"patent_number": patent_number},
                    timeout=120
                )

                if download_response.status_code == 200:
                    download_data = download_response.json()
                    local_path = download_data.get('local_path')
                    logger.info(f"PDF downloaded to: {local_path}")
                    return local_path
                else:
                    raise ValueError("PDF download failed")
        else:
            raise ValueError(f"Patent {patent_number} not found")

    except Exception as e:
        logger.error(f"Failed to get PDF URL: {e}")
        raise


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    PDFファイルからテキストを抽出

    Args:
        pdf_path: PDFファイルパス

    Returns:
        抽出されたテキスト
    """
    try:
        import PyPDF2

        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""

            logger.info(f"Extracting text from {len(pdf_reader.pages)} pages...")

            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += page_text

                if i < 3:  # 最初の3ページの情報を表示
                    logger.info(f"Page {i+1}: {len(page_text)} characters")

            logger.info(f"Total text extracted: {len(text)} characters")
            return text

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise


def download_pdf_from_url(url: str, output_path: str) -> str:
    """
    URLからPDFをダウンロード

    Args:
        url: PDF URL
        output_path: 保存先パス

    Returns:
        保存されたファイルパス
    """
    try:
        logger.info(f"Downloading PDF from: {url}")

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            f.write(response.content)

        logger.info(f"PDF saved to: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        raise


def analyze_jp2014007731a():
    """JP2014007731Aの構成要件分割を実行"""

    logger.info("=" * 80)
    logger.info(f"特許 {PATENT_NUMBER} の構成要件分割デモ")
    logger.info("=" * 80)

    # ステップ1: PDFを取得
    logger.info(f"\n[Step 1] PDFを取得中...")

    pdf_path = f"./patents_pdf/{PATENT_NUMBER}.pdf"
    os.makedirs("./patents_pdf", exist_ok=True)

    # ローカルにPDFが既に存在するか確認
    if os.path.exists(pdf_path):
        logger.info(f"Using existing PDF: {pdf_path}")
    else:
        try:
            # Google Patents APIでPDF URLを取得
            pdf_url_or_path = get_patent_pdf_url(PATENT_NUMBER)

            if pdf_url_or_path.startswith('http'):
                # URLの場合はダウンロード
                pdf_path = download_pdf_from_url(pdf_url_or_path, pdf_path)
            else:
                # ローカルパスの場合はそのまま使用
                pdf_path = pdf_url_or_path

        except Exception as e:
            logger.error(f"Failed to get PDF: {e}")
            logger.info("\nNote: Make sure Google Patents API is running at http://localhost:8001")
            logger.info("Alternative: You can manually download the PDF and place it at:")
            logger.info(f"  {pdf_path}")
            return None

    # ステップ2: PDFからテキストを抽出
    logger.info(f"\n[Step 2] PDFからテキストを抽出中...")

    try:
        patent_text = extract_text_from_pdf(pdf_path)

        # 抽出したテキストをファイルに保存
        text_output_path = f"./patents_pdf/{PATENT_NUMBER}.txt"
        with open(text_output_path, 'w', encoding='utf-8') as f:
            f.write(patent_text)
        logger.info(f"Extracted text saved to: {text_output_path}")

        # テキストのプレビュー
        logger.info("\nText preview (first 500 characters):")
        logger.info("-" * 80)
        logger.info(patent_text[:500])
        logger.info("-" * 80)

    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        return None

    # ステップ3: Geminiクライアントを初期化
    logger.info(f"\n[Step 3] Gemini 2.5 Pro (Vertex AI) を初期化中...")

    try:
        gemini_client = GeminiClient(
            service_account_path=SERVICE_ACCOUNT_PATH,
            project_id="ttdc-in-house-dev",
            location="us-central1",
            model_name="gemini-2.5-pro"
        )
        logger.info("✓ Gemini client initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        logger.info("\nNote: Make sure the service account JSON file exists at:")
        logger.info(f"  {SERVICE_ACCOUNT_PATH}")
        return None

    # ステップ4: 構成要件分割を実行
    logger.info(f"\n[Step 4] 構成要件分割を実行中...")
    logger.info("This may take a few minutes...")

    try:
        analyzer = PatentComponentAnalyzer(gemini_client)
        components = analyzer.analyze_patent_components(patent_text)

        logger.info(f"\n✓ 構成要件分割完了: {len(components)}個の構成要素を抽出")

    except Exception as e:
        logger.error(f"Failed to analyze components: {e}")
        return None

    # ステップ5: 結果を表示・保存
    logger.info(f"\n[Step 5] 結果を保存中...")

    # 結果を表示
    logger.info("\n" + "=" * 80)
    logger.info("構成要素リスト")
    logger.info("=" * 80)

    for i, comp in enumerate(components, 1):
        logger.info(f"\n{i}. [{comp.構成要素番号}] {comp.構成要素}")
        logger.info(f"   簡単説明: {comp.構成要素の簡単説明}")
        logger.info(f"   重要度: {comp.構成要素の重要度}")
        logger.info(f"   従属関係: {comp.構成要素の従属関係}")
        logger.info(f"   サポート箇所: {comp.構成要素のサポート箇所[:100]}...")

    # JSONファイルに保存
    json_output_path = f"./{PATENT_NUMBER}_components.json"
    save_components_to_json(components, json_output_path)
    logger.info(f"\n✓ 構成要素をJSONファイルに保存: {json_output_path}")

    # 人間が読みやすい形式でも保存
    readable_output_path = f"./{PATENT_NUMBER}_components_readable.txt"
    with open(readable_output_path, 'w', encoding='utf-8') as f:
        f.write(f"特許番号: {PATENT_NUMBER}\n")
        f.write(f"構成要素数: {len(components)}\n")
        f.write("=" * 80 + "\n\n")

        for i, comp in enumerate(components, 1):
            f.write(f"{i}. [{comp.構成要素番号}] {comp.構成要素}\n")
            f.write(f"   簡単説明: {comp.構成要素の簡単説明}\n")
            f.write(f"   重要度: {comp.構成要素の重要度}\n")
            f.write(f"   従属関係: {comp.構成要素の従属関係}\n")
            f.write(f"   サポート箇所: {comp.構成要素のサポート箇所}\n")
            f.write("\n" + "-" * 80 + "\n\n")

    logger.info(f"✓ 読みやすい形式でも保存: {readable_output_path}")

    logger.info("\n" + "=" * 80)
    logger.info("デモ完了")
    logger.info("=" * 80)
    logger.info(f"\n出力ファイル:")
    logger.info(f"  1. PDF: {pdf_path}")
    logger.info(f"  2. テキスト: {text_output_path}")
    logger.info(f"  3. 構成要素JSON: {json_output_path}")
    logger.info(f"  4. 構成要素テキスト: {readable_output_path}")

    return components


# ============================================================================
# Main
# ============================================================================

def main():
    """メイン処理"""
    try:
        components = analyze_jp2014007731a()

        if components:
            return 0
        else:
            return 1

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
