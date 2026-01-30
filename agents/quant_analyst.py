"""
3V Engine - Quant Analyst Agent
================================
@Quant_Analyst: Responsável pela análise técnica.
Consome API Twelve Data e calcula indicadores.
"""

from typing import Any

from agents.base import BaseAgent
from utils.twelve_data import twelve_data_client


class QuantAnalystAgent(BaseAgent):
    """
    @Quant_Analyst - Especialista em Análise Técnica
    
    Responsabilidades:
    - Monitorar preços em tempo real via Twelve Data
    - Calcular Médias Móveis (20/50/200)
    - Calcular RSI e Bandas de Bollinger
    - Identificar padrões de candlesticks
    - Emitir sinal técnico (BULLISH/BEARISH/NEUTRAL)
    """
    
    @property
    def name(self) -> str:
        return "@Quant_Analyst"
    
    @property
    def role(self) -> str:
        return """Analista Quantitativo especializado em análise técnica de Forex.
        
Você analisa:
1. Médias Móveis (20, 50, 200) - Tendência de curto, médio e longo prazo
2. RSI (14 períodos) - Condições de sobrecompra/sobrevenda
3. Bandas de Bollinger - Volatilidade e posição do preço
4. Padrões de Candlesticks - Reversões e continuações

Sua análise deve ser objetiva, baseada APENAS nos dados técnicos.
Não considere notícias ou eventos macroeconômicos - outros agentes fazem isso."""
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Executa análise técnica completa.
        
        Args:
            market_state: Estado do mercado (pode ser ignorado, usamos dados frescos)
        
        Returns:
            Análise técnica com indicadores e sinal
        """
        self.log("Starting technical analysis")
        
        # Obtém dados técnicos frescos
        technical_data = await twelve_data_client.get_technical_analysis()
        
        self.log("Technical data retrieved", {
            "price": technical_data["current_price"],
            "rsi": technical_data["rsi"]["rsi"],
            "trend": technical_data["moving_averages"].get("trend")
        })
        
        # Usa LLM para interpretar os dados
        llm_analysis = await self.reason(technical_data)
        
        # Combina dados técnicos com análise do LLM
        result = {
            "agent": self.name,
            "timestamp": technical_data["timestamp"],
            "raw_data": technical_data,
            "llm_analysis": llm_analysis,
            "signal": llm_analysis.get("signal", "NEUTRAL"),
            "confidence": llm_analysis.get("confidence_score", 50)
        }
        
        self.log("Analysis complete", {
            "signal": result["signal"],
            "confidence": result["confidence"]
        })
        
        return result


# Singleton
quant_analyst = QuantAnalystAgent()
