"""アプリケーション設定"""

import os
from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から設定を読み込むクラス"""

    # プロジェクト情報
    PROJECT_NAME: str = "PatGenius API"
    VERSION: str = "2.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Google Cloud認証
    GOOGLE_CREDENTIALS_PATH: str = "../../credentials/google_credentials.json"
    GOOGLE_CLOUD_PROJECT: str = "ttdc-in-house-dev"

    # PatentField API
    PATENTFIELD_KEY_PATH: str = "../../credentials/patentfield_key.json"
    PATENTFIELD_API_KEY: str = ""
    PATENTFIELD_ENDPOINT: str = "https://ttdc.patentfield.com/api/v1/patents/search"

    # Classification Search API
    CLASSIFICATION_SEARCH_URL: str = "http://localhost:8001"

    # CORS設定
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Claude設定
    CLAUDE_MODEL: str = "claude-sonnet-4-5@20250929"
    CLAUDE_REGION: str = "us-east5"

    # Gemini設定
    GEMINI_MODEL: str = "gemini-3-pro-preview"
    GEMINI_LOCATION: str = "global"

    # サーバー設定
    BACKEND_PORT: int = 8000
    ENVIRONMENT: str = "development"

    class Config:
        env_file = "../../credentials/.env"
        case_sensitive = True
        extra = "allow"  # 追加の環境変数を許可

    @property
    def google_credentials_absolute_path(self) -> str:
        """Google認証情報の絶対パスを返す"""
        base_dir = Path(__file__).parent.parent.parent.parent
        return str(base_dir / self.GOOGLE_CREDENTIALS_PATH)

    @property
    def patentfield_key_absolute_path(self) -> str:
        """PatentField APIキーの絶対パスを返す"""
        base_dir = Path(__file__).parent.parent.parent.parent
        return str(base_dir / self.PATENTFIELD_KEY_PATH)


# グローバル設定インスタンス
settings = Settings()
