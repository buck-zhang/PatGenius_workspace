"""Vector store operations using Qdrant."""

from typing import List, Dict, Optional, Any
from uuid import uuid4
import numpy as np
from loguru import logger

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    SearchRequest,
    NamedVector
)

try:
    from ..models.patent_class import PatentClassification, SearchResult
except ImportError:
    from models.patent_class import PatentClassification, SearchResult


class VectorStore:
    """Manages patent classification vectors in Qdrant."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "patent_classifications",
        vector_dimension: int = 768
    ):
        """
        Initialize vector store connection.

        Args:
            host: Qdrant server host
            port: Qdrant server port
            collection_name: Name of the collection
            vector_dimension: Dimension of text embeddings
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension

        logger.info(f"Connecting to Qdrant at {host}:{port}")
        self.client = QdrantClient(host=host, port=port)

    def create_collection(self, recreate: bool = False) -> None:
        """
        Create Qdrant collection with proper configuration.

        Args:
            recreate: If True, delete existing collection and create new one
        """
        if recreate:
            logger.info(f"Deleting existing collection: {self.collection_name}")
            self.client.delete_collection(collection_name=self.collection_name)

        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dimension,
                    distance=Distance.COSINE
                )
            )
            logger.info("Collection created successfully")
        else:
            logger.info(f"Collection {self.collection_name} already exists")

    def _classification_to_payload(self, classification: PatentClassification) -> Dict[str, Any]:
        """
        Convert PatentClassification to Qdrant payload.

        Args:
            classification: PatentClassification object

        Returns:
            Dictionary payload for Qdrant
        """
        return {
            "code": classification.code,
            "classification_type": classification.classification_type,
            "dot_number": classification.dot_number,
            "title_en": classification.title_en,
            "title_ja": classification.title_ja,
            "parent_code": classification.parent_code,
            "theme": classification.theme,
            "concordance": classification.concordance,
            "document_count": classification.document_count or 0,
            # Combined text for better search
            "combined_text": f"{classification.code} {classification.title_en} {classification.title_ja}"
        }

    def _payload_to_classification(self, payload: Dict[str, Any]) -> PatentClassification:
        """
        Convert Qdrant payload to PatentClassification.

        Args:
            payload: Dictionary payload from Qdrant

        Returns:
            PatentClassification object
        """
        return PatentClassification(
            code=payload["code"],
            classification_type=payload["classification_type"],
            dot_number=payload["dot_number"],
            title_en=payload["title_en"],
            title_ja=payload["title_ja"],
            parent_code=payload.get("parent_code"),
            theme=payload.get("theme"),
            concordance=payload.get("concordance"),
            document_count=payload.get("document_count", 0)
        )

    def insert_classifications(
        self,
        classifications: List[PatentClassification],
        embeddings: np.ndarray,
        batch_size: int = 100
    ) -> None:
        """
        Insert patent classifications with embeddings into Qdrant.

        Args:
            classifications: List of PatentClassification objects
            embeddings: Numpy array of embeddings (shape: [n, dimension])
            batch_size: Batch size for insertion
        """
        total = len(classifications)
        logger.info(f"Inserting {total} classifications into Qdrant")

        points = []
        for i, (classification, embedding) in enumerate(zip(classifications, embeddings)):
            point_id = str(uuid4())
            payload = self._classification_to_payload(classification)

            point = PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload=payload
            )
            points.append(point)

            # Insert in batches
            if len(points) >= batch_size or i == total - 1:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.debug(f"Inserted batch of {len(points)} points")
                points = []

        logger.info(f"Successfully inserted {total} classifications")

    def search(
        self,
        query_vector: np.ndarray,
        limit: int = 20,
        classification_type: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        Search for similar classifications.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            classification_type: Filter by type (IPC, CPC, or FI)
            min_score: Minimum similarity score

        Returns:
            List of SearchResult objects
        """
        # Build filter
        filter_conditions = None
        if classification_type:
            filter_conditions = Filter(
                must=[
                    FieldCondition(
                        key="classification_type",
                        match=MatchValue(value=classification_type)
                    )
                ]
            )

        # Perform search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=limit,
            query_filter=filter_conditions,
            score_threshold=min_score
        )

        # Convert to SearchResult objects
        search_results = []
        for result in results:
            classification = self._payload_to_classification(result.payload)
            search_results.append(
                SearchResult(
                    classification=classification,
                    similarity_score=result.score
                )
            )

        return search_results

    def search_by_code(self, code: str) -> Optional[PatentClassification]:
        """
        Search for a specific classification by code.

        Args:
            code: Classification code

        Returns:
            PatentClassification if found, None otherwise
        """
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="code",
                        match=MatchValue(value=code)
                    )
                ]
            ),
            limit=1
        )

        if results[0]:  # results is a tuple (records, next_page_offset)
            return self._payload_to_classification(results[0][0].payload)
        return None

    def search_by_codes(self, codes: List[str]) -> List[PatentClassification]:
        """
        Search for multiple classifications by codes.

        Args:
            codes: List of classification codes

        Returns:
            List of PatentClassification objects
        """
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="code",
                        match=MatchAny(any=codes)
                    )
                ]
            ),
            limit=len(codes)
        )

        classifications = []
        for record in results[0]:  # results is a tuple (records, next_page_offset)
            classifications.append(self._payload_to_classification(record.payload))

        return classifications

    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dictionary with collection statistics
        """
        collection_info = self.client.get_collection(self.collection_name)
        return {
            "name": collection_info.config.params,
            "vectors_count": collection_info.vectors_count,
            "points_count": collection_info.points_count,
            "status": collection_info.status
        }

    def count_by_type(self) -> Dict[str, int]:
        """
        Count classifications by type.

        Returns:
            Dictionary with counts for each classification type
        """
        counts = {}
        for class_type in ["IPC", "CPC", "FI"]:
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="classification_type",
                            match=MatchValue(value=class_type)
                        )
                    ]
                )
            )
            counts[class_type] = result.count

        return counts
