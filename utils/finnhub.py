"""
3V Engine - Finnhub Client
===========================
Cliente assíncrono para API da Finnhub.
Fornece análise de sentimento de notícias e calendário econômico.
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

from core.config import settings
from utils.logger import log_agent_action


class FinnhubClient:
    """
    Cliente para consumo da API Finnhub.
    - Calcula score de sentimento para o @Sentiment_Pulse.
    - Fornece calendário econômico para o @Macro_Watcher.
    """
    
    def __init__(self) -> None:
        self._base_url = settings.finnhub_base_url
        self._api_key = settings.finnhub_api_key
    
    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> Any:
        """Executa requisição à API."""
        params = params or {}
        params["token"] = self._api_key
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/{endpoint}",
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def get_forex_news(
        self,
        category: str = "forex",
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Obtém notícias de Forex.
        
        Args:
            category: Categoria (forex, crypto, general)
            limit: Número máximo de notícias
        
        Returns:
            Lista de notícias com headline, summary, datetime
        """
        log_agent_action("@Finnhub", "Fetching forex news", {"limit": limit})
        
        data = await self._request("news", {"category": category})
        
        # Filtra notícias das últimas 24 horas
        cutoff = datetime.now() - timedelta(hours=24)
        recent_news = []
        
        for article in data[:limit]:
            article_time = datetime.fromtimestamp(article.get("datetime", 0))
            if article_time >= cutoff:
                recent_news.append({
                    "headline": article.get("headline", ""),
                    "summary": article.get("summary", ""),
                    "source": article.get("source", ""),
                    "datetime": article_time.isoformat(),
                    "url": article.get("url", "")
                })
        
        return recent_news[:limit]
    
    async def get_news_sentiment(
        self,
        symbol: str = "EUR"
    ) -> dict[str, Any]:
        """
        Obtém sentimento agregado de notícias para uma moeda.
        
        Args:
            symbol: Símbolo da moeda (EUR, USD, etc)
        
        Returns:
            Dict com sentiment score, articles count, e breakdown
        """
        log_agent_action("@Finnhub", "Calculating news sentiment", {"symbol": symbol})
        
        # Obtém notícias
        news = await self.get_forex_news(limit=20)
        
        if not news:
            return {
                "score": 0.0,
                "label": "NEUTRAL",
                "articles_analyzed": 0,
                "message": "No recent news available"
            }
        
        # Keywords para análise de sentimento básica
        bullish_words = [
            "surge", "rally", "gains", "bullish", "rise", "climb",
            "strong", "positive", "growth", "optimistic", "buy",
            "breakthrough", "high", "soar", "up", "advance", "boost"
        ]
        
        bearish_words = [
            "drop", "fall", "decline", "bearish", "weak", "loss",
            "negative", "pessimistic", "sell", "crash", "low",
            "tumble", "down", "plunge", "slump", "risk", "fear"
        ]
        
        # Filtrar notícias relevantes para EUR ou USD
        relevant_keywords = ["EUR", "USD", "Euro", "Dollar", "ECB", "Fed", "forex"]
        
        bullish_count = 0
        bearish_count = 0
        relevant_articles = []
        
        for article in news:
            text = f"{article['headline']} {article['summary']}".lower()
            headline_upper = article['headline']
            
            # Checa relevância
            is_relevant = any(kw in headline_upper for kw in relevant_keywords)
            if not is_relevant:
                continue
            
            relevant_articles.append(article)
            
            # Conta palavras bullish e bearish
            for word in bullish_words:
                if word in text:
                    bullish_count += 1
            
            for word in bearish_words:
                if word in text:
                    bearish_count += 1
        
        # Calcula score de -1 a +1
        total = bullish_count + bearish_count
        if total == 0:
            score = 0.0
        else:
            score = (bullish_count - bearish_count) / total
        
        # Determina label
        if score >= 0.3:
            label = "BULLISH"
        elif score <= -0.3:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        
        return {
            "score": round(score, 2),
            "label": label,
            "articles_analyzed": len(relevant_articles),
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "recent_headlines": [a["headline"] for a in relevant_articles[:5]],
            "timestamp": datetime.now().isoformat()
        }
    
    # ==========================================
    # CALENDÁRIO ECONÔMICO (para @Macro_Watcher)
    # ==========================================
    
    async def get_economic_calendar(
        self,
        days_ahead: int = 1
    ) -> list[dict[str, Any]]:
        """
        Obtém eventos do calendário econômico.
        
        Args:
            days_ahead: Dias à frente para buscar (padrão: 1)
        
        Returns:
            Lista de eventos econômicos
        """
        log_agent_action("@Finnhub", "Fetching economic calendar")
        
        today = datetime.now()
        from_date = today.strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        data = await self._request("calendar/economic", {
            "from": from_date,
            "to": to_date
        })
        
        # Finnhub retorna { "economicCalendar": [...] }
        events = data.get("economicCalendar", [])
        return events if isinstance(events, list) else []
    
    async def get_upcoming_high_impact_events(
        self,
        minutes_window: int = 60
    ) -> dict[str, Any]:
        """
        Verifica eventos de alto impacto nos próximos X minutos.
        Usado pelo @Macro_Watcher para alertas de volatilidade.
        
        Args:
            minutes_window: Janela de tempo em minutos (padrão: 60)
        
        Returns:
            Dict com análise de risco e eventos próximos
        """
        log_agent_action(
            "@Finnhub",
            "Checking high impact events",
            {"window_minutes": minutes_window}
        )
        
        # Obtém calendário
        events = await self.get_economic_calendar()
        
        # Países relevantes para EUR/USD
        relevant_countries = ["US", "EU", "United States", "Euro Area", "Eurozone", "EMU"]
        
        # Filtrar eventos das próximas X horas
        now = datetime.now()
        cutoff = now + timedelta(minutes=minutes_window)
        
        upcoming_events = []
        high_impact_count = 0
        
        for event in events:
            # Parse datetime do evento
            event_time_str = event.get("time", "")
            event_date = event.get("date", datetime.now().strftime("%Y-%m-%d"))
            
            try:
                if event_time_str:
                    # Formato típico: "14:30:00" ou "14:30"
                    time_parts = event_time_str.split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    event_dt = datetime.strptime(event_date, "%Y-%m-%d").replace(
                        hour=hour, minute=minute
                    )
                else:
                    # Se não tem hora, assume início do dia
                    event_dt = datetime.strptime(event_date, "%Y-%m-%d")
            except (ValueError, IndexError):
                continue
            
            # Checa se está na janela de tempo
            if not (now <= event_dt <= cutoff):
                continue
            
            # Checa relevância (país)
            country = event.get("country", "")
            if not any(c.lower() in country.lower() for c in relevant_countries):
                continue
            
            # Determina impacto (Finnhub usa "impact": "high", "medium", "low")
            impact = event.get("impact", "").lower()
            event_name = event.get("event", "").lower()
            
            # Eventos críticos por nome
            critical_keywords = [
                "interest rate", "rate decision", "fomc", "ecb", 
                "nfp", "non-farm", "payroll", "cpi", "inflation",
                "gdp", "unemployment", "retail sales"
            ]
            
            is_high_impact = (
                impact == "high" or
                any(kw in event_name for kw in critical_keywords)
            )
            
            if is_high_impact:
                high_impact_count += 1
            
            upcoming_events.append({
                "event": event.get("event", "Unknown"),
                "country": country,
                "datetime": event_dt.isoformat(),
                "minutes_until": int((event_dt - now).total_seconds() / 60),
                "impact": "HIGH" if is_high_impact else "MEDIUM",
                "previous": event.get("prev"),
                "forecast": event.get("estimate"),
                "actual": event.get("actual"),
                "unit": event.get("unit", "")
            })
        
        # Determina alerta de volatilidade
        if high_impact_count >= 2:
            alert = "EXTREME_RISK"
            message = f"⚠️ {high_impact_count} eventos de alto impacto nos próximos {minutes_window} minutos!"
        elif high_impact_count == 1:
            alert = "HIGH_RISK"
            message = f"⚡ 1 evento de alto impacto nos próximos {minutes_window} minutos"
        elif len(upcoming_events) > 0:
            alert = "MODERATE_RISK"
            message = f"📊 {len(upcoming_events)} eventos nos próximos {minutes_window} minutos"
        else:
            alert = "LOW_RISK"
            message = "✅ Calendário limpo - sem eventos de impacto próximos"
        
        return {
            "alert": alert,
            "message": message,
            "high_impact_events": high_impact_count,
            "total_events": len(upcoming_events),
            "window_minutes": minutes_window,
            "events": sorted(upcoming_events, key=lambda x: x["minutes_until"]),
            "timestamp": now.isoformat()
        }
    
    async def test_connection(self) -> bool:
        """Testa conexão com a API."""
        try:
            news = await self.get_forex_news(limit=1)
            print(f"✅ Finnhub Connection OK - {len(news)} news articles available")
            return True
        except Exception as e:
            print(f"❌ Finnhub Connection FAILED: {e}")
            return False
    
    async def test_calendar_connection(self) -> bool:
        """Testa conexão com o calendário econômico."""
        try:
            events = await self.get_economic_calendar(days_ahead=1)
            print(f"✅ Finnhub Calendar OK - {len(events)} events found")
            return True
        except Exception as e:
            print(f"❌ Finnhub Calendar FAILED: {e}")
            return False


# Singleton
finnhub_client = FinnhubClient()
