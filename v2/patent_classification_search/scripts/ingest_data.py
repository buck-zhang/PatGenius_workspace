"""Data ingestion script to load patent classifications into Qdrant."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from tqdm import tqdm

from patent_classification_search.core.config import settings
from patent_classification_search.core.data_loader import ClassificationDataLoader
from patent_classification_search.core.embeddings import EmbeddingManager
from patent_classification_search.core.vector_store import VectorStore
from patent_classification_search.models.patent_class import PatentClassification


def create_embedding_text(classification: PatentClassification) -> str:
    """
    Create combined text for embedding generation.

    Args:
        classification: PatentClassification object

    Returns:
        Combined text string
    """
    parts = [
        classification.code,
        classification.title_en,
        classification.title_ja
    ]

    # Add theme for FI classifications
    if classification.theme:
        parts.append(f"Theme: {classification.theme}")

    return " | ".join(filter(None, parts))


def ingest_data(batch_size: int = 500, recreate_collection: bool = False):
    """
    Main data ingestion function.

    Args:
        batch_size: Number of records to process in each batch
        recreate_collection: If True, delete and recreate the collection
    """
    logger.info("=" * 80)
    logger.info("Starting Patent Classification Data Ingestion")
    logger.info("=" * 80)

    # Initialize components
    logger.info("Initializing components...")
    data_loader = ClassificationDataLoader(settings.data_path)
    embedding_manager = EmbeddingManager(
        text_model_name=settings.text_embedding_model,
        image_model_name=settings.image_embedding_model
    )
    vector_store = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection_name,
        vector_dimension=embedding_manager.text_dimension
    )

    # Create collection
    logger.info("Setting up Qdrant collection...")
    vector_store.create_collection(recreate=recreate_collection)

    # Get statistics
    logger.info("Analyzing data files...")
    stats = data_loader.get_statistics()
    logger.info(f"Data statistics: {stats}")

    # Process in batches
    logger.info(f"Processing classifications in batches of {batch_size}...")

    batch = []
    batch_texts = []
    total_processed = 0

    for classification in tqdm(
        data_loader.load_all_classifications(),
        total=stats["Total"],
        desc="Loading classifications"
    ):
        # Add to batch
        batch.append(classification)
        batch_texts.append(create_embedding_text(classification))

        # Process batch when full
        if len(batch) >= batch_size:
            # Generate embeddings
            logger.debug(f"Generating embeddings for batch of {len(batch)}")
            embeddings = embedding_manager.text_embedder.embed_text(batch_texts)

            # Insert into Qdrant
            logger.debug(f"Inserting batch into Qdrant")
            vector_store.insert_classifications(batch, embeddings)

            total_processed += len(batch)
            logger.info(f"Processed {total_processed}/{stats['Total']} classifications")

            # Reset batch
            batch = []
            batch_texts = []

    # Process remaining records
    if batch:
        logger.debug(f"Processing final batch of {len(batch)}")
        embeddings = embedding_manager.text_embedder.embed_text(batch_texts)
        vector_store.insert_classifications(batch, embeddings)
        total_processed += len(batch)

    logger.info("=" * 80)
    logger.info(f"Data ingestion completed!")
    logger.info(f"Total classifications processed: {total_processed}")

    # Get collection info
    info = vector_store.get_collection_info()
    logger.info(f"Collection info: {info}")

    # Get counts by type
    counts = vector_store.count_by_type()
    logger.info(f"Classifications by type: {counts}")
    logger.info("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest patent classification data into Qdrant")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for processing (default: 500)"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate collection (delete existing data)"
    )

    args = parser.parse_args()

    try:
        ingest_data(batch_size=args.batch_size, recreate_collection=args.recreate)
    except Exception as e:
        logger.error(f"Error during data ingestion: {e}")
        raise
