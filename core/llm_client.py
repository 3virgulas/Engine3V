"""
3V Engine - LLM Client
=======================
Cliente OpenRouter para Claude 3.5 Sonnet.
Gerencia comunicação com o LLM para raciocínio dos agentes.
"""

from functools import lru_cache
from typing import Any

import httpx
from pydantic import BaseModel

from core.config import settings


class LLMResponse(BaseModel):
    """Resposta estruturada do LLM."""
    content: str
    tokens_used: int
    model: str
    finish_reason: str


class LLMClient:
    """
    Cliente assíncrono para OpenRouter (Claude 3.5 Sonnet).
    Otimizado para raciocínio de trading com baixo custo de tokens.
    """
    
    def __init__(self) -> None:
        self._base_url = settings.openrouter_base_url
        self._api_key = settings.openrouter_api_key
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://3virgulas.com",
            "X-Title": "3V Engine - Forex Analysis"
        }
    
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
        payload = {
            "model": self._model,
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
            model=data.get("model", self._model),
            finish_reason=choice.get("finish_reason", "unknown")
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


@lru_cache
def get_llm_client() -> LLMClient:
    """Retorna instância singleton do cliente LLM."""
    return LLMClient()


# Alias para acesso rápido
llm_client = get_llm_client()
