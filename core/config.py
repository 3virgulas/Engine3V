"""
3V Engine - Configuration Module
================================
Carrega e valida variáveis de ambiente usando Pydantic Settings.
Todas as configurações são tipadas e validadas no startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações centralizadas do 3V Engine.
    Carrega automaticamente do arquivo .env.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Keys
    twelve_data_api_key: str = Field(..., description="Twelve Data API Key")
    finnhub_api_key: str = Field(..., description="Finnhub API Key")
    fmp_api_key: str | None = Field(default=None, description="Financial Modeling Prep API Key (not used)")
    openrouter_api_key: str = Field(..., description="OpenRouter API Key")
    
    # Supabase
    supabase_url: str = Field(..., description="Supabase Project URL")
    supabase_service_key: str = Field(..., description="Supabase Service Role Key")
    
    # Telegram Notifications (Optional)
    telegram_bot_token: str | None = Field(default=None, description="Telegram Bot Token")
    telegram_chat_id: str | None = Field(default=None, description="Telegram Chat ID for notifications")
    
    # Trading Configuration
    trading_pair: str = Field(default="EUR/USD", description="Par de moedas para análise")
    analysis_interval_minutes: int = Field(default=5, ge=1, le=60, description="Intervalo de análise em minutos")
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    
    # LLM Configuration
    llm_model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        description="Modelo LLM via OpenRouter"
    )
    llm_temperature: float = Field(default=0.3, ge=0, le=1)
    llm_max_tokens: int = Field(default=2048, ge=256, le=8192)
    
    # API Base URLs
    twelve_data_base_url: str = Field(default="https://api.twelvedata.com")
    finnhub_base_url: str = Field(default="https://finnhub.io/api/v1")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    Uso: `from core.config import get_settings; settings = get_settings()`
    """
    return Settings()


# Alias para acesso rápido
settings = get_settings()
