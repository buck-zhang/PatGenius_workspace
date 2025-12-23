"""Basic system test without ML models."""

from qdrant_client import QdrantClient
from loguru import logger
import sys

def test_qdrant_connection():
    """Test Qdrant connection."""
    logger.info("Testing Qdrant connection...")
    try:
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()
        logger.success(f"✓ Qdrant connected successfully")
        logger.info(f"Collections: {[c.name for c in collections.collections]}")
        return True
    except Exception as e:
        logger.error(f"✗ Qdrant connection failed: {e}")
        return False


def test_imports():
    """Test basic imports."""
    logger.info("Testing basic imports...")
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
        from pydantic_settings import BaseSettings
        logger.success("✓ All basic imports successful")
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_config():
    """Test configuration loading."""
    logger.info("Testing configuration...")
    try:
        sys.path.insert(0, "/Users/ttdc-user/Desktop/patgenius/zhang_opera/v2/patent_classification_search")
        from core.config import settings
        logger.success(f"✓ Configuration loaded")
        logger.info(f"  - Qdrant host: {settings.qdrant_host}:{settings.qdrant_port}")
        logger.info(f"  - Collection: {settings.qdrant_collection_name}")
        logger.info(f"  - API port: {settings.api_port}")
        logger.info(f"  - Data path: {settings.data_path}")
        return True
    except Exception as e:
        logger.error(f"✗ Configuration failed: {e}")
        return False


def test_data_path():
    """Test data path exists."""
    logger.info("Testing data path...")
    try:
        from pathlib import Path
        data_path = Path("../data_20250812")
        if data_path.exists():
            logger.success(f"✓ Data path exists: {data_path.absolute()}")

            # Check subdirectories
            ipc_dir = data_path / "data_ipc"
            cpc_dir = data_path / "data_cpc_interleave"
            fi_dir = data_path / "data_fi"

            logger.info(f"  - IPC files: {len(list(ipc_dir.glob('*.txt'))) if ipc_dir.exists() else 0}")
            logger.info(f"  - CPC files: {len(list(cpc_dir.glob('*.txt'))) if cpc_dir.exists() else 0}")
            logger.info(f"  - FI files: {len(list(fi_dir.glob('*.txt'))) if fi_dir.exists() else 0}")
            return True
        else:
            logger.warning(f"✗ Data path not found: {data_path.absolute()}")
            return False
    except Exception as e:
        logger.error(f"✗ Data path test failed: {e}")
        return False


def main():
    """Run all basic tests."""
    logger.info("=" * 60)
    logger.info("Running Basic System Tests")
    logger.info("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Qdrant Connection", test_qdrant_connection()))
    results.append(("Data Path", test_data_path()))

    logger.info("=" * 60)
    logger.info("Test Results Summary")
    logger.info("=" * 60)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name}: {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    logger.info("=" * 60)
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info("=" * 60)

    return all(r for _, r in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
