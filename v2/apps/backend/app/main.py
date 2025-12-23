"""FastAPIメインアプリケーション"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

# アプリケーション初期化
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="特許検索・分析システム - AI駆動型先行技術調査プラットフォーム",
    version=settings.VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの登録（将来実装）
# from app.api.v1.router import api_router
# app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """ルートエンドポイント"""
    return {
        "message": "PatGenius API",
        "version": settings.VERSION,
        "docs": "/api/docs",
        "status": "operational"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
