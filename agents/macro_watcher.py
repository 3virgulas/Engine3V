"""
3V Engine - Macro Watcher Agent
================================
@Macro_Watcher: Responsável pelo monitoramento macro.
Verifica calendário econômico via Forex Factory RSS.
"""

from typing import Any

from agents.base import BaseAgent
from utils.forex_factory import forex_factory_client


class MacroWatcherAgent(BaseAgent):
    """
    @Macro_Watcher - Vigilante Macroeconômico
    
    Responsabilidades:
    - Monitorar calendário econômico via Forex Factory RSS
    - Identificar eventos de Alto Impacto (High)
    - Emitir alertas de volatilidade iminente
    - Considerar janela de 60 minutos para risco
    """
    
    @property
    def name(self) -> str:
        return "@Macro_Watcher"
    
    @property
    def role(self) -> str:
        return """Vigilante Macroeconômico especializado em eventos de impacto no Forex.
        
Você monitora:
1. Decisões de taxa de juros (Fed, BCE)
2. Non-Farm Payrolls (NFP) - EUA
3. CPI (Inflação) - EUA e Europa
4. PIB e outros indicadores de alto impacto

Alertas de volatilidade:
- EXTREME_RISK: 2+ eventos de alto impacto nos próximos 60 min
- HIGH_RISK: 1 evento de alto impacto nos próximos 60 min
- MODERATE_RISK: Eventos de médio impacto próximos
- LOW_RISK: Calendário limpo

Seu papel é PROTEGER contra volatilidade inesperada."""
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Verifica eventos econômicos de alto impacto.
        
        Args:
            market_state: Estado do mercado (contexto adicional)
        
        Returns:
            Alerta de volatilidade e eventos próximos
        """
        self.log("Checking economic calendar via Forex Factory")
        
        # Verifica eventos nos próximos 60 minutos usando Forex Factory
        calendar_data = await forex_factory_client.get_upcoming_high_impact_events(
            minutes_window=60
        )
        
        self.log("Calendar check complete", {
            "alert": calendar_data["alert"],
            "high_impact": calendar_data["high_impact_events"],
            "total_events": calendar_data["total_events"]
        })
        
        # Se houver eventos, usa LLM para análise de risco
        if calendar_data["total_events"] > 0:
            llm_input = {
                "alert_level": calendar_data["alert"],
                "upcoming_events": calendar_data["events"],
                "high_impact_count": calendar_data["high_impact_events"]
            }
            llm_analysis = await self.reason(llm_input)
        else:
            llm_analysis = {
                "signal": "NEUTRAL",
                "confidence_score": 90,
                "analysis": "No significant economic events in the next 60 minutes",
                "key_factors": ["Clear economic calendar"]
            }
        
        result = {
            "agent": self.name,
            "timestamp": calendar_data["timestamp"],
            "raw_data": calendar_data,
            "llm_analysis": llm_analysis,
            "alert": calendar_data["alert"],
            "message": calendar_data["message"],
            "high_impact_events": calendar_data["high_impact_events"],
            "should_trade": calendar_data["alert"] not in ["EXTREME_RISK", "HIGH_RISK"]
        }
        
        self.log("Analysis complete", {
            "alert": result["alert"],
            "should_trade": result["should_trade"]
        })
        
        return result


# Singleton
macro_watcher = MacroWatcherAgent()
