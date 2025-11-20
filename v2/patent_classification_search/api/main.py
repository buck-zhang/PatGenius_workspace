"""Main FastAPI application for patent classification search."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from ..core.config import settings
from ..core.embeddings import EmbeddingManager
from ..core.vector_store import VectorStore
from .routes import search, health


# Global instances
embedding_manager: EmbeddingManager = None
vector_store: VectorStore = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Patent Classification Search API...")

    global embedding_manager, vector_store

    try:
        # Initialize embedding models
        logger.info("Loading embedding models...")
        embedding_manager = EmbeddingManager(
            text_model_name=settings.text_embedding_model,
            image_model_name=settings.image_embedding_model
        )
        logger.info("Embedding models loaded successfully")

        # Initialize vector store
        logger.info("Connecting to Qdrant...")
        vector_store = VectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name,
            vector_dimension=embedding_manager.text_dimension
        )
        logger.info("Connected to Qdrant successfully")

        # Setup route dependencies
        search.setup_search_dependencies(embedding_manager, vector_store)
        health.setup_health_dependencies(vector_store)

        logger.info("API startup complete")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Patent Classification Search API...")


# Create FastAPI app
app = FastAPI(
    title="Patent Classification Search API",
    description="""
    RAG-based search engine for patent classification codes (IPC, CPC, FI).

    ## Features

    - **Text Search**: Semantic search using natural language queries
    - **Code Search**: Direct lookup by classification codes
    - **Boolean Search**: Combined search with OR/AND operators
    - **Image Search**: Search using images with CLIP embeddings
    - **Multi-classification Support**: Search across IPC, CPC, and FI classifications

    ## Data Sources

    - **IPC**: International Patent Classification
    - **CPC**: Cooperative Patent Classification
    - **FI**: File Index (Japanese Patent Classification)
    """,
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(health.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Patent Classification Search API",
        "version": "2.0.0",
        "status": "running",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
