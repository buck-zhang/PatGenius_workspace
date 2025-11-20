"""Complete system test with all components."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
import numpy as np

def test_embeddings():
    """Test embedding models."""
    logger.info("=" * 60)
    logger.info("Testing Embedding Models")
    logger.info("=" * 60)

    try:
        from core.embeddings import TextEmbedding, ImageEmbedding

        # Test text embedding
        logger.info("Loading text embedding model...")
        text_embedder = TextEmbedding()
        logger.success(f"✓ Text model loaded (dimension: {text_embedder.dimension})")

        # Test embedding generation
        test_text = "agricultural hand tools"
        embedding = text_embedder.embed_single(test_text)
        logger.info(f"  Sample embedding shape: {embedding.shape}")
        logger.info(f"  Sample values: {embedding[:5]}")
        logger.success("✓ Text embedding generation successful")

        # Test image embedding
        logger.info("\nLoading CLIP image embedding model...")
        image_embedder = ImageEmbedding()
        logger.success(f"✓ CLIP model loaded (dimension: {image_embedder.dimension})")

        # Test text embedding in CLIP space
        clip_text_embedding = image_embedder.embed_text_for_image_search(test_text)
        logger.info(f"  CLIP text embedding shape: {clip_text_embedding.shape}")
        logger.success("✓ CLIP text embedding successful")

        return True

    except Exception as e:
        logger.error(f"✗ Embedding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_store_operations():
    """Test vector store operations."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Vector Store Operations")
    logger.info("=" * 60)

    try:
        from core.vector_store import VectorStore
        from core.embeddings import TextEmbedding
        from models.patent_class import PatentClassification

        # Initialize
        text_embedder = TextEmbedding()
        vector_store = VectorStore(
            host="localhost",
            port=6333,
            collection_name="test_collection",
            vector_dimension=text_embedder.dimension
        )

        # Create test collection
        logger.info("Creating test collection...")
        vector_store.create_collection(recreate=True)
        logger.success("✓ Test collection created")

        # Create test data
        test_classifications = [
            PatentClassification(
                code="A01B1/00",
                classification_type="IPC",
                dot_number=7,
                title_en="Hand tools",
                title_ja="手工具",
                parent_code="A01B",
                concordance="A01B1/00",
                document_count=1737
            ),
            PatentClassification(
                code="H04L29/06",
                classification_type="IPC",
                dot_number=8,
                title_en="Communication protocols",
                title_ja="通信プロトコル",
                parent_code="H04L29",
                concordance="H04L29/06",
                document_count=5000
            )
        ]

        # Generate embeddings
        texts = [f"{c.code} {c.title_en} {c.title_ja}" for c in test_classifications]
        embeddings = text_embedder.embed_text(texts)

        # Insert
        logger.info("Inserting test data...")
        vector_store.insert_classifications(test_classifications, embeddings)
        logger.success("✓ Data inserted successfully")

        # Search
        logger.info("Testing search...")
        query = "agricultural equipment"
        query_embedding = text_embedder.embed_single(query)
        results = vector_store.search(query_embedding, limit=2)

        logger.info(f"Search query: '{query}'")
        logger.info(f"Results found: {len(results)}")
        for i, result in enumerate(results, 1):
            logger.info(f"  {i}. {result.classification.code}: {result.classification.title_en}")
            logger.info(f"     Score: {result.similarity_score:.4f}")

        logger.success("✓ Search successful")

        # Cleanup
        vector_store.client.delete_collection("test_collection")
        logger.info("Test collection cleaned up")

        return True

    except Exception as e:
        logger.error(f"✗ Vector store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complete_data_loading():
    """Test loading complete dataset statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Complete Data Loading")
    logger.info("=" * 60)

    try:
        from core.data_loader import ClassificationDataLoader

        data_path = Path("../data_20250812")
        loader = ClassificationDataLoader(data_path)

        logger.info("Analyzing all data files...")
        stats = loader.get_statistics()

        logger.info("\nComplete Dataset Statistics:")
        logger.info("=" * 60)
        for key, value in stats.items():
            logger.info(f"  {key:10s}: {value:,}")
        logger.info("=" * 60)

        logger.success("✓ Data loading test successful")
        return True

    except Exception as e:
        logger.error(f"✗ Data loading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run complete system test."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 10 + "COMPLETE SYSTEM TEST" + " " * 28 + "║")
    logger.info("║" + " " * 5 + "Patent Classification Search v2.0" + " " * 20 + "║")
    logger.info("╚" + "=" * 58 + "╝")

    results = []

    # Run tests
    results.append(("Embedding Models", test_embeddings()))
    results.append(("Vector Store Operations", test_vector_store_operations()))
    results.append(("Complete Data Loading", test_complete_data_loading()))

    # Summary
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 18 + "TEST SUMMARY" + " " * 28 + "║")
    logger.info("╠" + "=" * 58 + "╣")

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        padding = " " * (40 - len(test_name))
        logger.info(f"║  {test_name}{padding}{status}      ║")

    logger.info("╠" + "=" * 58 + "╣")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    status_text = "ALL TESTS PASSED!" if passed == total else f"{passed}/{total} TESTS PASSED"
    padding = " " * (40 - len(status_text))
    logger.info(f"║  {status_text}{padding}          ║")

    logger.info("╚" + "=" * 58 + "╝")

    return all(r for _, r in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
