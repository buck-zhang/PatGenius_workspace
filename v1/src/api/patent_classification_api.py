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


class CPCToFIRequest(BaseModel):
    """CPC to FI conversion request model"""
    cpc_codes: List[str] = Field(..., description="CPC codes to convert to FI", min_items=1)
    top_k: int = Field(10, ge=1, le=100, description="Number of FI codes to return per CPC")


class CPCToFIResponse(BaseModel):
    """CPC to FI conversion response model"""
    fi_codes: List[str] = Field(description="List of FI codes corresponding to the input CPCs")
    total: int = Field(description="Total number of FI codes found")
    took_ms: float = Field(description="Time taken in milliseconds")


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

    def convert_cpc_to_fi(self, cpc_codes: List[str], top_k: int = 10) -> Dict[str, Any]:
        """
        Convert CPC codes to FI codes

        CPC and FI use different formatting:
        - CPC: "H10D30/00" (no spaces)
        - FI: "H10D  30/01" (2 spaces after section)

        This method normalizes CPC codes to FI format and searches by prefix.

        Args:
            cpc_codes: List of CPC codes to convert
            top_k: Maximum number of FI codes to return

        Returns:
            Dictionary with fi_codes list and metadata
        """
        import time
        import re
        start_time = time.time()

        fi_codes_set = set()

        try:
            # For each CPC code, search FI index with normalized format
            for cpc_code in cpc_codes:
                # Normalize CPC to FI format
                # CPC: "H10D30/00" → FI prefix: "H10D  30"
                # Extract section (e.g., "H10D") and class (e.g., "30")
                match = re.match(r'^([A-Z]\d{2}[A-Z])(\d+)', cpc_code)
                if not match:
                    continue

                section = match.group(1)  # e.g., "H10D"
                class_num = match.group(2)  # e.g., "30"

                # FI format: section + 2 spaces + class (padded to 2 chars)
                fi_prefix = f"{section}  {class_num.rjust(2)}"

                # Search FI index with prefix match on code field
                response = self.client.search(
                    index="patent_classification_fi",
                    body={
                        "query": {
                            "prefix": {
                                "code": fi_prefix
                            }
                        },
                        "size": top_k,
                        "_source": ["code"]
                    }
                )

                # Collect FI codes from results
                for hit in response['hits']['hits']:
                    fi_code = hit['_source'].get('code')
                    if fi_code:
                        fi_codes_set.add(fi_code)

                        # Stop if we've collected enough
                        if len(fi_codes_set) >= top_k:
                            break

                if len(fi_codes_set) >= top_k:
                    break

            fi_codes_list = list(fi_codes_set)[:top_k]
            took_ms = (time.time() - start_time) * 1000

            return {
                "fi_codes": fi_codes_list,
                "total": len(fi_codes_list),
                "took_ms": took_ms
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"CPC to FI conversion error: {str(e)}")

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


@app.post("/convert/cpc_to_fi", response_model=CPCToFIResponse)
async def convert_cpc_to_fi(request: CPCToFIRequest):
    """
    Convert CPC codes to FI codes

    Searches the FI index for classifications that have concordance (related mappings)
    with the given CPC codes.

    Args:
        request: CPCToFIRequest containing list of CPC codes and top_k parameter

    Returns:
        CPCToFIResponse containing the list of FI codes found
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    result = searcher.convert_cpc_to_fi(request.cpc_codes, request.top_k)

    return CPCToFIResponse(**result)


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
