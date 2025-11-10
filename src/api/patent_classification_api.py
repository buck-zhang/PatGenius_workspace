"""
Patent Classification Search API with RAG
Provides REST API for searching IPC, CPC, and FI classifications
"""

import os
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
import torch
from PIL import Image
import io


# Models and Enums
class ClassificationType(str, Enum):
    """Classification type enum"""
    IPC = "ipc"
    CPC = "cpc"
    FI = "fi"
    ALL = "all"


class SearchCondition(str, Enum):
    """Search condition type"""
    AND = "and"
    OR = "or"


class SearchRequest(BaseModel):
    """Search request model"""
    keywords: Optional[List[str]] = Field(None, description="Keywords to search")
    text: Optional[str] = Field(None, description="Text for semantic search")
    ipc_codes: Optional[List[str]] = Field(None, description="IPC codes to filter")
    cpc_codes: Optional[List[str]] = Field(None, description="CPC codes to filter")
    fi_codes: Optional[List[str]] = Field(None, description="FI codes to filter")
    classification_types: List[ClassificationType] = Field(
        [ClassificationType.ALL],
        description="Classification types to search"
    )
    condition: SearchCondition = Field(
        SearchCondition.OR,
        description="AND or OR condition for keywords"
    )
    top_k: int = Field(20, ge=1, le=100, description="Number of results to return")
    use_semantic_search: bool = Field(True, description="Use RAG semantic search")


class ClassificationResult(BaseModel):
    """Classification search result"""
    code: str
    classification_type: str
    title_ja: Optional[str] = None
    title_en: Optional[str] = None
    subsection_title_ja: Optional[str] = None
    subsection_title_en: Optional[str] = None
    concordance: Optional[str] = None
    ipc_part: Optional[str] = None
    theme: Optional[str] = None
    num_families: Optional[int] = None
    num_documents: Optional[int] = None
    level: Optional[int] = None
    is_head: bool = False
    score: float


class SearchResponse(BaseModel):
    """Search response model"""
    results: List[ClassificationResult]
    total: int
    took_ms: float


