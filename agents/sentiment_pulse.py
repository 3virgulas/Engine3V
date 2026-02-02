"""
3V Engine - Sentiment Pulse Agent
==================================
@Sentiment_Pulse: Responsável pela análise de sentimento.
Consome Finnhub + Redes Sociais (Twitter, Reddit, StockTwits).
"""

from typing import Any

from agents.base import BaseAgent
from utils.finnhub import finnhub_client
from utils.social_sentiment import social_sentiment


class SentimentPulseAgent(BaseAgent):
    """
    @Sentiment_Pulse - Especialista em Sentimento de Mercado
    
    Responsabilidades:
    - Monitorar notícias de Forex via Finnhub
    - Analisar sentimento em redes sociais (Twitter, Reddit, StockTwits)
    - Agregar múltiplas fontes com pesos configuráveis
    - Calcular score de -1 (Bearish) a +1 (Bullish)
    - Identificar narrativas dominantes no mercado
    """
    
    @property
    def name(self) -> str:
        return "@Sentiment_Pulse"
    
    @property
    def role(self) -> str:
        return """Analista de Sentimento especializado em percepção de mercado Forex.
        
Você analisa MÚLTIPLAS FONTES:
1. Notícias financeiras (Finnhub)
2. Reddit (r/forex, r/ForexTrading)
3. StockTwits (traders ativos)
4. Twitter/X (quando disponível)

Seu score de sentimento varia de:
- -1.0: Extremamente Bearish para EUR/USD
- 0.0: Neutro
- +1.0: Extremamente Bullish para EUR/USD

IMPORTANTE: Pondere mais as fontes com mais dados. Redes sociais
capturam o "mood" dos traders retail em tempo real."""
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Executa análise de sentimento multi-fonte.
        
        Fontes:
        1. Finnhub News (40%)
        2. Social Media Agregado (60%)
           - Reddit (30%)
           - StockTwits (20%)
           - Twitter (40% se disponível)
        
        Args:
            market_state: Estado do mercado (contexto adicional)
        
        Returns:
            Score de sentimento agregado e breakdown por fonte
        """
        self.log("Starting multi-source sentiment analysis")
        
        # ==================== FINNHUB NEWS ====================
        self.log("Fetching Finnhub news sentiment")
        news_sentiment = await finnhub_client.get_news_sentiment(symbol="EUR")
        
        # ==================== SOCIAL MEDIA ====================
        self.log("Fetching social media sentiment")
        social_data = await social_sentiment.get_aggregated_sentiment()
        
        # ==================== AGREGAÇÃO FINAL ====================
        # Pesos: News 40%, Social 60%
        news_score = news_sentiment.get("score", 0)
        social_score = social_data.get("aggregated_score", 0)
        
        # Se social não disponível, usa só news
        if not social_data.get("sources_available"):
            final_score = news_score
            source_weight = "100% News (Social unavailable)"
        else:
            final_score = (news_score * 0.4) + (social_score * 0.6)
            source_weight = "40% News + 60% Social"
        
        # Determina label
        if final_score > 0.15:
            label = "BULLISH"
        elif final_score < -0.15:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        
        # Contagem total de dados
        total_articles = news_sentiment.get("articles_analyzed", 0)
        total_posts = social_data.get("total_posts_analyzed", 0)
        
        self.log("Multi-source data aggregated", {
            "news_score": news_score,
            "social_score": social_score,
            "final_score": round(final_score, 2),
            "label": label,
            "articles": total_articles,
            "posts": total_posts
        })
        
        # ==================== LLM DEEP ANALYSIS ====================
        # Se houver dados suficientes, usa LLM para análise profunda
        if total_articles >= 3 or total_posts >= 10:
            llm_input = {
                "news_sentiment": {
                    "score": news_score,
                    "headlines": news_sentiment.get("recent_headlines", [])[:5],
                    "bullish_signals": news_sentiment.get("bullish_signals", 0),
                    "bearish_signals": news_sentiment.get("bearish_signals", 0)
                },
                "social_sentiment": {
                    "score": social_score,
                    "sources": social_data.get("sources_available", []),
                    "total_posts": total_posts,
                    "reddit": social_data.get("sources_breakdown", {}).get("reddit", {}),
                    "stocktwits": social_data.get("sources_breakdown", {}).get("stocktwits", {})
                },
                "final_score": final_score
            }
            llm_analysis = await self.reason(llm_input)
        else:
            llm_analysis = {
                "signal": label,
                "confidence_score": 30,
                "analysis": "Insufficient data for deep analysis",
                "key_factors": []
            }
        
        # ==================== RESULTADO FINAL ====================
        result = {
            "agent": self.name,
            "timestamp": social_data.get("timestamp", news_sentiment.get("timestamp")),
            
            # Scores individuais
            "news_score": news_score,
            "social_score": social_score,
            "sentiment_score": round(final_score, 2),
            
            # Label e sinal
            "signal": llm_analysis.get("signal", label),
            "confidence": llm_analysis.get("confidence_score", 50),
            
            # Dados brutos para outros agentes
            "raw_data": {
                "score": final_score,
                "label": label,
                "articles_analyzed": total_articles,
                "social_posts_analyzed": total_posts,
                "source_weight": source_weight,
                
                # Headlines para CIO
                "headlines": news_sentiment.get("recent_headlines", [])[:5],
                
                # Breakdown por fonte
                "sources": {
                    "finnhub_news": {
                        "score": news_score,
                        "articles": total_articles,
                        "label": news_sentiment.get("label", "NEUTRAL")
                    },
                    "reddit": social_data.get("sources_breakdown", {}).get("reddit", {}),
                    "stocktwits": social_data.get("sources_breakdown", {}).get("stocktwits", {}),
                    "twitter": social_data.get("sources_breakdown", {}).get("twitter", {})
                },
                
                # Bullish/Bearish signals
                "bullish_signals": news_sentiment.get("bullish_signals", 0),
                "bearish_signals": news_sentiment.get("bearish_signals", 0)
            },
            
            # Análise LLM
            "llm_analysis": llm_analysis
        }
        
        self.log("Analysis complete", {
            "final_score": result["sentiment_score"],
            "signal": result["signal"],
            "sources": social_data.get("sources_available", [])
        })
        
        return result


# Singleton
sentiment_pulse = SentimentPulseAgent()

