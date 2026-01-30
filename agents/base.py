"""
3V Engine - Base Agent
=======================
Classe abstrata base para todos os agentes do sistema.
Define interface comum e integração com LLM.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from core.llm_client import llm_client
from utils.logger import log_agent_action


class AgentSignal(BaseModel):
    """Sinal padrão emitido por um agente."""
    signal: str  # BULLISH, BEARISH, NEUTRAL
    confidence_score: int  # 0-100
    analysis: str
    key_factors: list[str]


class BaseAgent(ABC):
    """
    Classe base abstrata para agentes do 3V Engine.
    
    Todos os agentes devem implementar:
    - name: Nome do agente (ex: @Quant_Analyst)
    - role: Descrição do papel do agente
    - analyze(): Método principal de análise
    """
    
    def __init__(self) -> None:
        self._llm = llm_client
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome único do agente (ex: @Quant_Analyst)."""
        pass
    
    @property
    @abstractmethod
    def role(self) -> str:
        """Descrição do papel do agente no sistema."""
        pass
    
    @abstractmethod
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Executa análise principal do agente.
        
        Args:
            market_state: Estado atual do mercado compartilhado
        
        Returns:
            Resultado da análise do agente
        """
        pass
    
    async def reason(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Usa LLM para raciocínio sobre os dados.
        
        Args:
            data: Dados para análise pelo LLM
        
        Returns:
            Análise estruturada do LLM
        """
        log_agent_action(self.name, "Reasoning with LLM")
        return await self._llm.analyze(
            agent_name=self.name,
            agent_role=self.role,
            market_data=data
        )
    
    def log(self, action: str, data: dict | None = None, level: str = "info") -> None:
        """Log facilitado para o agente."""
        log_agent_action(self.name, action, data, level)
