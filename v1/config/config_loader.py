"""
設定ファイル読み込みモジュール
Configuration Loader Module

YAMLファイルから設定を読み込み、システム全体で利用可能にします。
"""

import yaml
import os
from typing import Dict, Any
from pathlib import Path


class Config:
    """設定クラス - シングルトンパターン"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self.load_config()

    def load_config(self, config_path: str = None):
        """
        設定ファイルを読み込む

        Args:
            config_path: 設定ファイルのパス（デフォルト: ./config/ai_config.yaml）
        """
        if config_path is None:
            # デフォルトの設定ファイルパスを構築
            current_dir = Path(__file__).parent
            config_path = current_dir / "ai_config.yaml"

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得

        Args:
            key_path: ドット区切りのキーパス (例: "vertex_ai.project_id")
            default: キーが見つからない場合のデフォルト値

        Returns:
            設定値

        Examples:
            >>> config = Config()
            >>> config.get("vertex_ai.project_id")
            'ttdc-in-house-dev'
            >>> config.get("ai_models.component_analyzer.model_name")
            'claude-sonnet-4-5@20250929'
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_vertex_ai_config(self) -> Dict[str, Any]:
        """Vertex AI設定を取得"""
        return self._config.get('vertex_ai', {})

    def get_component_analyzer_config(self) -> Dict[str, Any]:
        """構成要素分析モデル設定を取得"""
        return self._config.get('ai_models', {}).get('component_analyzer', {})

    def get_keyword_generator_config(self) -> Dict[str, Any]:
        """キーワード生成モデル設定を取得"""
        return self._config.get('ai_models', {}).get('keyword_generator', {})

    def get_api_endpoints(self) -> Dict[str, str]:
        """APIエンドポイント設定を取得"""
        return self._config.get('api_endpoints', {})

    def get_search_parameters(self) -> Dict[str, Any]:
        """検索パラメータ設定を取得"""
        return self._config.get('search_parameters', {})

    @property
    def all(self) -> Dict[str, Any]:
        """全設定を取得"""
        return self._config


# グローバル設定インスタンス
config = Config()
