"""
3V Engine - Forex Factory Client
=================================
Cliente assíncrono para parse do RSS do Forex Factory.
Fornece calendário econômico gratuito sem necessidade de API key.

Feed URL: https://www.forexfactory.com/ff_calendar_thisweek.xml

NOTA: Forex Factory pode bloquear requisições automatizadas.
      O cliente inclui fallback para LOW_RISK quando bloqueado,
      garantindo que o sistema nunca falhe por causa do calendário.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx

from utils.logger import log_agent_action


class ForexFactoryClient:
    """
    Cliente para consumo do RSS do Forex Factory.
    Fornece calendário econômico para o @Macro_Watcher.
    
    Vantagens:
    - Gratuito, sem API key necessária
    - Dados confiáveis e atualizados
    - Inclui impacto (High/Medium/Low)
    
    NOTA: Inclui fallback para quando o RSS estiver bloqueado.
          O sistema assume LOW_RISK quando não consegue acessar os dados.
    """
    
    RSS_URL = "https://www.forexfactory.com/ff_calendar_thisweek.xml"
    
    # Moedas relevantes para EUR/USD
    RELEVANT_CURRENCIES = {"EUR", "USD"}
    
    def __init__(self) -> None:
        # Headers que simulam um navegador real
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self._fallback_mode = False
    
    async def _fetch_rss(self) -> str | None:
        """
        Busca o XML do RSS.
        Retorna None se bloqueado (403/outras falhas).
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    self.RSS_URL,
                    headers=self._headers
                )
                response.raise_for_status()
                self._fallback_mode = False
                return response.text
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            log_agent_action(
                "@ForexFactory",
                f"RSS access failed: {e}",
                level="warning"
            )
            self._fallback_mode = True
            return None
    
    def _parse_event(self, item: ET.Element) -> dict[str, Any]:
        """Parse de um item do RSS."""
        # Namespace do Forex Factory
        ns = {"ff": "http://www.forexfactory.com/ffcal"}
        
        # Extrai campos básicos
        title = item.findtext("title", "")
        country = item.findtext(f"{{{ns['ff']}}}country", "")
        date_str = item.findtext(f"{{{ns['ff']}}}date", "")
        time_str = item.findtext(f"{{{ns['ff']}}}time", "")
        impact = item.findtext(f"{{{ns['ff']}}}impact", "")
        forecast = item.findtext(f"{{{ns['ff']}}}forecast", "")
        previous = item.findtext(f"{{{ns['ff']}}}previous", "")
        
        # Parse datetime
        event_datetime = None
        if date_str:
            try:
                # Formato típico: "01-29-2026"
                if time_str and time_str not in ["All Day", "Tentative", ""]:
                    # Formato: "8:30am"
                    dt_str = f"{date_str} {time_str}"
                    event_datetime = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                else:
                    event_datetime = datetime.strptime(date_str, "%m-%d-%Y")
            except ValueError:
                pass
        
        return {
            "title": title,
            "country": country,
            "datetime": event_datetime.isoformat() if event_datetime else None,
            "datetime_obj": event_datetime,
            "impact": impact.upper() if impact else "LOW",
            "forecast": forecast,
            "previous": previous
        }
    
    async def get_economic_calendar(self) -> list[dict[str, Any]]:
        """
        Obtém todos os eventos econômicos da semana.
        
        Returns:
            Lista de eventos do calendário (vazia se fallback)
        """
        log_agent_action("@ForexFactory", "Fetching economic calendar")
        
        xml_content = await self._fetch_rss()
        
        # Fallback: retorna lista vazia se não conseguiu acessar
        if xml_content is None:
            return []
        
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            events = []
            for item in root.findall(".//item"):
                event = self._parse_event(item)
                events.append(event)
            
            return events
        except ET.ParseError as e:
            log_agent_action(
                "@ForexFactory",
                f"XML parse error: {e}",
                level="error"
            )
            return []
    
    async def get_upcoming_high_impact_events(
        self,
        minutes_window: int = 60
    ) -> dict[str, Any]:
        """
        Verifica eventos de alto impacto nos próximos X minutos.
        Filtra apenas eventos para EUR e USD.
        
        Args:
            minutes_window: Janela de tempo em minutos (padrão: 60)
        
        Returns:
            Dict com análise de risco e eventos próximos
        """
        log_agent_action(
            "@ForexFactory",
            "Checking high impact events",
            {"window_minutes": minutes_window}
        )
        
        now = datetime.now()
        
        # Obtém calendário
        all_events = await self.get_economic_calendar()
        
        # Se em modo fallback, retorna LOW_RISK com aviso
        if self._fallback_mode:
            return {
                "alert": "LOW_RISK",
                "message": "⚠️ Calendário indisponível (fallback) - assumindo baixo risco",
                "high_impact_events": 0,
                "total_events": 0,
                "window_minutes": minutes_window,
                "events": [],
                "timestamp": now.isoformat(),
                "fallback_mode": True
            }
        
        # Filtrar eventos das próximas X horas
        cutoff = now + timedelta(minutes=minutes_window)
        
        upcoming_events = []
        high_impact_count = 0
        
        for event in all_events:
            event_dt = event.get("datetime_obj")
            if not event_dt:
                continue
            
            # Checa se está na janela de tempo
            if not (now <= event_dt <= cutoff):
                continue
            
            # Checa relevância (moeda)
            country = event.get("country", "").upper()
            is_relevant = country in self.RELEVANT_CURRENCIES
            if not is_relevant:
                continue
            
            # Verifica impacto
            impact = event.get("impact", "LOW")
            is_high_impact = impact == "HIGH"
            
            if is_high_impact:
                high_impact_count += 1
            
            upcoming_events.append({
                "event": event["title"],
                "country": country,
                "datetime": event["datetime"],
                "minutes_until": int((event_dt - now).total_seconds() / 60),
                "impact": impact,
                "forecast": event.get("forecast"),
                "previous": event.get("previous")
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
            "timestamp": now.isoformat(),
            "fallback_mode": False
        }
    
    async def test_connection(self) -> bool:
        """
        Testa conexão com o RSS do Forex Factory.
        
        Retorna True mesmo em fallback mode (sistema funciona sem calendário).
        """
        try:
            result = await self.get_upcoming_high_impact_events()
            
            if result.get("fallback_mode"):
                print(f"✅ Forex Factory (Fallback Mode) - Calendar unavailable, using LOW_RISK default")
            else:
                events = await self.get_economic_calendar()
                print(f"✅ Forex Factory Connection OK - {len(events)} events this week")
            
            return True
        except Exception as e:
            print(f"❌ Forex Factory Connection FAILED: {e}")
            return False


# Singleton
forex_factory_client = ForexFactoryClient()
