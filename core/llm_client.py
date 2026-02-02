"""
3V Engine - LLM Client
=======================
Cliente OpenRouter para Claude 3.5 Sonnet.
Gerencia comunicação com o LLM para raciocínio dos agentes.
Suporta modelo dinâmico via Supabase system_settings.
"""

from typing import Any

import httpx
from pydantic import BaseModel

from core.config import settings
from utils.logger import log_agent_action


class LLMResponse(BaseModel):
    """Resposta estruturada do LLM."""
    content: str
    tokens_used: int
    model: str
    finish_reason: str = "unknown"  # Default para APIs que retornam None


class LLMClient:
    """
    Cliente assíncrono para OpenRouter (Claude 3.5 Sonnet).
    Otimizado para raciocínio de trading com baixo custo de tokens.
    
    O modelo pode ser configurado dinamicamente via Supabase:
    1. Consulta tabela system_settings.active_model
    2. Fallback para settings.llm_model do .env
    """
    
    def __init__(self) -> None:
        self._base_url = settings.openrouter_base_url
        self._api_key = settings.openrouter_api_key
        self._default_model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://3virgulas.com",
            "X-Title": "3V Engine - Forex Analysis"
        }
        
        # Cache do modelo ativo (atualizado a cada chamada)
        self._cached_model: str | None = None
    
    async def _get_active_model(self) -> str:
        """
        Obtém o modelo ativo do Supabase.
        Fallback para o modelo padrão do .env se não encontrar.
        
        Returns:
            Nome do modelo a ser usado
        """
        try:
            from core.supabase_client import supabase_client
            
            result = supabase_client.client.table("system_settings") \
                .select("value") \
                .eq("key", "active_model") \
                .limit(1) \
                .execute()
            
            if result.data and len(result.data) > 0:
                model = result.data[0].get("value")
                if model and model != self._cached_model:
                    log_agent_action(
                        "@LLMClient",
                        f"Model changed: {self._cached_model} -> {model}",
                        level="info"
                    )
                    self._cached_model = model
                return model or self._default_model
            
        except Exception as e:
            log_agent_action(
                "@LLMClient",
                f"Failed to fetch active_model from Supabase: {e}",
                level="warning"
            )
        
        # Fallback para modelo padrão
        return self._default_model
    
    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None
    ) -> LLMResponse:
        """
        Envia mensagem para o LLM e retorna resposta estruturada.
        
        Args:
            system_prompt: Prompt de sistema (personalidade do agente)
            user_message: Mensagem do usuário (dados para análise)
            temperature: Override da temperatura (opcional)
            max_tokens: Override do max_tokens (opcional)
        
        Returns:
            LLMResponse com o conteúdo e metadados
        """
        # Obtém modelo ativo (dinâmico via Supabase)
        active_model = await self._get_active_model()
        
        payload = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature or self._temperature,
            "max_tokens": max_tokens or self._max_tokens
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        choice = data["choices"][0]
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=choice["message"]["content"],
            tokens_used=usage.get("total_tokens", 0),
            model=data.get("model", active_model),
            finish_reason=choice.get("finish_reason") or "unknown"  # Handle None explicitly
        )
    
    async def analyze(
        self,
        agent_name: str,
        agent_role: str,
        market_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Executa análise estruturada para um agente específico.
        
        Args:
            agent_name: Nome do agente (ex: @Quant_Analyst)
            agent_role: Descrição do papel do agente
            market_data: Dados de mercado para análise
        
        Returns:
            Análise estruturada do agente
        """
        system_prompt = f"""Você é {agent_name}, um agente especializado no sistema 3V Engine.

Seu papel: {agent_role}

REGRAS:
1. Seja objetivo e baseie-se apenas nos dados fornecidos
2. Responda SEMPRE em JSON válido
3. Inclua confidence_score de 0 a 100
4. Justifique sua análise de forma concisa

FORMATO DE RESPOSTA:
{{
    "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
    "confidence_score": 0-100,
    "analysis": "sua análise aqui",
    "key_factors": ["fator1", "fator2"]
}}"""

        import json
        user_message = f"Analise os seguintes dados de mercado:\n\n{json.dumps(market_data, indent=2)}"
        
        response = await self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.2  # Baixa temperatura para análise técnica
        )
        
        # Parse JSON da resposta
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback se o LLM não retornar JSON válido
            return {
                "signal": "NEUTRAL",
                "confidence_score": 0,
                "analysis": response.content,
                "key_factors": [],
                "error": "Failed to parse JSON response"
            }


# Singleton - instância única
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Retorna instância singleton do cliente LLM."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# Alias para acesso rápido
llm_client = get_llm_client()
