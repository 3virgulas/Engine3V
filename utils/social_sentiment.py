"""
Social Sentiment Module - 3V Engine
===================================
Análise de sentimento de múltiplas fontes sociais.

Features:
- Twitter/X API (quando disponível)
- Reddit (forex/trading subreddits)
- StockTwits
- Agregação de múltiplas fontes
- Cache para evitar rate limits
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any
import httpx
import re

from core.config import settings
from utils.logger import log_agent_action


class SocialSentimentClient:
    """
    Cliente para análise de sentimento em múltiplas redes sociais.
    
    Suporta:
    - Twitter/X API v2 (requer chave paga)
    - Reddit API (gratuito com limites)
    - StockTwits API (gratuito)
    - RSS/News feeds
    
    O sentimento é agregado de todas as fontes disponíveis
    com pesos configuráveis.
    """
    
    # Pesos para cada fonte (total = 1.0)
    SOURCE_WEIGHTS = {
        "twitter": 0.40,
        "reddit": 0.30,
        "stocktwits": 0.20,
        "news_rss": 0.10
    }
    
    # Keywords para Forex EUR/USD
    FOREX_KEYWORDS = [
        "EURUSD", "EUR/USD", "euro dollar",
        "EUR", "USD", "ECB", "Fed",
        "forex", "FX", "currency",
        "Lagarde", "Powell",
        "eurozone", "inflation euro",
        "dollar index", "DXY"
    ]
    
    # Palavras bullish/bearish para análise
    BULLISH_WORDS = [
        "bullish", "long", "buy", "up", "rally", "breakout",
        "moon", "gains", "surge", "soar", "strong", "higher",
        "support", "accumulation", "recovery"
    ]
    
    BEARISH_WORDS = [
        "bearish", "short", "sell", "down", "crash", "breakdown",
        "dump", "losses", "plunge", "weak", "lower", "fall",
        "resistance", "distribution", "decline"
    ]
    
    def __init__(self):
        self.name = "@SocialSentiment"
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutos
        
        # API Keys (opcionais)
        self.twitter_bearer = getattr(settings, 'twitter_bearer_token', None)
        self.reddit_client_id = getattr(settings, 'reddit_client_id', None)
        self.reddit_secret = getattr(settings, 'reddit_client_secret', None)
        
    def log(self, message: str, data: dict | None = None, level: str = "info"):
        """Log com estrutura padronizada."""
        log_agent_action(self.name, message, data, level)
    
    def _analyze_text_sentiment(self, text: str) -> dict[str, Any]:
        """
        Analisa sentimento de um texto usando keywords.
        
        Args:
            text: Texto para análise
        
        Returns:
            Dict com score e breakdown
        """
        text_lower = text.lower()
        
        bullish_count = sum(1 for word in self.BULLISH_WORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_WORDS if word in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return {"score": 0, "bullish": 0, "bearish": 0, "label": "NEUTRAL"}
        
        score = (bullish_count - bearish_count) / max(total, 1)
        
        if score > 0.2:
            label = "BULLISH"
        elif score < -0.2:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        
        return {
            "score": round(score, 2),
            "bullish": bullish_count,
            "bearish": bearish_count,
            "label": label
        }
    
    # ==================== TWITTER/X ====================
    
    async def get_twitter_sentiment(self, query: str = "EURUSD") -> dict[str, Any]:
        """
        Busca sentimento do Twitter/X.
        
        NOTA: Requer Twitter API v2 Bearer Token (plano pago $100+/mês)
        Se não disponível, retorna dados vazios.
        
        Args:
            query: Query de busca
        
        Returns:
            Dict com sentimento do Twitter
        """
        if not self.twitter_bearer:
            self.log("Twitter API not configured (requires paid plan)", level="debug")
            return {
                "source": "twitter",
                "available": False,
                "score": 0,
                "posts_analyzed": 0,
                "message": "Twitter API requires Bearer Token ($100+/month plan)"
            }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {self.twitter_bearer}"}
                
                # Search recent tweets
                params = {
                    "query": f"{query} -is:retweet lang:en",
                    "max_results": 100,
                    "tweet.fields": "created_at,public_metrics"
                }
                
                response = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    return {
                        "source": "twitter",
                        "available": False,
                        "score": 0,
                        "error": f"API returned {response.status_code}"
                    }
                
                data = response.json()
                tweets = data.get("data", [])
                
                if not tweets:
                    return {
                        "source": "twitter",
                        "available": True,
                        "score": 0,
                        "posts_analyzed": 0
                    }
                
                # Analisa sentimento de cada tweet
                sentiments = []
                sample_tweets = []
                
                for tweet in tweets[:50]:  # Limita a 50 tweets
                    text = tweet.get("text", "")
                    sentiment = self._analyze_text_sentiment(text)
                    sentiments.append(sentiment["score"])
                    
                    if len(sample_tweets) < 5:
                        sample_tweets.append({
                            "text": text[:200],
                            "sentiment": sentiment["label"]
                        })
                
                avg_score = sum(sentiments) / len(sentiments) if sentiments else 0
                
                return {
                    "source": "twitter",
                    "available": True,
                    "score": round(avg_score, 2),
                    "posts_analyzed": len(sentiments),
                    "sample_posts": sample_tweets,
                    "label": "BULLISH" if avg_score > 0.1 else "BEARISH" if avg_score < -0.1 else "NEUTRAL"
                }
                
        except Exception as e:
            self.log(f"Twitter API error: {e}", level="warning")
            return {
                "source": "twitter",
                "available": False,
                "score": 0,
                "error": str(e)
            }
    
    # ==================== REDDIT ====================
    
    async def get_reddit_sentiment(
        self,
        subreddits: list[str] = ["forex", "Forex", "ForexTrading"]
    ) -> dict[str, Any]:
        """
        Busca sentimento de subreddits de Forex.
        
        Usa API pública do Reddit (limite: 60 req/min).
        
        Args:
            subreddits: Lista de subreddits para buscar
        
        Returns:
            Dict com sentimento do Reddit
        """
        try:
            all_posts = []
            
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": "3VEngine/1.0"}
                
                for subreddit in subreddits:
                    try:
                        # Busca posts recentes (últimas 24h)
                        response = await client.get(
                            f"https://www.reddit.com/r/{subreddit}/new.json",
                            headers=headers,
                            params={"limit": 25}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            posts = data.get("data", {}).get("children", [])
                            
                            for post in posts:
                                post_data = post.get("data", {})
                                title = post_data.get("title", "")
                                selftext = post_data.get("selftext", "")
                                
                                # Filtra posts relevantes para EUR/USD
                                full_text = f"{title} {selftext}"
                                if any(kw.lower() in full_text.lower() for kw in self.FOREX_KEYWORDS):
                                    all_posts.append({
                                        "title": title,
                                        "text": selftext[:500],
                                        "score": post_data.get("score", 0),
                                        "subreddit": subreddit
                                    })
                    except Exception as e:
                        self.log(f"Reddit r/{subreddit} error: {e}", level="debug")
                        continue
                    
                    # Rate limit: aguarda entre subreddits
                    await asyncio.sleep(0.5)
            
            if not all_posts:
                return {
                    "source": "reddit",
                    "available": True,
                    "score": 0,
                    "posts_analyzed": 0,
                    "message": "No relevant EUR/USD posts found"
                }
            
            # Analisa sentimento
            sentiments = []
            sample_posts = []
            
            for post in all_posts[:30]:  # Limita a 30 posts
                full_text = f"{post['title']} {post['text']}"
                sentiment = self._analyze_text_sentiment(full_text)
                
                # Pondera pelo score do post (upvotes)
                weight = min(1 + (post["score"] / 100), 3)  # Max 3x
                sentiments.append(sentiment["score"] * weight)
                
                if len(sample_posts) < 5:
                    sample_posts.append({
                        "title": post["title"][:100],
                        "subreddit": post["subreddit"],
                        "sentiment": sentiment["label"]
                    })
            
            avg_score = sum(sentiments) / len(sentiments) if sentiments else 0
            
            return {
                "source": "reddit",
                "available": True,
                "score": round(avg_score, 2),
                "posts_analyzed": len(all_posts),
                "sample_posts": sample_posts,
                "label": "BULLISH" if avg_score > 0.1 else "BEARISH" if avg_score < -0.1 else "NEUTRAL"
            }
            
        except Exception as e:
            self.log(f"Reddit API error: {e}", level="warning")
            return {
                "source": "reddit",
                "available": False,
                "score": 0,
                "error": str(e)
            }
    
    # ==================== STOCKTWITS ====================
    
    async def get_stocktwits_sentiment(self, symbol: str = "EURUSD") -> dict[str, Any]:
        """
        Busca sentimento do StockTwits.
        
        API gratuita com limite de 200 req/hora.
        
        Args:
            symbol: Símbolo para buscar (EURUSD, EUR.X, USD.X)
        
        Returns:
            Dict com sentimento do StockTwits
        """
        try:
            symbols_to_try = [symbol, "EUR.X", "USD.X", "DXY.X"]
            all_messages = []
            
            async with httpx.AsyncClient(timeout=10) as client:
                for sym in symbols_to_try:
                    try:
                        response = await client.get(
                            f"https://api.stocktwits.com/api/2/streams/symbol/{sym}.json"
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            messages = data.get("messages", [])
                            
                            for msg in messages:
                                all_messages.append({
                                    "text": msg.get("body", ""),
                                    "sentiment": msg.get("entities", {}).get("sentiment", {}).get("basic"),
                                    "symbol": sym
                                })
                    except Exception:
                        continue
                    
                    await asyncio.sleep(0.3)
            
            if not all_messages:
                return {
                    "source": "stocktwits",
                    "available": True,
                    "score": 0,
                    "posts_analyzed": 0
                }
            
            # StockTwits já fornece sentimento em alguns posts
            bullish = 0
            bearish = 0
            neutral = 0
            
            for msg in all_messages:
                st_sentiment = msg.get("sentiment")
                if st_sentiment == "Bullish":
                    bullish += 1
                elif st_sentiment == "Bearish":
                    bearish += 1
                else:
                    # Analisa texto se não houver sentimento marcado
                    text_sentiment = self._analyze_text_sentiment(msg["text"])
                    if text_sentiment["score"] > 0.1:
                        bullish += 1
                    elif text_sentiment["score"] < -0.1:
                        bearish += 1
                    else:
                        neutral += 1
            
            total = bullish + bearish + neutral
            score = (bullish - bearish) / total if total > 0 else 0
            
            return {
                "source": "stocktwits",
                "available": True,
                "score": round(score, 2),
                "posts_analyzed": len(all_messages),
                "breakdown": {
                    "bullish": bullish,
                    "bearish": bearish,
                    "neutral": neutral
                },
                "label": "BULLISH" if score > 0.1 else "BEARISH" if score < -0.1 else "NEUTRAL"
            }
            
        except Exception as e:
            self.log(f"StockTwits API error: {e}", level="warning")
            return {
                "source": "stocktwits",
                "available": False,
                "score": 0,
                "error": str(e)
            }
    
    # ==================== AGREGADOR ====================
    
    async def get_aggregated_sentiment(self) -> dict[str, Any]:
        """
        Agrega sentimento de todas as fontes disponíveis.
        
        Usa pesos configurados para cada fonte:
        - Twitter: 40% (se disponível)
        - Reddit: 30%
        - StockTwits: 20%
        - News: 10% (via Finnhub, já integrado)
        
        Returns:
            Dict com sentimento agregado e breakdown por fonte
        """
        cache_key = "aggregated_sentiment"
        
        # Verifica cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            cache_age = (datetime.now() - cached["timestamp"]).total_seconds()
            if cache_age < self._cache_ttl:
                self.log("Using cached aggregated sentiment")
                return cached["data"]
        
        self.log("Fetching sentiment from all sources")
        
        # Busca todas as fontes em paralelo
        twitter_task = self.get_twitter_sentiment()
        reddit_task = self.get_reddit_sentiment()
        stocktwits_task = self.get_stocktwits_sentiment()
        
        twitter, reddit, stocktwits = await asyncio.gather(
            twitter_task, reddit_task, stocktwits_task,
            return_exceptions=True
        )
        
        # Trata exceções
        if isinstance(twitter, Exception):
            twitter = {"source": "twitter", "available": False, "score": 0}
        if isinstance(reddit, Exception):
            reddit = {"source": "reddit", "available": False, "score": 0}
        if isinstance(stocktwits, Exception):
            stocktwits = {"source": "stocktwits", "available": False, "score": 0}
        
        sources = [twitter, reddit, stocktwits]
        
        # Calcula score ponderado
        weighted_sum = 0
        total_weight = 0
        available_sources = []
        
        for source in sources:
            source_name = source.get("source", "unknown")
            weight = self.SOURCE_WEIGHTS.get(source_name, 0.1)
            
            if source.get("available", False):
                weighted_sum += source.get("score", 0) * weight
                total_weight += weight
                available_sources.append(source_name)
        
        final_score = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Determina label
        if final_score > 0.15:
            label = "BULLISH"
        elif final_score < -0.15:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        
        # Conta posts totais
        total_posts = sum(
            s.get("posts_analyzed", 0) 
            for s in sources 
            if s.get("available", False)
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "aggregated_score": round(final_score, 2),
            "label": label,
            "total_posts_analyzed": total_posts,
            "sources_available": available_sources,
            "sources_breakdown": {
                "twitter": twitter,
                "reddit": reddit,
                "stocktwits": stocktwits
            },
            "weights_used": self.SOURCE_WEIGHTS,
            "confidence": min(90, 30 + (total_posts * 2))  # Mais posts = mais confiança
        }
        
        # Cache
        self._cache[cache_key] = {
            "timestamp": datetime.now(),
            "data": result
        }
        
        self.log("Aggregated sentiment calculated", {
            "score": result["aggregated_score"],
            "label": result["label"],
            "sources": result["sources_available"],
            "posts": result["total_posts_analyzed"]
        })
        
        return result


# Singleton
social_sentiment = SocialSentimentClient()
