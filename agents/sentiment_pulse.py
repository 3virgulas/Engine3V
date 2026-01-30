"""
3V Engine - Sentiment Pulse Agent
==================================
@Sentiment_Pulse: Responsável pela análise de sentimento.
Consome API Finnhub para análise de notícias.
"""

from typing import Any

from agents.base import BaseAgent
from utils.finnhub import finnhub_client


class SentimentPulseAgent(BaseAgent):
    """
    @Sentiment_Pulse - Especialista em Sentimento de Mercado
    
    Responsabilidades:
    - Monitorar notícias de Forex via Finnhub
    - Analisar sentimento das últimas 20 notícias
    - Calcular score de -1 (Bearish) a +1 (Bullish)
    - Identificar narrativas dominantes no mercado
    """
    
    @property
    def name(self) -> str:
        return "@Sentiment_Pulse"
    
    @property
    def role(self) -> str:
        return """Analista de Sentimento especializado em percepção de mercado Forex.
        
Você analisa:
1. Notícias recentes sobre EUR e USD
2. Declarações do BCE (ECB) e Fed
3. Narrativas dominantes no mercado
4. Mudanças de tom na mídia financeira

Seu score de sentimento varia de:
- -1.0: Extremamente Bearish para EUR/USD
- 0.0: Neutro
- +1.0: Extremamente Bullish para EUR/USD

Considere o CONTEXTO das notícias, não apenas palavras-chave."""
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Executa análise de sentimento.
        
        Args:
            market_state: Estado do mercado (contexto adicional)
        
        Returns:
            Score de sentimento e análise
        """
        self.log("Starting sentiment analysis")
        
        # Obtém sentimento de notícias
        sentiment_data = await finnhub_client.get_news_sentiment(symbol="EUR")
        
        self.log("Sentiment data retrieved", {
            "score": sentiment_data["score"],
            "label": sentiment_data["label"],
            "articles": sentiment_data["articles_analyzed"]
        })
        
        # Se houver artigos suficientes, usa LLM para análise mais profunda
        if sentiment_data["articles_analyzed"] >= 3:
            llm_input = {
                "sentiment_score": sentiment_data["score"],
                "headlines": sentiment_data.get("recent_headlines", []),
                "bullish_signals": sentiment_data["bullish_signals"],
                "bearish_signals": sentiment_data["bearish_signals"]
            }
            llm_analysis = await self.reason(llm_input)
        else:
            llm_analysis = {
                "signal": sentiment_data["label"],
                "confidence_score": 30,
                "analysis": "Insufficient news data for deep analysis",
                "key_factors": []
            }
        
        result = {
            "agent": self.name,
            "timestamp": sentiment_data["timestamp"],
            "raw_data": sentiment_data,
            "llm_analysis": llm_analysis,
            "sentiment_score": sentiment_data["score"],
            "signal": llm_analysis.get("signal", sentiment_data["label"]),
            "confidence": llm_analysis.get("confidence_score", 50)
        }
        
        self.log("Analysis complete", {
            "score": result["sentiment_score"],
            "signal": result["signal"]
        })
        
        return result


# Singleton
sentiment_pulse = SentimentPulseAgent()