# API Application
app = FastAPI(
    title="Patent Classification Search API",
    description="RAG-enabled search API for IPC, CPC, and FI patent classifications",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PatentClassificationSearcher:
    """Patent classification searcher with RAG"""

    def __init__(self,
                 opensearch_host: str = "localhost",
                 opensearch_port: int = 9200,
                 embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"):
        """Initialize searcher"""
        self.client = OpenSearch(
            hosts=[{'host': opensearch_host, 'port': opensearch_port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )

        print(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        print("Model loaded successfully")

    def get_index_names(self, classification_types: List[ClassificationType]) -> List[str]:
        """Get index names based on classification types"""
        if ClassificationType.ALL in classification_types:
            return ["patent_classification_ipc", "patent_classification_cpc", "patent_classification_fi"]

        index_names = []
        for ct in classification_types:
            if ct != ClassificationType.ALL:
                index_names.append(f"patent_classification_{ct.value}")

        return index_names

    def build_keyword_query(self, request: SearchRequest) -> Dict[str, Any]:
        """Build keyword-based query"""
        must_clauses = []
        should_clauses = []

        # Keyword search
        if request.keywords:
            for keyword in request.keywords:
                keyword_query = {
                    "multi_match": {
                        "query": keyword,
                        "fields": ["title_ja^2", "title_en^2", "subsection_title_ja", "subsection_title_en", "theme"],
                        "type": "best_fields",
                        "operator": "or"
                    }
                }

                if request.condition == SearchCondition.AND:
                    must_clauses.append(keyword_query)
                else:
                    should_clauses.append(keyword_query)

        # Code filters
        if request.ipc_codes:
            for code in request.ipc_codes:
                filter_clause = {
                    "bool": {
                        "should": [
                            {"term": {"code": code}},
                            {"prefix": {"code": code}}
                        ]
                    }
                }
                if request.condition == SearchCondition.AND:
                    must_clauses.append(filter_clause)
                else:
                    should_clauses.append(filter_clause)

        if request.cpc_codes:
            for code in request.cpc_codes:
                filter_clause = {
                    "bool": {
                        "should": [
                            {"term": {"code": code}},
                            {"prefix": {"code": code}}
                        ]
                    }
                }
                if request.condition == SearchCondition.AND:
                    must_clauses.append(filter_clause)
                else:
                    should_clauses.append(filter_clause)

        if request.fi_codes:
            for code in request.fi_codes:
                filter_clause = {
                    "bool": {
                        "should": [
                            {"term": {"code": code}},
                            {"prefix": {"code": code}}
                        ]
                    }
                }
                if request.condition == SearchCondition.AND:
                    must_clauses.append(filter_clause)
                else:
                    should_clauses.append(filter_clause)

        # Build final query
        if request.condition == SearchCondition.AND:
            query = {
                "bool": {
                    "must": must_clauses
                }
            }
        else:
            query = {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            }

        return query

    def build_semantic_query(self, request: SearchRequest) -> Dict[str, Any]:
        """Build semantic search query using RAG embeddings"""
        if not request.text:
            return self.build_keyword_query(request)

        # Generate embedding for query text
        query_embedding = self.model.encode(request.text, convert_to_numpy=True)

        # KNN query for semantic search
        knn_query = {
            "knn": {
                "embedding": {
                    "vector": query_embedding.tolist(),
                    "k": request.top_k
                }
            }
        }

        # Combine with keyword filters if provided
        filter_clauses = []

        if request.ipc_codes:
            filter_clauses.append({
                "terms": {"code": request.ipc_codes}
            })

        if request.cpc_codes:
            filter_clauses.append({
                "terms": {"code": request.cpc_codes}
            })

        if request.fi_codes:
            filter_clauses.append({
                "terms": {"code": request.fi_codes}
            })

        if filter_clauses:
            return {
                "bool": {
                    "must": [knn_query],
                    "filter": filter_clauses if request.condition == SearchCondition.AND else [],
                    "should": filter_clauses if request.condition == SearchCondition.OR else []
                }
            }

        return knn_query

    def search(self, request: SearchRequest) -> SearchResponse:
        """Execute search"""
        import time
        start_time = time.time()

        # Get index names
        index_names = self.get_index_names(request.classification_types)

        # Build query
        if request.use_semantic_search and request.text:
            query = self.build_semantic_query(request)
        else:
            query = self.build_keyword_query(request)

        # Execute search
        try:
            response = self.client.search(
                index=",".join(index_names),
                body={
                    "query": query,
                    "size": request.top_k,
                    "_source": {
                        "excludes": ["embedding"]
                    }
                }
            )

            # Parse results
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                result = ClassificationResult(
                    code=source.get('code', ''),
                    classification_type=source.get('classification_type', ''),
                    title_ja=source.get('title_ja'),
                    title_en=source.get('title_en'),
                    subsection_title_ja=source.get('subsection_title_ja'),
                    subsection_title_en=source.get('subsection_title_en'),
                    concordance=source.get('concordance'),
                    ipc_part=source.get('ipc_part'),
                    theme=source.get('theme'),
                    num_families=source.get('num_families'),
                    num_documents=source.get('num_documents'),
                    level=source.get('level'),
                    is_head=source.get('is_head', False),
                    score=hit['_score']
                )
                results.append(result)

            took_ms = (time.time() - start_time) * 1000

            return SearchResponse(
                results=results,
                total=response['hits']['total']['value'],
                took_ms=took_ms
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

    def get_by_code(self, code: str, classification_type: ClassificationType) -> Optional[ClassificationResult]:
        """Get classification by exact code"""
        index_name = f"patent_classification_{classification_type.value}"

        try:
            response = self.client.search(
                index=index_name,
                body={
                    "query": {
                        "term": {"code": code}
                    },
                    "size": 1,
                    "_source": {
                        "excludes": ["embedding"]
                    }
                }
            )

            if response['hits']['total']['value'] > 0:
                source = response['hits']['hits'][0]['_source']
                return ClassificationResult(
                    code=source.get('code', ''),
                    classification_type=source.get('classification_type', ''),
                    title_ja=source.get('title_ja'),
                    title_en=source.get('title_en'),
                    subsection_title_ja=source.get('subsection_title_ja'),
                    subsection_title_en=source.get('subsection_title_en'),
                    concordance=source.get('concordance'),
                    ipc_part=source.get('ipc_part'),
                    theme=source.get('theme'),
                    num_families=source.get('num_families'),
                    num_documents=source.get('num_documents'),
                    level=source.get('level'),
                    is_head=source.get('is_head', False),
                    score=response['hits']['hits'][0]['_score']
                )

            return None

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


# Initialize searcher
searcher = None


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global searcher

    opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
    opensearch_port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    embedding_model = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")

    searcher = PatentClassificationSearcher(
        opensearch_host=opensearch_host,
        opensearch_port=opensearch_port,
        embedding_model=embedding_model
    )


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Patent Classification Search API",
        "version": "1.0.0",
        "endpoints": {
            "/search": "POST - Advanced search with keywords, text, and codes",
            "/search/keyword": "GET - Simple keyword search",
            "/search/text": "GET - Semantic text search (RAG)",
            "/search/code/{classification_type}/{code}": "GET - Get classification by code",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    try:
        if searcher:
            searcher.client.cluster.health()
            return {"status": "healthy", "opensearch": "connected"}
        return {"status": "initializing"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Advanced search endpoint supporting:
    - Keywords with AND/OR conditions
    - Semantic text search using RAG
    - IPC/CPC/FI code filters
    - Multiple classification types
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return searcher.search(request)


@app.get("/search/keyword", response_model=SearchResponse)
async def search_keyword(
    q: str = Query(..., description="Keyword to search"),
    classification_type: ClassificationType = Query(ClassificationType.ALL, description="Classification type"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Simple keyword search"""
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    request = SearchRequest(
        keywords=[q],
        classification_types=[classification_type],
        top_k=top_k,
        use_semantic_search=False
    )

    return searcher.search(request)


@app.get("/search/text", response_model=SearchResponse)
async def search_text(
    q: str = Query(..., description="Text for semantic search"),
    classification_type: ClassificationType = Query(ClassificationType.ALL, description="Classification type"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Semantic text search using RAG"""
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    request = SearchRequest(
        text=q,
        classification_types=[classification_type],
        top_k=top_k,
        use_semantic_search=True
    )

    return searcher.search(request)


@app.get("/search/code/{classification_type}/{code}", response_model=ClassificationResult)
async def search_by_code(
    classification_type: ClassificationType,
    code: str
):
    """Get classification by exact code"""
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if classification_type == ClassificationType.ALL:
        raise HTTPException(status_code=400, detail="Please specify a specific classification type")

    result = searcher.get_by_code(code, classification_type)

    if not result:
        raise HTTPException(status_code=404, detail=f"Classification code {code} not found")

    return result


@app.post("/search/image", response_model=SearchResponse)
async def search_image(
    file: UploadFile = File(...),
    classification_type: ClassificationType = Query(ClassificationType.ALL, description="Classification type"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """
    Image-based search (placeholder for future CLIP integration)
    Currently returns error - requires CLIP model implementation
    """
    raise HTTPException(
        status_code=501,
        detail="Image search not yet implemented. Requires CLIP model integration."
    )


if __name__ == "__main__":
    uvicorn.run(
        "patent_classification_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
