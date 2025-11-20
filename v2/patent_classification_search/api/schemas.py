"""Pydantic schemas for API requests and responses."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

from ..models.patent_class import SearchResult, ClassificationType


class TextSearchRequest(BaseModel):
    """Request schema for text-based search."""

    query: str = Field(..., description="Search query text", min_length=1)
    classification_type: Optional[ClassificationType] = Field(
        None,
        description="Filter by classification type (IPC, CPC, or FI)"
    )
    limit: int = Field(20, description="Maximum number of results", ge=1, le=100)
    min_score: float = Field(0.0, description="Minimum similarity score", ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "agricultural hand tools",
                "classification_type": "IPC",
                "limit": 10,
                "min_score": 0.5
            }
        }


class CodeSearchRequest(BaseModel):
    """Request schema for direct code search."""

    codes: List[str] = Field(..., description="List of classification codes to search")

    class Config:
        json_schema_extra = {
            "example": {
                "codes": ["A01B1/00", "H04L29/06"]
            }
        }


class BooleanSearchRequest(BaseModel):
    """Request schema for boolean search with OR/AND operators."""

    queries: List[str] = Field(..., description="List of query terms", min_length=1)
    operator: Literal["OR", "AND"] = Field("OR", description="Boolean operator (OR or AND)")
    classification_type: Optional[ClassificationType] = Field(
        None,
        description="Filter by classification type"
    )
    limit: int = Field(20, description="Maximum number of results", ge=1, le=100)
    min_score: float = Field(0.0, description="Minimum similarity score", ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {
                "queries": ["hand tools", "agricultural equipment"],
                "operator": "OR",
                "classification_type": "IPC",
                "limit": 10,
                "min_score": 0.5
            }
        }


class SearchResponse(BaseModel):
    """Response schema for search results."""

    results: List[SearchResult] = Field(..., description="List of search results")
    total: int = Field(..., description="Total number of results returned")
    query_info: dict = Field(..., description="Information about the query")

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "classification": {
                            "code": "A01B1/00",
                            "classification_type": "IPC",
                            "dot_number": 7,
                            "title_en": "Hand tools",
                            "title_ja": "手工具",
                            "document_count": 1737
                        },
                        "similarity_score": 0.92
                    }
                ],
                "total": 1,
                "query_info": {
                    "query": "agricultural hand tools",
                    "classification_type": "IPC",
                    "limit": 10
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    qdrant_status: str = Field(..., description="Qdrant connection status")
    collection_info: dict = Field(..., description="Collection information")
