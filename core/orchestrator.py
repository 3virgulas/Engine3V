"""
3V Engine - Orchestrator
=========================
LangGraph state machine para orquestração dos agentes.
Gerencia fluxo de análise e comunicação entre agentes.
"""

import asyncio
from datetime import datetime
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from agents.quant_analyst import quant_analyst
from agents.sentiment_pulse import sentiment_pulse
from agents.macro_watcher import macro_watcher
from agents.risk_commander import risk_commander
from core.supabase_client import supabase_client
from utils.logger import logger, log_trade_signal
from utils.telegram_bot import telegram_bot


class MarketState(TypedDict):
    """Estado compartilhado entre os agentes."""
    pair: str
    timestamp: str
    quant_analysis: dict[str, Any]
    sentiment_analysis: dict[str, Any]
    macro_analysis: dict[str, Any]
    final_decision: dict[str, Any]
    errors: list[str]


async def analyze_technical(state: MarketState) -> MarketState:
    """Node: Análise técnica pelo @Quant_Analyst."""
    try:
        result = await quant_analyst.analyze(state)
        state["quant_analysis"] = result
    except Exception as e:
        logger.error(f"@Quant_Analyst error: {e}")
        state["errors"].append(f"Quant: {str(e)}")
        state["quant_analysis"] = {"signal": "NEUTRAL", "confidence": 0, "error": str(e)}
    return state


async def analyze_sentiment(state: MarketState) -> MarketState:
    """Node: Análise de sentimento pelo @Sentiment_Pulse."""
    try:
        result = await sentiment_pulse.analyze(state)
        state["sentiment_analysis"] = result
    except Exception as e:
        logger.error(f"@Sentiment_Pulse error: {e}")
        state["errors"].append(f"Sentiment: {str(e)}")
        state["sentiment_analysis"] = {"sentiment_score": 0, "signal": "NEUTRAL", "error": str(e)}
    return state


async def analyze_macro(state: MarketState) -> MarketState:
    """Node: Análise macro pelo @Macro_Watcher."""
    try:
        result = await macro_watcher.analyze(state)
        state["macro_analysis"] = result
    except Exception as e:
        logger.error(f"@Macro_Watcher error: {e}")
        state["errors"].append(f"Macro: {str(e)}")
        state["macro_analysis"] = {"alert": "LOW_RISK", "should_trade": True, "error": str(e)}
    return state


async def make_decision(state: MarketState) -> MarketState:
    """Node: Decisão final pelo @Risk_Commander."""
    try:
        result = await risk_commander.analyze(state)
        state["final_decision"] = result
        
        decision = result.get("decision", "HOLD")
        confidence = result.get("confidence", 0)
        reasoning = result.get("reasoning", "")
        
        # Log do sinal de trade
        log_trade_signal(
            signal=decision,
            confidence=confidence,
            reasoning=reasoning
        )
        
        # Notificação Telegram (apenas BUY, SELL, VETO)
        await telegram_bot.notify_trade_signal(
            decision=decision,
            direction=result.get("direction"),
            confidence=confidence,
            reasoning=reasoning,
            pair=state["pair"],
            inputs=result.get("inputs")
        )
        
    except Exception as e:
        logger.error(f"@Risk_Commander error: {e}")
        state["errors"].append(f"RiskCommander: {str(e)}")
        state["final_decision"] = {"decision": "HOLD", "error": str(e)}
    return state


async def save_to_database(state: MarketState) -> MarketState:
    """Node: Salva decisão no Supabase para audit trail."""
    try:
        final_decision = state.get("final_decision", {})
        supabase_record = final_decision.get("supabase_record", {})
        
        # Usa o registro estruturado do Risk Commander quando disponível
        if supabase_record:
            await supabase_client.log_decision(
                pair=supabase_record.get("pair", state["pair"]),
                technical_signal=supabase_record.get("technical_signal", {}),
                sentiment_score=supabase_record.get("sentiment_score", 0),
                macro_alert=supabase_record.get("macro_alert", "UNKNOWN"),
                final_decision=supabase_record.get("final_decision", "HOLD"),
                reasoning={
                    "verdict": supabase_record.get("reasoning", ""),
                    "inputs": final_decision.get("inputs", {}),
                    "llm_validation": final_decision.get("llm_validation", {}),
                    "confidence": final_decision.get("confidence", 0),
                    "errors": state["errors"]
                }
            )
        else:
            # Fallback para formato antigo
            await supabase_client.log_decision(
                pair=state["pair"],
                technical_signal=state["quant_analysis"],
                sentiment_score=state["sentiment_analysis"].get("sentiment_score", 0),
                macro_alert=state["macro_analysis"].get("alert", "UNKNOWN"),
                final_decision=final_decision.get("decision", "HOLD"),
                reasoning={
                    "quant": state["quant_analysis"].get("llm_analysis", {}),
                    "sentiment": state["sentiment_analysis"].get("llm_analysis", {}),
                    "macro": state["macro_analysis"].get("llm_analysis", {}),
                    "commander": final_decision.get("llm_validation", {}),
                    "errors": state["errors"]
                }
            )
        
        logger.info("Decision saved to Supabase audit trail")
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")
        state["errors"].append(f"Database: {str(e)}")
    return state


