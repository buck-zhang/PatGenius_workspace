"""Test data loader functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# Import with absolute imports
from core.data_loader import ClassificationDataLoader
from models.patent_class import PatentClassification


def test_load_sample_data():
    """Test loading a small sample of classification data."""
    logger.info("=" * 60)
    logger.info("Testing Data Loader")
    logger.info("=" * 60)

    data_path = Path("../data_20250812")
    loader = ClassificationDataLoader(data_path)

    # Test loading IPC file
    logger.info("\nTesting IPC file parsing...")
    ipc_file = data_path / "data_ipc" / "ipc_A01B.txt"
    if ipc_file.exists():
        count = 0
        for classification in loader.parse_ipc_file(ipc_file):
            if count < 3:
                logger.info(f"  Code: {classification.code}")
                logger.info(f"  Type: {classification.classification_type}")
                logger.info(f"  Title EN: {classification.title_en}")
                logger.info(f"  Title JA: {classification.title_ja}")
                logger.info(f"  Docs: {classification.document_count}")
                logger.info(f"  ---")
            count += 1
        logger.success(f"✓ Parsed {count} IPC classifications from {ipc_file.name}")
    else:
        logger.warning(f"✗ IPC file not found: {ipc_file}")

    # Test loading CPC file
    logger.info("\nTesting CPC file parsing...")
    cpc_file = data_path / "data_cpc_interleave" / "cpc_A01B.txt"
    if cpc_file.exists():
        count = 0
        for classification in loader.parse_cpc_file(cpc_file):
            if count < 3:
                logger.info(f"  Code: {classification.code}")
                logger.info(f"  Type: {classification.classification_type}")
                logger.info(f"  Title EN: {classification.title_en}")
                logger.info(f"  Title JA: {classification.title_ja}")
                logger.info(f"  ---")
            count += 1
        logger.success(f"✓ Parsed {count} CPC classifications from {cpc_file.name}")
    else:
        logger.warning(f"✗ CPC file not found: {cpc_file}")

    # Test loading FI file
    logger.info("\nTesting FI file parsing...")
    fi_file = data_path / "data_fi" / "fi_A01B.txt"
    if fi_file.exists():
        count = 0
        for classification in loader.parse_fi_file(fi_file):
            if count < 3:
                logger.info(f"  Code: {classification.code}")
                logger.info(f"  Type: {classification.classification_type}")
                logger.info(f"  Title EN: {classification.title_en}")
                logger.info(f"  Title JA: {classification.title_ja}")
                logger.info(f"  Theme: {classification.theme}")
                logger.info(f"  ---")
            count += 1
        logger.success(f"✓ Parsed {count} FI classifications from {fi_file.name}")
    else:
        logger.warning(f"✗ FI file not found: {fi_file}")

    # Get statistics
    logger.info("\nGetting overall statistics (this may take a moment)...")
    stats = loader.get_statistics()
    logger.info("=" * 60)
    logger.info("Data Statistics:")
    logger.info("=" * 60)
    for key, value in stats.items():
        logger.info(f"  {key}: {value:,}")

    logger.success("\n✓ Data loader test completed successfully!")


if __name__ == "__main__":
    test_load_sample_data()
