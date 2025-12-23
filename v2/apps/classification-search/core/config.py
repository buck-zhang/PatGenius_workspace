"""Configuration management for the patent classification search system."""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "patent_classifications"

    # Embedding Models
    text_embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    image_embedding_model: str = "openai/clip-vit-base-patch32"

    # Data Path
    data_path: Path = Path("../data_20250812")

    # Vector Store Settings
    vector_dimension: int = 768  # For multilingual-mpnet
    image_vector_dimension: int = 512  # For CLIP

    # Search Settings
    default_limit: int = 20
    max_limit: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
