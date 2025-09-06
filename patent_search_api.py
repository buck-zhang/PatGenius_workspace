#!/usr/bin/env python3
"""
PatGenius FastAPI - Japanese Patent Search API
OpenSearchを使った高速特許検索API
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import requests
import json
from datetime import datetime
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション初期化
app = FastAPI(
    title="PatGenius Search API",
    description="30,002件の日本特許データを対象とした高速検索API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenSearch設定
OPENSEARCH_URL = "http://localhost:9200"
INDEX_NAME = "patents"

class SearchRequest(BaseModel):
    """検索リクエストモデル"""
    query: str = Field(..., description="検索クエリ", example="画像形成装置")
    field: Optional[str] = Field(None, description="検索対象フィールド", example="invention_title")
    size: int = Field(10, description="取得件数", ge=1, le=100)
    from_: int = Field(0, description="開始位置", alias="from", ge=0)
    sort_field: Optional[str] = Field(None, description="ソートフィールド")
    sort_order: str = Field("desc", description="ソート順", pattern="^(asc|desc)$")

class PatentDocument(BaseModel):
    """特許文書モデル"""
    document_id: Optional[str] = None
    invention_title: Optional[str] = None
    applicant_name: Optional[str] = None
    inventor_names: Optional[str] = None
    technical_field: Optional[str] = None
    background_art: Optional[str] = None
    tech_problem: Optional[str] = None
    tech_solution: Optional[str] = None
    advantageous_effects: Optional[str] = None
    description: Optional[str] = None
    claims: Optional[str] = None
    abstract: Optional[str] = None
    classification_ipc: Optional[List[str]] = None
    classification_national: Optional[List[str]] = None
    f_terms: Optional[List[str]] = None
    date: Optional[str] = None
    application_date: Optional[str] = None

class SearchResponse(BaseModel):
    """検索レスポンスモデル"""
    total: int = Field(..., description="総件数")
    hits: List[PatentDocument] = Field(..., description="検索結果")
    took: int = Field(..., description="検索時間(ms)")
    query_info: Dict[str, Any] = Field(..., description="クエリ情報")

class OpenSearchClient:
    """OpenSearchクライアント"""
    
    def __init__(self, url: str = OPENSEARCH_URL, index: str = INDEX_NAME):
        self.url = url
        self.index = index
        self.session = requests.Session()
    
    def search(self, query_body: Dict[str, Any]) -> Dict[str, Any]:
        """OpenSearch検索実行"""
        try:
            response = self.session.post(
                f"{self.url}/{self.index}/_search",
                json=query_body,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenSearch search error: {e}")
            raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
    
    def get_index_stats(self) -> Dict[str, Any]:
        """インデックス統計取得"""
        try:
            response = self.session.get(f"{self.url}/{self.index}/_stats")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenSearch stats error: {e}")
            raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

# OpenSearchクライアント初期化
client = OpenSearchClient()

@app.get("/", tags=["Health"])
async def root():
    """API根エンドポイント"""
    return {
        "message": "PatGenius Search API",
        "version": "1.0.0",
        "description": "日本特許データ検索API",
        "endpoints": {
            "search": "/search",
            "advanced_search": "/search/advanced",
            "document": "/document/{document_id}",
            "stats": "/stats",
            "fields": "/fields"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """ヘルスチェック"""
    try:
        response = requests.get(f"{OPENSEARCH_URL}/_cluster/health", timeout=5)
        opensearch_status = response.json().get("status", "unknown")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "opensearch_status": opensearch_status,
            "index": INDEX_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/stats", tags=["Statistics"])
async def get_stats():
    """インデックス統計情報"""
    try:
        stats = client.get_index_stats()
        count_response = requests.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_count")
        count_data = count_response.json()
        
        return {
            "total_documents": count_data.get("count", 0),
            "index_size": stats["indices"][INDEX_NAME]["total"]["store"]["size_in_bytes"],
            "index_name": INDEX_NAME,
            "shards": stats["indices"][INDEX_NAME]["total"]["shard_stats"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

@app.get("/fields", tags=["Metadata"])
async def get_searchable_fields():
    """検索可能フィールド一覧"""
    return {
        "searchable_fields": {
            "invention_title": "発明名称",
            "applicant_name": "出願人名", 
            "inventor_names": "発明者名",
            "technical_field": "技術分野",
            "background_art": "背景技術", 
            "tech_problem": "解決課題",
            "tech_solution": "解決手段",
            "advantageous_effects": "発明の効果",
            "description": "詳細説明",
            "claims": "請求項",
            "abstract": "要約",
            "classification_ipc": "IPC分類",
            "classification_national": "国内分類",
            "f_terms": "Fターム",
            "document_id": "文献番号"
        },
        "examples": {
            "invention_title": "画像形成装置",
            "applicant_name": "京セラミタ株式会社",
            "technical_field": "電子写真",
            "classification_ipc": "G03G 15/08"
        }
    }

@app.get("/search", response_model=SearchResponse, tags=["Search"])
async def simple_search(
    q: str = Query(..., description="検索クエリ", example="画像形成装置"),
    field: Optional[str] = Query(None, description="検索フィールド", example="invention_title"),
    size: int = Query(10, description="取得件数", ge=1, le=100),
    from_: int = Query(0, description="開始位置", alias="from", ge=0)
):
    """シンプル検索"""
    
    # クエリ構築
    if field:
        query_body = {
            "query": {
                "match": {
                    field: q
                }
            },
            "size": size,
            "from": from_,
            "sort": [{"_score": {"order": "desc"}}]
        }
    else:
        # 全フィールド検索
        query_body = {
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "invention_title^3",
                        "technical_field^2", 
                        "abstract^2",
                        "claims",
                        "description",
                        "applicant_name",
                        "background_art",
                        "tech_problem",
                        "tech_solution",
                        "advantageous_effects"
                    ]
                }
            },
            "size": size,
            "from": from_,
            "sort": [{"_score": {"order": "desc"}}]
        }
    
    # 検索実行
    start_time = datetime.now()
    result = client.search(query_body)
    end_time = datetime.now()
    
    # レスポンス構築
    hits = []
    for hit in result["hits"]["hits"]:
        source = hit["_source"]
        patent = PatentDocument(**source)
        hits.append(patent)
    
    return SearchResponse(
        total=result["hits"]["total"]["value"],
        hits=hits,
        took=result["took"],
        query_info={
            "query": q,
            "field": field,
            "size": size,
            "from": from_,
            "execution_time_ms": int((end_time - start_time).total_seconds() * 1000)
        }
    )

@app.post("/search/advanced", response_model=SearchResponse, tags=["Search"])
async def advanced_search(request: SearchRequest):
    """高度検索"""
    
    # 複合クエリ構築
    if request.field:
        query_body = {
            "query": {
                "match": {
                    request.field: request.query
                }
            }
        }
    else:
        query_body = {
            "query": {
                "multi_match": {
                    "query": request.query,
                    "fields": [
                        "invention_title^3",
                        "technical_field^2",
                        "abstract^2",
                        "claims",
                        "description"
                    ]
                }
            }
        }
    
    query_body["size"] = request.size
    query_body["from"] = request.from_
    
    # ソート設定
    if request.sort_field:
        query_body["sort"] = [{request.sort_field: {"order": request.sort_order}}]
    else:
        query_body["sort"] = [{"_score": {"order": "desc"}}]
    
    # ハイライト設定
    query_body["highlight"] = {
        "fields": {
            "invention_title": {},
            "abstract": {},
            "technical_field": {}
        }
    }
    
    # 検索実行
    start_time = datetime.now()
    result = client.search(query_body)
    end_time = datetime.now()
    
    # レスポンス構築
    hits = []
    for hit in result["hits"]["hits"]:
        source = hit["_source"]
        patent = PatentDocument(**source)
        hits.append(patent)
    
    return SearchResponse(
        total=result["hits"]["total"]["value"],
        hits=hits,
        took=result["took"],
        query_info={
            "query": request.query,
            "field": request.field,
            "size": request.size,
            "from": request.from_,
            "sort_field": request.sort_field,
            "sort_order": request.sort_order,
            "execution_time_ms": int((end_time - start_time).total_seconds() * 1000)
        }
    )

@app.get("/document/{document_id}", response_model=PatentDocument, tags=["Document"])
async def get_document(document_id: str):
    """特許文書詳細取得"""
    try:
        response = requests.get(f"{OPENSEARCH_URL}/{INDEX_NAME}/_doc/{document_id}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        
        response.raise_for_status()
        data = response.json()
        
        return PatentDocument(**data["_source"])
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")

@app.get("/search/suggest", tags=["Search"])
async def search_suggestions(
    q: str = Query(..., description="検索クエリ", example="画像"),
    field: str = Query("invention_title", description="サジェストフィールド")
):
    """検索サジェスト"""
    
    query_body = {
        "suggest": {
            "text": q,
            "simple_phrase": {
                "phrase": {
                    "field": field,
                    "size": 5,
                    "gram_size": 2,
                    "direct_generator": [{
                        "field": field,
                        "suggest_mode": "always"
                    }]
                }
            }
        }
    }
    
    try:
        result = client.search(query_body)
        suggestions = []
        
        if "suggest" in result:
            for suggestion in result["suggest"]["simple_phrase"][0]["options"]:
                suggestions.append({
                    "text": suggestion["text"],
                    "score": suggestion["score"]
                })
        
        return {
            "query": q,
            "suggestions": suggestions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)