def create_orchestrator() -> StateGraph:
    """
    Cria o grafo de orquestração dos agentes.
    
    Fluxo:
    1. Análises paralelas: Quant + Sentiment + Macro
    2. Decisão final: Risk Commander
    3. Persistência: Supabase
    
    Returns:
        StateGraph compilado
    """
    # Define o grafo
    workflow = StateGraph(MarketState)
    
    # Adiciona nodes
    workflow.add_node("technical", analyze_technical)
    workflow.add_node("sentiment", analyze_sentiment)
    workflow.add_node("macro", analyze_macro)
    workflow.add_node("decision", make_decision)
    workflow.add_node("persist", save_to_database)
    
    # Define o fluxo
    # Start -> Parallel analyses
    workflow.set_entry_point("technical")
    
    # Technical -> Sentiment -> Macro (sequencial para demo)
    # Em produção, pode ser paralelo com asyncio.gather
    workflow.add_edge("technical", "sentiment")
    workflow.add_edge("sentiment", "macro")
    
    # Macro -> Decision
    workflow.add_edge("macro", "decision")
    
    # Decision -> Persist -> End
    workflow.add_edge("decision", "persist")
    workflow.add_edge("persist", END)
    
    return workflow.compile()


class Orchestrator:
    """
    Orquestrador principal do 3V Engine.
    Gerencia o ciclo de análise e decisão.
    """
    
    def __init__(self, pair: str = "EUR/USD") -> None:
        self.pair = pair
        self.graph = create_orchestrator()
        self._running = False
    
    def create_initial_state(self) -> MarketState:
        """Cria estado inicial para uma rodada de análise."""
        return MarketState(
            pair=self.pair,
            timestamp=datetime.now().isoformat(),
            quant_analysis={},
            sentiment_analysis={},
            macro_analysis={},
            final_decision={},
            errors=[]
        )
    
    async def run_analysis(self) -> MarketState:
        """
        Executa uma rodada completa de análise.
        
        Returns:
            Estado final com todas as análises e decisão
        """
        logger.info(f"🔄 Starting analysis cycle for {self.pair}")
        
        initial_state = self.create_initial_state()
        final_state = await self.graph.ainvoke(initial_state)
        
        decision = final_state.get("final_decision", {})
        logger.info(
            f"✅ Analysis complete: {decision.get('decision', 'UNKNOWN')} "
            f"(Confidence: {decision.get('confidence', 0)}%)"
        )
        
        return final_state
    
    async def start_monitoring_loop(self, interval_minutes: int = 5) -> None:
        """
        Inicia loop de monitoramento contínuo.
        
        Args:
            interval_minutes: Intervalo entre análises
        """
        self._running = True
        logger.info(f"🚀 3V Engine started - Monitoring {self.pair} every {interval_minutes} minutes")
        
        while self._running:
            try:
                await self.run_analysis()
            except Exception as e:
                logger.error(f"Analysis cycle failed: {e}")
            
            if self._running:
                logger.info(f"💤 Waiting {interval_minutes} minutes until next analysis...")
                await asyncio.sleep(interval_minutes * 60)
    
    def stop(self) -> None:
        """Para o loop de monitoramento."""
        self._running = False
        logger.info("🛑 3V Engine stopping...")


# Factory function
def get_orchestrator(pair: str = "EUR/USD") -> Orchestrator:
    """Retorna instância do orquestrador."""
    return Orchestrator(pair=pair)
