"""
Google Patents Search API
FastAPI endpoints for searching Google Patents using web scraping
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path
import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

from src.core.google_patents_scraper_playwright import GooglePatentsScraperPlaywright


# ============================================================================
# Pydantic Models
# ============================================================================

class SearchCondition(str, Enum):
    """Search condition type"""
    AND = "and"
    OR = "or"
    NOT = "not"
    NEAR = "near"


class GooglePatentsSearchRequest(BaseModel):
    """Request model for Google Patents search"""
    keywords: Optional[List[str]] = Field(None, description="Keywords to search")
    fi_codes: Optional[List[str]] = Field(None, description="FI classification codes")
    ipc_codes: Optional[List[str]] = Field(None, description="IPC classification codes")
    cpc_codes: Optional[List[str]] = Field(None, description="CPC classification codes")
    advanced_query: Optional[str] = Field(
        None,
        description="Advanced query string (e.g., 'agriculture AND (soil OR farming) NOT pesticide NEAR/5 crop')"
    )
    max_results: int = Field(50, ge=1, le=1000, description="Maximum number of results to retrieve")
    language: str = Field("en", description="Language for results (en, ja, etc.)")
    cpc_ranking_only: bool = Field(
        False,
        description="If True, only retrieve CPC ranking statistics without fetching individual patent details (much faster)"
    )
    max_ranking_items: int = Field(
        50,
        ge=1,
        le=100,
        description="Maximum number of CPC ranking items to return when cpc_ranking_only=True"
    )


class PatentResult(BaseModel):
    """Individual patent result"""
    patent_number: str
    title: str
    assignee: str
    publication_date: str
    cpc_codes: List[str]
    url: str
    pdf_url: Optional[str]


class CPCRanking(BaseModel):
    """CPC code ranking"""
    cpc_code: str
    count: int
    percentage: float


class GooglePatentsSearchResponse(BaseModel):
    """Response model for Google Patents search"""
    query: str
    total_hits: int
    results_count: int
    patents: List[PatentResult]
    cpc_ranking: List[CPCRanking]
    patent_numbers: List[str]


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Google Patents Search API",
    description="API for searching Google Patents with support for advanced queries (AND, OR, NOT, NEAR)",
    version="1.0.0"
)

# ThreadPoolExecutor for running sync Playwright code in async FastAPI
executor = ThreadPoolExecutor(max_workers=3)

# Playwright-based scraper
# Each request gets a fresh scraper instance
# Playwright manages browser lifecycle internally


def get_scraper() -> GooglePatentsScraperPlaywright:
    """
    Create scraper instance using Playwright

    Returns a new Playwright-based scraper instance for each request.
    Playwright manages browser lifecycle internally.
    """
    return GooglePatentsScraperPlaywright(headless=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    # Playwright manages its own lifecycle - no cleanup needed
    pass


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Google Patents Search API",
        "version": "1.0.0",
        "endpoints": {
            "/search": "Search Google Patents (POST)",
            "/search/simple": "Simple keyword search (GET)",
            "/download/{patent_number}": "Download patent PDF (GET)",
            "/health": "Health check"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "google-patents-api"}


@app.get("/search/simple", response_model=GooglePatentsSearchResponse)
async def simple_search(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(50, ge=1, le=1000, description="Maximum results"),
    language: str = Query("en", description="Language (en, ja, etc.)")
):
    """
    Simple keyword search on Google Patents

    Example:
        GET /search/simple?q=agriculture&max_results=20
        GET /search/simple?q=agriculture+AND+soil&max_results=50
    """
    try:
        # Run sync Playwright code in thread pool
        loop = asyncio.get_event_loop()

        def sync_search():
            scraper_instance = get_scraper()
            try:
                results = scraper_instance.search(
                    query=q,
                    max_results=max_results,
                    language=language
                )
                return results
            finally:
                scraper_instance.close()

        results = await loop.run_in_executor(executor, sync_search)

        # Convert to response model
        return GooglePatentsSearchResponse(
            query=results["query"],
            total_hits=results["total_hits"],
            results_count=results["results_count"],
            patents=[PatentResult(**p) for p in results["patents"]],
            cpc_ranking=[CPCRanking(**c) for c in results["cpc_ranking"]],
            patent_numbers=[p["patent_number"] for p in results["patents"]]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/search", response_model=GooglePatentsSearchResponse)
async def advanced_search(request: GooglePatentsSearchRequest):
    """
    Advanced search on Google Patents with support for:
    - Keywords with operators (AND, OR, NOT, NEAR)
    - FI, IPC, CPC classification codes
    - Custom advanced query strings

    Example request body:
    {
        "keywords": ["agriculture", "soil"],
        "fi_codes": ["A01B33/00"],
        "advanced_query": "agriculture AND (soil OR farming) NOT pesticide",
        "max_results": 100,
        "language": "en"
    }
    """
    try:
        # Run sync Playwright code in thread pool
        loop = asyncio.get_event_loop()

        def sync_advanced_search():
            scraper_instance = get_scraper()
            try:
                # Build search query
                query = scraper_instance.build_search_query(
                    keywords=request.keywords,
                    fi_codes=request.fi_codes,
                    ipc_codes=request.ipc_codes,
                    cpc_codes=request.cpc_codes,
                    advanced_query=request.advanced_query
                )

                if not query:
                    raise ValueError("No search criteria provided")

                # Execute search
                results = scraper_instance.search(
                    query=query,
                    max_results=request.max_results,
                    language=request.language,
                    cpc_ranking_only=request.cpc_ranking_only,
                    max_ranking_items=request.max_ranking_items
                )
                return results
            finally:
                scraper_instance.close()

        results = await loop.run_in_executor(executor, sync_advanced_search)

        # Convert to response model
        return GooglePatentsSearchResponse(
            query=results["query"],
            total_hits=results["total_hits"],
            results_count=results["results_count"],
            patents=[PatentResult(**p) for p in results["patents"]],
            cpc_ranking=[CPCRanking(**c) for c in results["cpc_ranking"]],
            patent_numbers=[p["patent_number"] for p in results["patents"]]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/download/{patent_number}")
async def download_patent_pdf(
    patent_number: str,
    background_tasks: BackgroundTasks
):
    """
    Download patent PDF

    Args:
        patent_number: Patent number (e.g., US1234567A)

    Returns:
        PDF file

    Example:
        GET /download/US1234567A
    """
    try:
        # Create downloads directory
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(exist_ok=True)

        output_path = downloads_dir / f"{patent_number}.pdf"

        # Run sync Playwright code in thread pool
        loop = asyncio.get_event_loop()

        def sync_download():
            scraper_instance = get_scraper()
            try:
                success = scraper_instance.download_pdf(patent_number, str(output_path))
                return success
            finally:
                scraper_instance.close()

        success = await loop.run_in_executor(executor, sync_download)

        if not success:
            raise HTTPException(status_code=404, detail=f"Failed to download PDF for {patent_number}")

        # Schedule cleanup after response is sent
        def cleanup():
            try:
                output_path.unlink()
            except:
                pass

        background_tasks.add_task(cleanup)

        # Return PDF file
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"{patent_number}.pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.get("/patent_numbers", response_model=Dict[str, Any])
async def get_patent_numbers(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(100, ge=1, le=1000)
):
    """
    Get only patent numbers from search (faster than full search)

    Example:
        GET /patent_numbers?q=agriculture&max_results=100
    """
    try:
        # Run sync Playwright code in thread pool
        loop = asyncio.get_event_loop()

        def sync_get_patent_numbers():
            scraper_instance = get_scraper()
            try:
                results = scraper_instance.search(
                    query=q,
                    max_results=max_results
                )
                return results
            finally:
                scraper_instance.close()

        results = await loop.run_in_executor(executor, sync_get_patent_numbers)

        return {
            "query": results["query"],
            "total_hits": results["total_hits"],
            "patent_numbers": [p["patent_number"] for p in results["patents"]]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/cpc_ranking", response_model=Dict[str, Any])
async def get_cpc_ranking(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(100, ge=1, le=1000),
    top_k: int = Query(20, ge=1, le=100, description="Top K CPC codes to return")
):
    """
    Get CPC code ranking from search results

    Example:
        GET /cpc_ranking?q=agriculture&max_results=100&top_k=10
    """
    try:
        # Run sync Playwright code in thread pool
        loop = asyncio.get_event_loop()

        def sync_get_cpc_ranking():
            scraper_instance = get_scraper()
            try:
                results = scraper_instance.search(
                    query=q,
                    max_results=max_results
                )
                return results
            finally:
                scraper_instance.close()

        results = await loop.run_in_executor(executor, sync_get_cpc_ranking)

        return {
            "query": results["query"],
            "total_hits": results["total_hits"],
            "results_analyzed": results["results_count"],
            "cpc_ranking": results["cpc_ranking"][:top_k]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ============================================================================
# Main
# ============================================================================

def main():
    """Run the API server"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # Different port from classification API
        log_level="info"
    )


if __name__ == "__main__":
    main()
