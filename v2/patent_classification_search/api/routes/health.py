"""Health check and system status routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from loguru import logger

from ...core.vector_store import VectorStore
from ..schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

# Global vector store instance
vector_store: Optional[VectorStore] = None


def setup_health_dependencies(vec_store: VectorStore):
    """Setup dependencies for health routes."""
    global vector_store
    vector_store = vec_store


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns the status of the API service and Qdrant connection.
    """
    try:
        # Check Qdrant connection and get collection info
        collection_info = vector_store.get_collection_info()
        counts = vector_store.count_by_type()

        return HealthResponse(
            status="healthy",
            qdrant_status="connected",
            collection_info={
                **collection_info,
                "counts_by_type": counts
            }
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


@router.get("/stats")
async def get_statistics():
    """
    Get detailed statistics about the classification database.

    Returns:
        Statistics including counts by classification type and total records
    """
    try:
        counts = vector_store.count_by_type()
        info = vector_store.get_collection_info()

        return {
            "total_classifications": info.get("points_count", 0),
            "classifications_by_type": counts,
            "collection_name": info.get("name", "unknown"),
            "status": info.get("status", "unknown")
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
