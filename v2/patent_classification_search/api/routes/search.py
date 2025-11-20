"""Search routes for patent classification API."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from loguru import logger
import numpy as np
from PIL import Image
import io

from ...core.config import settings
from ...core.embeddings import EmbeddingManager
from ...core.vector_store import VectorStore
from ...models.patent_class import SearchResult
from ..schemas import (
    TextSearchRequest,
    CodeSearchRequest,
    BooleanSearchRequest,
    SearchResponse
)

router = APIRouter(prefix="/search", tags=["search"])

# Initialize global instances (will be set up in main.py)
embedding_manager: Optional[EmbeddingManager] = None
vector_store: Optional[VectorStore] = None


def setup_search_dependencies(emb_manager: EmbeddingManager, vec_store: VectorStore):
    """Setup dependencies for search routes."""
    global embedding_manager, vector_store
    embedding_manager = emb_manager
    vector_store = vec_store


@router.post("/text", response_model=SearchResponse)
async def search_by_text(request: TextSearchRequest):
    """
    Search patent classifications by text query.

    This endpoint uses semantic search to find relevant patent classifications
    based on the text query.
    """
    try:
        logger.info(f"Text search: '{request.query}' (type: {request.classification_type})")

        # Generate embedding for query
        query_embedding = embedding_manager.text_embedder.embed_single(request.query)

        # Search in vector store
        results = vector_store.search(
            query_vector=query_embedding,
            limit=request.limit,
            classification_type=request.classification_type,
            min_score=request.min_score
        )

        return SearchResponse(
            results=results,
            total=len(results),
            query_info={
                "query": request.query,
                "classification_type": request.classification_type,
                "limit": request.limit,
                "min_score": request.min_score
            }
        )

    except Exception as e:
        logger.error(f"Error in text search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code", response_model=SearchResponse)
async def search_by_code(request: CodeSearchRequest):
    """
    Search patent classifications by exact code match.

    This endpoint retrieves specific classifications by their codes.
    """
    try:
        logger.info(f"Code search: {request.codes}")

        # Search by codes
        classifications = vector_store.search_by_codes(request.codes)

        # Convert to SearchResult format (with score 1.0 for exact matches)
        results = [
            SearchResult(classification=c, similarity_score=1.0)
            for c in classifications
        ]

        return SearchResponse(
            results=results,
            total=len(results),
            query_info={
                "codes": request.codes,
                "found": len(results)
            }
        )

    except Exception as e:
        logger.error(f"Error in code search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boolean", response_model=SearchResponse)
async def search_with_boolean_operators(request: BooleanSearchRequest):
    """
    Search with Boolean operators (OR/AND).

    - OR: Returns results matching ANY of the queries (union)
    - AND: Returns results matching ALL of the queries (intersection)
    """
    try:
        logger.info(f"Boolean search ({request.operator}): {request.queries}")

        all_results = []

        # For each query, perform search
        for query in request.queries:
            query_embedding = embedding_manager.text_embedder.embed_single(query)
            results = vector_store.search(
                query_vector=query_embedding,
                limit=request.limit * 2,  # Get more results for better merging
                classification_type=request.classification_type,
                min_score=request.min_score
            )
            all_results.append(results)

        # Merge results based on operator
        if request.operator == "OR":
            # Union: combine all results and remove duplicates
            merged_results = _merge_or_results(all_results, request.limit)
        else:  # AND
            # Intersection: only include results present in all queries
            merged_results = _merge_and_results(all_results, request.limit)

        return SearchResponse(
            results=merged_results,
            total=len(merged_results),
            query_info={
                "queries": request.queries,
                "operator": request.operator,
                "classification_type": request.classification_type,
                "limit": request.limit
            }
        )

    except Exception as e:
        logger.error(f"Error in boolean search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(..., description="Image file to search"),
    classification_type: Optional[str] = Form(None),
    limit: int = Form(20, ge=1, le=100),
    min_score: float = Form(0.0, ge=0.0, le=1.0)
):
    """
    Search patent classifications using an image.

    This endpoint uses CLIP to encode images and search for relevant
    patent classifications in the same embedding space.
    """
    try:
        logger.info(f"Image search (type: {classification_type})")

        # Read and process image
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Generate embedding using CLIP
        image_embedding = embedding_manager.image_embedder.embed_single_image(pil_image)

        # Search in vector store
        # Note: This assumes we have a separate collection for image embeddings
        # For now, we'll use text embeddings but in production you'd want separate collections
        results = vector_store.search(
            query_vector=image_embedding,
            limit=limit,
            classification_type=classification_type,
            min_score=min_score
        )

        return SearchResponse(
            results=results,
            total=len(results),
            query_info={
                "image_filename": image.filename,
                "classification_type": classification_type,
                "limit": limit,
                "min_score": min_score
            }
        )

    except Exception as e:
        logger.error(f"Error in image search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _merge_or_results(all_results: List[List[SearchResult]], limit: int) -> List[SearchResult]:
    """
    Merge results using OR operator (union).

    Combines all results, removes duplicates, and sorts by best score.
    """
    # Use dictionary to track best score for each code
    code_to_result = {}

    for results in all_results:
        for result in results:
            code = result.classification.code
            if code not in code_to_result or result.similarity_score > code_to_result[code].similarity_score:
                code_to_result[code] = result

    # Sort by score and limit
    merged = sorted(code_to_result.values(), key=lambda x: x.similarity_score, reverse=True)
    return merged[:limit]


def _merge_and_results(all_results: List[List[SearchResult]], limit: int) -> List[SearchResult]:
    """
    Merge results using AND operator (intersection).

    Only includes results that appear in ALL queries.
    """
    if not all_results:
        return []

    # Count occurrences of each code
    code_counts = {}
    code_to_scores = {}

    for results in all_results:
        for result in results:
            code = result.classification.code
            code_counts[code] = code_counts.get(code, 0) + 1

            if code not in code_to_scores:
                code_to_scores[code] = []
            code_to_scores[code].append(result.similarity_score)

    # Only keep codes that appear in all queries
    num_queries = len(all_results)
    intersection_codes = [code for code, count in code_counts.items() if count == num_queries]

    # Create results with average score
    intersection_results = []
    for code in intersection_codes:
        # Find the result object (from first occurrence)
        for results in all_results:
            for result in results:
                if result.classification.code == code:
                    # Calculate average score
                    avg_score = np.mean(code_to_scores[code])
                    intersection_results.append(
                        SearchResult(
                            classification=result.classification,
                            similarity_score=float(avg_score)
                        )
                    )
                    break
            else:
                continue
            break

    # Sort by average score and limit
    intersection_results.sort(key=lambda x: x.similarity_score, reverse=True)
    return intersection_results[:limit]
