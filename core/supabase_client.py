"""
3V Engine - Supabase Client
============================
Cliente singleton para operações de banco de dados.
Usado exclusivamente no servidor (Service Role Key).
"""

from functools import lru_cache
from typing import Any

from supabase import create_client, Client

from core.config import settings


class SupabaseClient:
    """
    Cliente Supabase para audit trail e logging.
    Usa Service Role Key para bypass de RLS.
    """
    
    def __init__(self) -> None:
        self._client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
    
    @property
    def client(self) -> Client:
        """Retorna o cliente Supabase."""
        return self._client
    
    async def log_decision(
        self,
        pair: str,
        technical_signal: dict[str, Any],
        sentiment_score: float,
        macro_alert: str,
        final_decision: str,
        reasoning: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Registra uma decisão dos agentes no audit trail.
        
        Args:
            pair: Par de moedas (ex: EUR/USD)
            technical_signal: Sinal do @Quant_Analyst
            sentiment_score: Score do @Sentiment_Pulse (-1 a +1)
            macro_alert: Alerta do @Macro_Watcher
            final_decision: Decisão do @Risk_Commander
            reasoning: Raciocínio completo de cada agente
        
        Returns:
            Registro inserido
        """
        data = {
            "pair": pair,
            "technical_signal": technical_signal,
            "sentiment_score": sentiment_score,
            "macro_alert": macro_alert,
            "final_decision": final_decision,
            "reasoning": reasoning
        }
        
        result = self._client.table("agent_decisions").insert(data).execute()
        return result.data[0] if result.data else {}
    
    async def get_recent_decisions(
        self,
        pair: str = "EUR/USD",
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Recupera as decisões mais recentes para um par.
        
        Args:
            pair: Par de moedas
            limit: Número máximo de registros
        
        Returns:
            Lista de decisões ordenadas por data (mais recente primeiro)
        """
        result = (
            self._client
            .table("agent_decisions")
            .select("*")
            .eq("pair", pair)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []


@lru_cache
def get_supabase_client() -> SupabaseClient:
    """Retorna instância singleton do cliente Supabase."""
    return SupabaseClient()


# Alias para acesso rápido
supabase_client = get_supabase_client()
