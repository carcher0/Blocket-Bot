"""
Configuration and environment handling for Blocket Bot v2.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = Field(default="gpt-4o")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.3)


class MySQLConfig(BaseModel):
    """MySQL database configuration."""
    host: str = Field(default_factory=lambda: os.getenv("MYSQL_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    user: str = Field(default_factory=lambda: os.getenv("MYSQL_USER", "root"))
    password: str = Field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    database: str = Field(default_factory=lambda: os.getenv("MYSQL_DATABASE", "blocket_bot_v2"))


class PipelineConfig(BaseModel):
    """Pipeline processing configuration."""
    discovery_sample_size: int = Field(default=30, description="Listings to sample for domain discovery")
    candidate_limit: int = Field(default=50, description="Max candidates after filtering")
    top_k: int = Field(default=10, description="Final top results to return")
    min_comps_for_pricing: int = Field(default=3, description="Minimum comps for reliable pricing")


class UIConfig(BaseModel):
    """UI configuration."""
    page_title: str = Field(default="Blocket Bot 2.0")
    page_icon: str = Field(default="🔍")
    theme_primary_color: str = Field(default="#0077B5")  # Blocket blue
    theme_accent_color: str = Field(default="#FFD200")   # Blocket yellow


class Config(BaseModel):
    """Main configuration."""
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    
    # Paths
    exports_dir: Path = Field(default=Path("exports"))
    cache_dir: Path = Field(default=Path(".cache"))
    
    # Feature flags
    enable_ai_discovery: bool = Field(default=True)
    enable_ai_enrichment: bool = Field(default=True)
    enable_debug_panel: bool = Field(default=True)


# Singleton config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the singleton config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
