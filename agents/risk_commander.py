"""
3V Engine - Risk Commander Agent (LLM-FIRST ARCHITECTURE)
==========================================================
@Risk_Commander: Decisor final do sistema.
Arquitetura LLM-First: A IA tem SOBERANIA TOTAL sobre as decisões.
Zero cálculos matemáticos - 100% inteligência artificial.
"""

from datetime import datetime, timedelta
from typing import Any, Literal
import json
import re

from agents.base import BaseAgent


# Type aliases
Decision = Literal["ENTRY", "HOLD"]
Direction = Literal["BUY", "SELL"]


class RiskCommanderAgent(BaseAgent):
    """
    @Risk_Commander - CIO (Chief Investment Officer)
    
    ARQUITETURA LLM-FIRST:
    - A IA recebe TODOS os dados brutos dos agentes
    - A IA decide: decision, direction, confidence, entry/tp/sl
    - ZERO cálculos matemáticos de confiança
    - ÚNICO VETO: Black Swan (evento de alto impacto < 30 min)
    
    Filosofia: "Seja agressivo quando a probabilidade estiver a seu favor."
    """
    
    # Entry Window config (minutos)
    ENTRY_WINDOW_START_MINUTES = 3
    ENTRY_WINDOW_END_MINUTES = 5
    
    # Veto window (minutos)
    BLACK_SWAN_VETO_MINUTES = 30
    
    @property
    def name(self) -> str:
        return "@Risk_Commander"
    
    @property
    def role(self) -> str:
        return """CIO (Chief Investment Officer) e Estrategista Chefe da 3virgulas.
        
Você é uma lenda do mercado financeiro. Sua reputação foi construída sobre duas regras:
1) Nunca perca dinheiro. 
2) Seja agressivo quando a probabilidade estiver a seu favor.

Você recebe relatórios de:
- @Quant_Analyst: Análise técnica (RSI, Bandas, MAs, Suporte/Resistência)
- @Sentiment_Pulse: Análise de sentimento do mercado
- @Macro_Watcher: Calendário econômico e riscos macro

Seu veredito é FINAL e SOBERANO."""
    
    def _build_cio_prompt(self, raw_data: dict[str, Any]) -> str:
        """
        Constrói o prompt do CIO (Chief Investment Officer).
        Estilo: Wolf of Wall Street / Ray Dalio.
        """
        return f"""Você é o CIO (Chief Investment Officer) e Estrategista Chefe da 3virgulas, uma lenda do mercado financeiro conhecida por transformar dados complexos em lucros bilionários. Sua reputação foi construída sobre duas regras: 1) Nunca perca dinheiro. 2) Seja agressivo quando a probabilidade estiver a seu favor.

Sua tarefa é analisar os relatórios dos seus analistas (Quant, Sentiment, Macro) e tomar a DECISÃO FINAL DE EXECUÇÃO.

DADOS DA MESA:
{json.dumps(raw_data, indent=2, ensure_ascii=False)}

DIRETRIZES DE ELITE:
1. CONFLUÊNCIA MULTI-TIMEFRAME (CRÍTICO): Priorize sinais com confluência em múltiplos timeframes (M5/M15/H1/H4). Se 3+ timeframes concordam = alta probabilidade. Se há divergência H4 vs M5 = cautela.
2. SOBERANIA TÉCNICA: Se o gráfico (Quant) mostrar um padrão de alta probabilidade com MTF confluente, ignore ruídos de sentimento neutro.
3. CAÇADOR DE ASSIMETRIA: Só recomende entrada se o potencial de lucro for maior que o risco (min 1:1.5 RR).
4. PRECISÃO CIRÚRGICA: Defina Entry, TP e SL baseados na volatilidade e níveis técnicos fornecidos. Não chute valores.
5. SEM HESITAÇÃO: Se for HOLD, diga o porquê. Se for ENTRY, seja convicto. Confiança 65% é para amadores; busque convicção > 80%.

Retorne EXCLUSIVAMENTE este JSON (sem markdown):
{{
  "decision": "ENTRY" ou "HOLD",
  "direction": "BUY" ou "SELL",
  "confidence": 0-100,
  "entry_price": 0.00000,
  "take_profit": 0.00000,
  "stop_loss": 0.00000,
  "reasoning": "Sua tese de investimento em uma frase de impacto."
}}"""
    
    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """
        Extrai JSON da resposta do LLM.
        Robusto para lidar com markdown ou texto extra.
        """
        try:
            # Tenta parse direto
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Remove markdown code blocks se existir
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback seguro
        self.log("Failed to parse LLM JSON, using fallback", level="warning")
        return {
            "decision": "HOLD",
            "direction": None,
            "confidence": 30,
            "reasoning": "Erro ao processar resposta da IA"
        }
    
    def _check_black_swan_veto(self, macro: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Verifica se há evento de alto impacto nos próximos 30 minutos.
        ÚNICO VETO DO SISTEMA.
        
        Returns:
            (should_veto, reason)
        """
        alert = macro.get("alert", "LOW_RISK")
        high_impact = macro.get("high_impact_events", 0)
        
        # Veto apenas para EXTREME_RISK com eventos iminentes
        if alert == "EXTREME_RISK":
            return True, f"BLACK SWAN: Risco extremo detectado. {high_impact} evento(s) de alto impacto iminente(s)."
        
        # HIGH_RISK com eventos próximos também é veto
        if alert == "HIGH_RISK" and high_impact > 0:
            return True, f"VETO MACRO: {high_impact} evento(s) de alto impacto nos próximos 30 min."
        
        return False, None
    
    def _get_market_bias(self, direction: str | None) -> str:
        """
        Determina o viés do mercado baseado na direção.
        """
        if direction == "BUY":
            return "Alta"
        elif direction == "SELL":
            return "Baixa"
        return "Lateralizado"
    
    def _calculate_entry_window(self, base_timestamp: datetime | None = None) -> dict[str, Any]:
        """
        Calcula a janela de entrada recomendada (3-5 minutos após análise).
        """
        base = base_timestamp or datetime.now()
        
        start_time = base + timedelta(minutes=self.ENTRY_WINDOW_START_MINUTES)
        end_time = base + timedelta(minutes=self.ENTRY_WINDOW_END_MINUTES)
        
        return {
            "start": start_time.strftime("%H:%M"),
            "end": end_time.strftime("%H:%M"),
            "start_iso": start_time.isoformat(),
            "end_iso": end_time.isoformat(),
            "instruction": "Aguardar confirmação de volume no horário sugerido"
        }
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        DECISÃO FINAL via LLM-FIRST ARCHITECTURE.
        A IA tem SOBERANIA TOTAL sobre a decisão.
        """
        self.log("CIO analyzing market data (LLM-First Architecture)")
        
        # ============== EXTRAÇÃO DE DADOS BRUTOS ==============
        quant = market_state.get("quant_analysis", {})
        sentiment = market_state.get("sentiment_analysis", {})
        macro = market_state.get("macro_analysis", {})
        pair = market_state.get("pair", "EUR/USD")
        
        # Dados técnicos detalhados
        quant_raw = quant.get("raw_data", {})
        quant_llm = quant.get("llm_analysis", {})
        
        # Dados de sentimento
        sentiment_raw = sentiment.get("raw_data", {})
        
        # ============== CHECK BLACK SWAN VETO ==============
        should_veto, veto_reason = self._check_black_swan_veto(macro)
        
        if should_veto:
            self.log("BLACK SWAN VETO TRIGGERED", {"reason": veto_reason}, level="warning")
            
            return self._build_veto_result(
                pair=pair,
                reason=veto_reason,
                macro=macro,
                quant=quant,
                sentiment_raw=sentiment_raw
            )
        
        # ============== MONTAR DADOS PARA O CIO ==============
        raw_data = {
            "pair": pair,
            "quant_analyst": {
                "signal": quant.get("signal", "NEUTRAL"),
                "trend": quant_raw.get("trend", "NEUTRAL"),
                "trend_score": quant_raw.get("trend_score", 0),
                "rsi": quant_raw.get("rsi", 50),
                "price": quant_raw.get("price", 0),
                "bollinger_bands": {
                    "upper": quant_raw.get("bb_upper", 0),
                    "middle": quant_raw.get("bb_middle", 0),
                    "lower": quant_raw.get("bb_lower", 0),
                    "position": quant_raw.get("bb_position", "middle")
                },
                "moving_averages": quant_raw.get("ma_signals", []),
                "llm_reasoning": quant_llm.get("reasoning", ""),
                "deterministic_reasons": quant.get("deterministic_reasons", [])
            },
            # MULTI-TIMEFRAME ANALYSIS (NEW!)
            "multi_timeframe": {
                "confluence_direction": quant_raw.get("mtf_confluence_direction", "NEUTRAL"),
                "confluence_score": quant_raw.get("mtf_confluence_score", 0),
                "confluence_message": quant_raw.get("mtf_confluence_message", ""),
                "signals": quant_raw.get("mtf_signals", []),
                "divergence_warning": quant_raw.get("mtf_divergence", False),
                "timeframes": {
                    tf: {
                        "signal": data.get("signal"),
                        "strength": data.get("strength"),
                        "rsi": data.get("rsi")
                    }
                    for tf, data in quant_raw.get("mtf_timeframes", {}).items()
                    if isinstance(data, dict)
                }
            },
            "sentiment_pulse": {
                "score": sentiment_raw.get("score", 0),
                "label": sentiment_raw.get("label", "NEUTRAL"),
                "articles_analyzed": sentiment_raw.get("articles_analyzed", 0),
                "headlines": sentiment_raw.get("headlines", [])[:5]  # Top 5 headlines
            },
            "macro_watcher": {
                "alert": macro.get("alert", "LOW_RISK"),
                "high_impact_events": macro.get("high_impact_events", 0),
                "message": macro.get("message", ""),
                "should_trade": macro.get("should_trade", True)
            }
        }
        
        # ============== CHAMADA LLM (CIO DECIDE) ==============
        self.log("Invoking CIO for final decision")
        
        cio_prompt = self._build_cio_prompt(raw_data)
        
        # Usar chat() diretamente para prompt customizado
        try:
            response = await self._llm.chat(
                system_prompt=cio_prompt,
                user_message="Analise e tome sua decisão. Retorne APENAS o JSON.",
                temperature=0.3  # Levemente criativo para reasoning
            )
            raw_response = response.content
        except Exception as e:
            self.log(f"LLM call failed: {e}", level="error")
            raw_response = '{"decision": "HOLD", "direction": null, "confidence": 30, "reasoning": "Erro na chamada LLM"}'
        
        # Parse da resposta
        cio_decision = self._parse_llm_response(raw_response)
        cio_decision["raw_response"] = raw_response
        
        # ============== EXTRAIR DECISÃO DA IA ==============
        decision = cio_decision.get("decision", "HOLD").upper()
        direction = cio_decision.get("direction")
        confidence = cio_decision.get("confidence", 50)
        reasoning = cio_decision.get("reasoning", "Sem explicação")
        
        # Entry/TP/SL definidos pela IA
        entry_price = cio_decision.get("entry_price", quant_raw.get("price", 0))
        take_profit = cio_decision.get("take_profit", 0)
        stop_loss = cio_decision.get("stop_loss", 0)
        
        # ============== CONFIDENCE OVERRIDE ==============
        # REGRA: Se confidence >= 65%, DEVE ser tratado como ENTRY (não HOLD)
        # Isso garante que sinais fortes nunca sejam desperdiçados
        quant_signal = raw_data["quant_analyst"]["signal"]
        
        if decision == "HOLD" and confidence >= 65:
            # Alta confiança + HOLD = inconsistência da IA
            # Forçar ENTRY baseado no sinal técnico
            self.log("CONFIDENCE OVERRIDE", {
                "original_decision": decision,
                "confidence": confidence,
                "override_action": "Forcing ENTRY due to high confidence"
            }, level="warning")
            
            if quant_signal == "BULLISH":
                decision = "ENTRY"
                direction = "BUY"
            elif quant_signal == "BEARISH":
                decision = "ENTRY"
                direction = "SELL"
            # Se técnico for NEUTRAL, mantém HOLD mesmo com alta confiança
        
        # Normalizar decision para o formato do sistema
        if decision == "ENTRY":
            if direction == "BUY":
                final_decision = "BUY"
            elif direction == "SELL":
                final_decision = "SELL"
            else:
                final_decision = "HOLD"
                direction = None
        else:
            final_decision = "HOLD"
            direction = None
        
        # ============== LOG DO VEREDITO ==============
        log_level = "warning" if final_decision in ["BUY", "SELL"] else "info"
        signal_strength = "FORTE" if confidence >= 75 else "MODERADO" if confidence >= 50 else "FRACO"
        
        self.log("CIO VERDICT", {
            "decision": final_decision,
            "direction": direction,
            "confidence": f"{confidence}%",
            "signal_strength": signal_strength,
            "reasoning": reasoning[:100] + "..." if len(reasoning) > 100 else reasoning
        }, level=log_level)
        
        # ============== RESULT FINAL ==============
        market_bias = self._get_market_bias(direction)
        scheduled_entry = self._calculate_entry_window()
        
        exit_levels = {
            "entry_price": entry_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "exit_condition": f"TP: {take_profit:.5f} | SL: {stop_loss:.5f}" if take_profit and stop_loss else "Não definido",
            "risk_reward_ratio": round((take_profit - entry_price) / (entry_price - stop_loss), 2) if stop_loss and take_profit and entry_price != stop_loss else 0
        }
        
        result = {
            "agent": self.name,
            "decision": final_decision,
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "signal_strength": signal_strength,
            "llm_validation": cio_decision,
            "timestamp": datetime.now().isoformat(),
            
            # Professional Execution Strategy
            "market_bias": market_bias,
            "scheduled_entry": scheduled_entry,
            "exit_levels": exit_levels,
            
            "inputs": {
                "technical": {
                    "signal": quant.get("signal", "NEUTRAL"),
                    "raw": quant_raw
                },
                "sentiment": {
                    "score": sentiment_raw.get("score", 0),
                    "label": sentiment_raw.get("label", "NEUTRAL"),
                    "articles_analyzed": sentiment_raw.get("articles_analyzed", 0)
                },
                "macro": {
                    "alert": macro.get("alert", "LOW_RISK"),
                    "high_impact_events": macro.get("high_impact_events", 0),
                    "message": macro.get("message", "")
                }
            },
            
            # Campos para Supabase
            "supabase_record": {
                "pair": pair,
                "technical_signal": {
                    "direction": quant.get("signal", "NEUTRAL"),
                    "indicators": quant_raw
                },
                "sentiment_score": sentiment_raw.get("score", 0),
                "macro_alert": macro.get("alert", "LOW_RISK"),
                "final_decision": f"{final_decision}_{direction}" if direction else final_decision,
                "reasoning": reasoning,
                "market_bias": market_bias,
                "scheduled_entry": scheduled_entry,
                "exit_levels": exit_levels
            }
        }
        
        return result
    
    def _build_veto_result(
        self, 
        pair: str, 
        reason: str, 
        macro: dict, 
        quant: dict,
        sentiment_raw: dict
    ) -> dict[str, Any]:
        """
        Constrói resultado de VETO para Black Swan events.
        """
        return {
            "agent": self.name,
            "decision": "HOLD",
            "direction": None,
            "confidence": 100,  # 100% certeza do veto
            "reasoning": reason,
            "signal_strength": "VETO",
            "llm_validation": {"vetoed": True, "reason": reason},
            "timestamp": datetime.now().isoformat(),
            
            "market_bias": "Lateralizado",
            "scheduled_entry": None,
            "exit_levels": {
                "take_profit": None,
                "stop_loss": None,
                "exit_condition": "VETO - Aguardar normalização",
                "risk_reward_ratio": 0
            },
            
            "inputs": {
                "technical": {
                    "signal": quant.get("signal", "NEUTRAL"),
                    "raw": quant.get("raw_data", {})
                },
                "sentiment": {
                    "score": sentiment_raw.get("score", 0),
                    "label": sentiment_raw.get("label", "NEUTRAL"),
                    "articles_analyzed": sentiment_raw.get("articles_analyzed", 0)
                },
                "macro": {
                    "alert": macro.get("alert", "HIGH_RISK"),
                    "high_impact_events": macro.get("high_impact_events", 0),
                    "message": macro.get("message", ""),
                    "VETO_ACTIVE": True
                }
            },
            
            "supabase_record": {
                "pair": pair,
                "technical_signal": {"direction": "NEUTRAL", "indicators": {}},
                "sentiment_score": sentiment_raw.get("score", 0),
                "macro_alert": macro.get("alert", "HIGH_RISK"),
                "final_decision": "VETO_MACRO",
                "reasoning": reason,
                "market_bias": "Lateralizado",
                "scheduled_entry": None,
                "exit_levels": None
            }
        }


# Singleton
risk_commander = RiskCommanderAgent()
