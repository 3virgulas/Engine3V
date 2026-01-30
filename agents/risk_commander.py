"""
3V Engine - Risk Commander Agent
=================================
@Risk_Commander: Decisor final do sistema.
Implementa "Veredito de Ouro" institucional com scoring de confiança.
"""

from datetime import datetime
from typing import Any, Literal

from agents.base import BaseAgent


# Type aliases para clareza
Decision = Literal["BUY", "SELL", "HOLD", "VETO"]
TechnicalSignal = Literal["BULLISH", "BEARISH", "NEUTRAL"]


class RiskCommanderAgent(BaseAgent):
    """
    @Risk_Commander - Comandante de Risco e Decisor Final
    
    Implementa o "Veredito de Ouro" institucional:
    
    1. LÓGICA DE DIREÇÃO:
       - BUY (Long): Technical BULLISH + Sentiment > 0.3
       - SELL (Short): Technical BEARISH + Sentiment < -0.3
       - HOLD: Caso contrário
    
    2. VETO MACRO (Crítico):
       - Se @Macro_Watcher retornar HIGH_RISK ou EXTREME_RISK
       - Decisão final DEVE ser HOLD com justificativa de veto
    
    3. CÁLCULO DE CONFIANÇA:
       - Convergência total: 85%+
       - Indicador neutro: < 60%
       
    Filosofia: Conservador e lucrativo.
    """
    
    # Thresholds institucionais
    SENTIMENT_BULLISH_THRESHOLD = 0.3
    SENTIMENT_BEARISH_THRESHOLD = -0.3
    CONFIDENCE_FULL_CONVERGENCE = 85
    CONFIDENCE_PARTIAL = 60
    CONFIDENCE_LOW = 40
    
    @property
    def name(self) -> str:
        return "@Risk_Commander"
    
    @property
    def role(self) -> str:
        return """Comandante de Risco - Decisor Final do sistema 3V Engine.
        
Você recebe análises de:
1. @Quant_Analyst - Sinal técnico (BULLISH/BEARISH/NEUTRAL)
2. @Sentiment_Pulse - Score de sentimento (-1 a +1)
3. @Macro_Watcher - Alerta de volatilidade (LOW/MODERATE/HIGH/EXTREME)

Regras de decisão (Veredito de Ouro):
- BUY: Técnico BULLISH + Sentimento > 0.3 + Macro não HIGH/EXTREME
- SELL: Técnico BEARISH + Sentimento < -0.3 + Macro não HIGH/EXTREME
- HOLD: Sinais conflitantes OU macro HIGH_RISK
- VETO: Macro EXTREME_RISK (nunca operar)

Seu veredito é FINAL. Seja conservador e proteja o capital."""
    
    def _calculate_confidence(
        self,
        technical: TechnicalSignal,
        sentiment: float,
        macro: str,
        decision: Decision
    ) -> int:
        """
        Calcula score de confiança do veredito.
        
        Regras:
        - Convergência total (tech + sentiment alinhados): 85%+
        - Sinal técnico claro + sentimento neutro: 70%
        - Indicador técnico neutro: < 60%
        - Veto macro: 100% (certeza do veto)
        """
        if decision == "VETO":
            return 100  # Certeza absoluta do veto
        
        if decision == "HOLD" and macro in ["HIGH_RISK", "EXTREME_RISK"]:
            return 95  # Alta confiança no hold por macro
        
        # Verificação de convergência
        tech_aligned = technical in ["BULLISH", "BEARISH"]
        sentiment_aligned = abs(sentiment) > 0.3
        sentiment_neutral = abs(sentiment) <= 0.3
        
        # Convergência total (tech + sentiment alinhados)
        if tech_aligned and sentiment_aligned and macro == "LOW_RISK":
            base_confidence = self.CONFIDENCE_FULL_CONVERGENCE
            # Bônus por sentimento forte
            sentiment_bonus = min(int(abs(sentiment) * 10), 10)
            return min(base_confidence + sentiment_bonus, 95)
        
        # Convergência parcial (macro moderado)
        if tech_aligned and sentiment_aligned and macro == "MODERATE_RISK":
            return 75
        
        # NOVO: Sinal técnico claro + sentimento neutro = 70%
        if tech_aligned and sentiment_neutral and macro in ["LOW_RISK", "MODERATE_RISK"]:
            return 70
        
        # Técnico neutro = baixa confiança
        if technical == "NEUTRAL":
            return self.CONFIDENCE_LOW
        
        # Parcialmente alinhado
        return self.CONFIDENCE_PARTIAL
    
    def _build_reasoning(
        self,
        decision: Decision,
        direction: str | None,
        technical: TechnicalSignal,
        sentiment: float,
        macro: str,
        confidence: int
    ) -> str:
        """
        Constrói justificativa detalhada para o veredito.
        Formato institucional para auditoria.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if decision == "VETO":
            return (
                f"[{timestamp}] VETO MACRO: Volatilidade extrema detectada. "
                f"Alert={macro}. Operações suspensas até normalização do calendário econômico."
            )
        
        if decision == "HOLD" and macro in ["HIGH_RISK", "EXTREME_RISK"]:
            return (
                f"[{timestamp}] VETO MACRO: Alta volatilidade esperada. "
                f"Alert={macro}. Aguardando janela de menor risco para entrada. "
                f"Tech={technical}, Sentiment={sentiment:.2f}."
            )
        
        if decision == "HOLD":
            # Analisar motivo do hold
            reasons = []
            if technical == "NEUTRAL":
                reasons.append("sinal técnico neutro")
            if abs(sentiment) < 0.3:
                reasons.append(f"sentimento fraco ({sentiment:.2f})")
            if technical == "BULLISH" and sentiment < 0:
                reasons.append("divergência técnico/sentimento")
            if technical == "BEARISH" and sentiment > 0:
                reasons.append("divergência técnico/sentimento")
            
            reason_text = ", ".join(reasons) if reasons else "sinais mistos"
            return (
                f"[{timestamp}] HOLD: Sem convergência clara. Motivo: {reason_text}. "
                f"Tech={technical}, Sentiment={sentiment:.2f}, Macro={macro}. "
                f"Aguardando condições favoráveis."
            )
        
        # BUY ou SELL
        direction_pt = "compra (Long)" if direction == "LONG" else "venda (Short)"
        return (
            f"[{timestamp}] {decision}: Entrada validada por convergência. "
            f"Direção: {direction_pt}. "
            f"Tech={technical} (confirmado), Sentiment={sentiment:.2f} "
            f"({'positivo forte' if sentiment > 0.3 else 'negativo forte'}), "
            f"Macro={macro} (sem riscos próximos). "
            f"Confiança: {confidence}%."
        )
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Toma decisão final baseada nos sinais agregados.
        Implementa o Veredito de Ouro institucional.
        
        Args:
            market_state: Estado do mercado com análises dos outros agentes
        
        Returns:
            Decisão final com justificativa para Supabase
        """
        self.log("Aggregating signals for Golden Verdict")
        
        # ============== EXTRAÇÃO DE SINAIS ==============
        quant = market_state.get("quant_analysis", {})
        sentiment = market_state.get("sentiment_analysis", {})
        macro = market_state.get("macro_analysis", {})
        
        # Sinais brutos
        technical_raw = quant.get("llm_analysis", {})
        technical_signal: TechnicalSignal = technical_raw.get("signal", "NEUTRAL")
        
        sentiment_data = sentiment.get("raw_data", {})
        sentiment_score: float = sentiment_data.get("score", 0.0)
        
        macro_alert: str = macro.get("alert", "LOW_RISK")
        
        self.log("Signals extracted", {
            "technical": technical_signal,
            "sentiment": sentiment_score,
            "macro": macro_alert
        })
        
        # ============== VEREDITO DE OURO ==============
        
        decision: Decision
        direction: str | None = None
        
        # 1. VETO MACRO (Prioridade máxima)
        if macro_alert == "EXTREME_RISK":
            decision = "VETO"
            direction = None
        
        # 2. HOLD por HIGH_RISK (Veto de precaução)
        elif macro_alert == "HIGH_RISK":
            decision = "HOLD"
            direction = None
        
        # 3. BUY: Convergência bullish
        elif (
            technical_signal == "BULLISH" and 
            sentiment_score > self.SENTIMENT_BULLISH_THRESHOLD
        ):
            decision = "BUY"
            direction = "LONG"
        
        # 4. SELL: Convergência bearish
        elif (
            technical_signal == "BEARISH" and 
            sentiment_score < self.SENTIMENT_BEARISH_THRESHOLD
        ):
            decision = "SELL"
            direction = "SHORT"
        
        # 5. HOLD: Sem convergência
        else:
            decision = "HOLD"
            direction = None
        
        # ============== CÁLCULO DE CONFIANÇA ==============
        confidence = self._calculate_confidence(
            technical_signal, 
            sentiment_score, 
            macro_alert, 
            decision
        )
        
        # ============== REASONING DETALHADO ==============
        reasoning = self._build_reasoning(
            decision,
            direction,
            technical_signal,
            sentiment_score,
            macro_alert,
            confidence
        )
        
        # ============== VALIDAÇÃO LLM (Opcional) ==============
        llm_input = {
            "technical_signal": technical_signal,
            "sentiment_score": sentiment_score,
            "macro_alert": macro_alert,
            "preliminary_decision": decision,
            "preliminary_direction": direction,
            "preliminary_confidence": confidence,
            "preliminary_reasoning": reasoning
        }
        
        llm_analysis = await self.reason(llm_input)
        
        # ============== RESULTADO FINAL ==============
        result = {
            "agent": self.name,
            "decision": decision,
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "llm_validation": llm_analysis,
            "timestamp": datetime.now().isoformat(),
            "inputs": {
                "technical": {
                    "signal": technical_signal,
                    "raw": quant.get("raw_data", {})
                },
                "sentiment": {
                    "score": sentiment_score,
                    "label": sentiment_data.get("label", "NEUTRAL"),
                    "articles_analyzed": sentiment_data.get("articles_analyzed", 0)
                },
                "macro": {
                    "alert": macro_alert,
                    "high_impact_events": macro.get("high_impact_events", 0),
                    "message": macro.get("message", "")
                }
            },
            # Campos para Supabase
            "supabase_record": {
                "pair": market_state.get("pair", "EUR/USD"),
                "technical_signal": {
                    "direction": technical_signal,
                    "indicators": quant.get("raw_data", {})
                },
                "sentiment_score": sentiment_score,
                "macro_alert": macro_alert,
                "final_decision": f"{decision}_{direction}" if direction else decision,
                "reasoning": reasoning
            }
        }
        
        # Log com destaque para decisões de entrada
        log_level = "warning" if decision in ["BUY", "SELL"] else "info"
        self.log("GOLDEN VERDICT", {
            "decision": decision,
            "direction": direction,
            "confidence": f"{confidence}%"
        }, level=log_level)
        
        return result


# Singleton
risk_commander = RiskCommanderAgent()
