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

class AdvancedSearchRequest(BaseModel):
    """高度な検索リクエストモデル"""
    query_type: str = Field("simple", description="検索タイプ: simple, proximity, boolean, query_string")
    query: str = Field(..., description="検索クエリ")
    field: Optional[str] = Field(None, description="検索対象フィールド")
    proximity_distance: Optional[int] = Field(3, description="近傍検索の距離", ge=1, le=100)
    boolean_operator: Optional[str] = Field("AND", description="ブール演算子: AND, OR")
    must_terms: Optional[List[str]] = Field(None, description="必須キーワードリスト")
    should_terms: Optional[List[str]] = Field(None, description="オプションキーワードリスト") 
    must_not_terms: Optional[List[str]] = Field(None, description="除外キーワードリスト")
    field_queries: Optional[Dict[str, str]] = Field(None, description="フィールド別クエリ")
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
    
    def build_advanced_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """高度な検索クエリ構築"""
        query_body = {
            "size": request.size,
            "from": request.from_,
            "_source": True
        }
        
        # ソート設定
        if request.sort_field:
            query_body["sort"] = [{request.sort_field: {"order": request.sort_order}}]
        
        # クエリタイプ別の処理
        if request.query_type == "proximity":
            # 近傍検索: "車 near3 両" -> "車"と"両"が3語以内の距離
            query_body["query"] = self._build_proximity_query(request)
        elif request.query_type == "boolean":
            # ブール検索: AND/OR/NOT組み合わせ
            query_body["query"] = self._build_boolean_query(request)
        elif request.query_type == "query_string":
            # クエリ文字列検索: フィールド指定可能
            query_body["query"] = self._build_query_string_query(request)
        elif request.query_type == "multi_field":
            # マルチフィールド検索
            query_body["query"] = self._build_multi_field_query(request)
        else:
            # シンプル検索（デフォルト）
            query_body["query"] = self._build_simple_query(request)
        
        return query_body
    
    def _build_proximity_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """近傍検索クエリ構築"""
        # "車 near3 両" の形式をパース
        if " near" in request.query:
            parts = request.query.split(" near")
            if len(parts) == 2:
                terms = parts[0].strip()
                distance_part = parts[1].strip()
                try:
                    distance = int(distance_part.split()[0])
                    field = request.field or "_all"
                    return {
                        "span_near": {
                            "clauses": [
                                {"span_term": {field: term.strip()}} 
                                for term in terms.split()
                            ],
                            "slop": distance,
                            "in_order": False
                        }
                    }
                except (ValueError, IndexError):
                    pass
        
        # 近傍検索パースに失敗した場合は通常のフレーズ検索
        field = request.field or "_all"
        return {
            "match_phrase": {
                field: {
                    "query": request.query,
                    "slop": request.proximity_distance or 3
                }
            }
        }
    
    def _build_boolean_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """ブール検索クエリ構築"""
        bool_query = {"bool": {}}
        
        # 必須条件 (must)
        if request.must_terms:
            bool_query["bool"]["must"] = [
                {"match": {request.field or "_all": term}} 
                for term in request.must_terms
            ]
        elif request.query:
            bool_query["bool"]["must"] = [
                {"match": {request.field or "_all": request.query}}
            ]
        
        # オプション条件 (should)
        if request.should_terms:
            bool_query["bool"]["should"] = [
                {"match": {request.field or "_all": term}} 
                for term in request.should_terms
            ]
        
        # 除外条件 (must_not)
        if request.must_not_terms:
            bool_query["bool"]["must_not"] = [
                {"match": {request.field or "_all": term}} 
                for term in request.must_not_terms
            ]
        
        return bool_query
    
    def _build_query_string_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """クエリ文字列検索構築"""
        return {
            "query_string": {
                "query": request.query,
                "fields": [request.field] if request.field else ["*"],
                "default_operator": request.boolean_operator.upper() if request.boolean_operator else "AND"
            }
        }
    
    def _build_multi_field_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """マルチフィールド検索構築"""
        if not request.field_queries:
            return self._build_simple_query(request)
        
        bool_query = {"bool": {"must": []}}
        for field, query in request.field_queries.items():
            bool_query["bool"]["must"].append({
                "match": {field: query}
            })
        
        return bool_query
    
    def _build_simple_query(self, request: AdvancedSearchRequest) -> Dict[str, Any]:
        """シンプル検索クエリ構築"""
        if request.field:
            return {"match": {request.field: request.query}}
        else:
            return {"multi_match": {
                "query": request.query,
                "fields": ["*"]
            }}

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
async def advanced_search(request: AdvancedSearchRequest):
    """
    高度検索API
    
    検索タイプ:
    - proximity: 近傍検索 ("車 near3 両" - 車と両が3語以内の距離)
    - boolean: ブール検索 (must/should/must_not条件組み合わせ)
    - query_string: クエリ文字列検索 (フィールド指定とAND/OR演算)
    - multi_field: マルチフィールド検索 (複数フィールドに異なるクエリ)
    - simple: シンプル検索（デフォルト）
    """
    
    # 高度検索クエリ構築
    start_time = datetime.now()
    query_body = client.build_advanced_query(request)
    
    # ハイライト設定を追加
    query_body["highlight"] = {
        "fields": {
            "invention_title": {"fragment_size": 100},
            "abstract": {"fragment_size": 150}, 
            "technical_field": {"fragment_size": 100},
            "claims": {"fragment_size": 150}
        },
        "pre_tags": ["<mark>"], 
        "post_tags": ["</mark>"]
    }
    
    # 検索実行
    result = client.search(query_body)
    end_time = datetime.now()
    
    # レスポンス構築
    hits = []
    for hit in result["hits"]["hits"]:
        source = hit["_source"]
        patent = PatentDocument(**source)
        
        # ハイライト情報を追加（必要に応じて）
        if "highlight" in hit:
            # ハイライト情報をPatentDocumentに追加する場合はここで処理
            pass
            
        hits.append(patent)
    
    return SearchResponse(
        total=result["hits"]["total"]["value"],
        hits=hits,
        took=result["took"],
        query_info={
            "query_type": request.query_type,
            "query": request.query,
            "field": request.field,
            "proximity_distance": request.proximity_distance,
            "boolean_operator": request.boolean_operator,
            "must_terms": request.must_terms,
            "should_terms": request.should_terms, 
            "must_not_terms": request.must_not_terms,
            "field_queries": request.field_queries,
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