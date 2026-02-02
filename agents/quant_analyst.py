"""
3V Engine - Quant Analyst Agent
================================
@Quant_Analyst: Responsável pela análise técnica.
Consome API Twelve Data e calcula indicadores.
Agora inclui cálculo de TP/SL baseado em Bollinger Bands e RSI.
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
    - Calcular níveis de TP/SL para execução precisa
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
    
    def _calculate_exit_levels(
        self,
        signal: str,
        current_price: float,
        atr_data: dict[str, Any],
        bollinger: dict[str, Any] | None = None,
        rsi: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Calcula níveis de Take Profit (TP) e Stop Loss (SL) baseados em ATR.
        
        ATR (Average True Range) adapta os níveis à volatilidade atual:
        - Mercado volátil: TP/SL mais distantes
        - Mercado calmo: TP/SL mais próximos
        
        Configuração padrão:
        - SL = 1.5x ATR (proteção)
        - TP = 2.5x ATR (alvo) → RR 1:1.67
        
        O volatility_factor ajusta automaticamente:
        - HIGH volatility: aumenta distâncias 1.5x
        - LOW volatility: reduz distâncias 0.75x
        
        Args:
            signal: Sinal técnico (BULLISH/BEARISH/NEUTRAL)
            current_price: Preço atual do par
            atr_data: Dados do ATR incluindo volatility_factor
            bollinger: Dados das Bandas de Bollinger (fallback)
            rsi: Dados do RSI para condição de saída
        
        Returns:
            Dict com take_profit, stop_loss, distâncias em pips, e RR
        """
        # Extrai dados do ATR
        atr = atr_data.get("atr", 0.001)  # Default ~10 pips se não disponível
        volatility = atr_data.get("volatility", "NORMAL")
        volatility_factor = atr_data.get("volatility_factor", 1.0)
        
        # Multipliers baseados em volatilidade
        sl_multiplier = 1.5 * volatility_factor  # 1.5x ATR base
        tp_multiplier = 2.5 * volatility_factor  # 2.5x ATR base (RR ~1.67)
        
        # Calcula distâncias
        sl_distance = atr * sl_multiplier
        tp_distance = atr * tp_multiplier
        
        # Converte para pips (1 pip = 0.0001 para EUR/USD)
        sl_pips = round(sl_distance * 10000, 1)
        tp_pips = round(tp_distance * 10000, 1)
        
        rsi_value = rsi.get("rsi", 50) if rsi else 50
        
        if signal == "BULLISH":
            take_profit = current_price + tp_distance
            stop_loss = current_price - sl_distance
            
            if rsi_value > 60:
                exit_condition = f"TP em {tp_pips} pips ou RSI > 70 (sobrecompra)"
            else:
                exit_condition = f"TP em {tp_pips} pips ou trailing stop"
        
        elif signal == "BEARISH":
            take_profit = current_price - tp_distance
            stop_loss = current_price + sl_distance
            
            if rsi_value < 40:
                exit_condition = f"TP em {tp_pips} pips ou RSI < 30 (sobrevenda)"
            else:
                exit_condition = f"TP em {tp_pips} pips ou trailing stop"
        
        else:  # NEUTRAL
            # Sem direção - usar ATR para ambos os lados
            take_profit = current_price + (tp_distance * 0.5)  # TP menor
            stop_loss = current_price - (sl_distance * 0.5)    # SL menor
            exit_condition = "Aguardar confirmação de direção"
            tp_pips = round(tp_pips * 0.5, 1)
            sl_pips = round(sl_pips * 0.5, 1)
        
        # Calcula Risk/Reward ratio
        potential_gain = abs(take_profit - current_price)
        potential_loss = abs(current_price - stop_loss)
        risk_reward = round(potential_gain / potential_loss, 2) if potential_loss > 0 else 0
        
        return {
            "take_profit": round(take_profit, 5),
            "stop_loss": round(stop_loss, 5),
            "exit_condition": exit_condition,
            "risk_reward_ratio": risk_reward,
            "current_price": round(current_price, 5),
            # ATR-specific data
            "atr": atr,
            "atr_pips": round(atr * 10000, 1),
            "volatility": volatility,
            "tp_pips": tp_pips,
            "sl_pips": sl_pips,
            "method": "ATR_DYNAMIC"  # Identificador do método usado
        }
    
    def _calculate_deterministic_signal(
        self,
        moving_averages: dict,
        rsi_data: dict,
        bollinger_data: dict
    ) -> tuple[str, int, list[str]]:
        """
        Calcula sinal técnico de forma DETERMINÍSTICA (sem LLM).
        
        ESTRATÉGIA TREND-FOLLOWING para Day Trading:
        - Trend forte (MA score >= 3 ou <= -3): SEGUE o trend
        - RSI é usado para CONFIRMAR trend, não para contra-trend
        - Bollinger usado para timing de entrada
        
        Returns:
            Tuple[signal, confidence, reasons]
        """
        score = 0
        reasons = []
        
        # 1. TENDÊNCIA DAS MAs (PESO DOMINANTE)
        ma_trend = moving_averages.get("trend", "NEUTRAL")
        ma_score = moving_averages.get("trend_score", 0)
        
        # REGRA CRÍTICA: Trend forte = seguir o trend!
        # MODO AGRESSIVO: baixamos o threshold de 3 para 2
        strong_trend = abs(ma_score) >= 2
        
        if ma_trend == "BULLISH":
            score += 3 if strong_trend else 2
            reasons.append(f"MAs bullish {'FORTE' if strong_trend else ''} (score: {ma_score})")
        elif ma_trend == "BEARISH":
            score -= 3 if strong_trend else 2
            reasons.append(f"MAs bearish {'FORTE' if strong_trend else ''} (score: {ma_score})")
        
        # 2. RSI - LÓGICA TREND-FOLLOWING
        # Em trend forte: RSI extremo CONFIRMA o movimento, não indica reversão
        rsi_value = rsi_data.get("rsi", 50)
        
        if rsi_value is not None:
            if strong_trend:
                # TREND-FOLLOWING: RSI extremo = momentum forte
                if ma_trend == "BULLISH":
                    if rsi_value >= 50:
                        score += 1
                        reasons.append(f"RSI confirma alta ({rsi_value})")
                    if rsi_value >= 60:
                        score += 1
                        reasons.append(f"RSI momentum forte ({rsi_value})")
                elif ma_trend == "BEARISH":
                    if rsi_value <= 50:
                        score -= 1
                        reasons.append(f"RSI confirma queda ({rsi_value})")
                    if rsi_value <= 40:
                        score -= 1
                        reasons.append(f"RSI momentum forte ({rsi_value})")
            else:
                # SEM TREND FORTE: lógica tradicional de reversão
                # MODO AGRESSIVO: RSI entre 40-60 também conta
                if rsi_value <= 30:
                    score += 2
                    reasons.append(f"RSI oversold ({rsi_value}) - potencial reversão")
                elif rsi_value <= 45:
                    score += 1
                    reasons.append(f"RSI baixo ({rsi_value})")
                elif rsi_value >= 70:
                    score -= 2
                    reasons.append(f"RSI overbought ({rsi_value}) - potencial reversão")
                elif rsi_value >= 55:
                    score -= 1
                    reasons.append(f"RSI alto ({rsi_value})")
        
        # 3. BOLLINGER BANDS (timing de entrada)
        bb_position = bollinger_data.get("position", "NEUTRAL")
        
        if strong_trend:
            # Em trend forte: preço na banda indica força, não reversão
            if ma_trend == "BULLISH" and bb_position in ["UPPER_HALF", "ABOVE_UPPER"]:
                score += 1
                reasons.append("Preço rompendo Bollinger (trend bullish)")
            elif ma_trend == "BEARISH" and bb_position in ["LOWER_HALF", "BELOW_LOWER"]:
                score -= 1
                reasons.append("Preço rompendo Bollinger (trend bearish)")
        else:
            # Sem trend forte: Bollinger tradicional (reversão à média)
            if bb_position == "BELOW_LOWER":
                score += 2
                reasons.append("Preço abaixo Bollinger inferior")
            elif bb_position == "ABOVE_UPPER":
                score -= 2
                reasons.append("Preço acima Bollinger superior")
            elif bb_position == "LOWER_HALF":
                score += 1
                reasons.append("Preço na metade inferior BB")
            elif bb_position == "UPPER_HALF":
                score -= 1
                reasons.append("Preço na metade superior BB")
        
        # DETERMINA SINAL FINAL
        # MODO AGRESSIVO: threshold baixo para mais operações
        if score >= 1:
            signal = "BULLISH"
            confidence = min(60 + (score * 8), 95)
        elif score <= -1:
            signal = "BEARISH"
            confidence = min(60 + (abs(score) * 8), 95)
        else:
            signal = "NEUTRAL"
            confidence = 40
        
        # Log especial para trend forte
        if strong_trend:
            reasons.insert(0, f"🔥 TREND FORTE DETECTADO ({ma_trend})")
        
        return signal, confidence, reasons
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Executa análise técnica completa.
        
        ESTRATÉGIA HÍBRIDA:
        1. Calcula sinal DETERMINÍSTICO (baseado em indicadores)
        2. Consulta LLM para validação
        3. Se LLM retornar NEUTRAL, usa sinal determinístico
        
        Args:
            market_state: Estado do mercado (pode ser ignorado, usamos dados frescos)
        
        Returns:
            Análise técnica com indicadores, sinal, e níveis de TP/SL
        """
        self.log("Starting technical analysis")
        
        # Obtém dados técnicos frescos
        technical_data = await twelve_data_client.get_technical_analysis()
        
        current_price = technical_data["current_price"]
        rsi_data = technical_data["rsi"]
        bollinger_data = technical_data["bollinger_bands"]
        moving_averages = technical_data["moving_averages"]
        atr_data = technical_data.get("atr", {})  # NEW: ATR para TP/SL dinâmico
        
        self.log("Technical data retrieved", {
            "price": current_price,
            "rsi": rsi_data["rsi"],
            "trend": moving_averages.get("trend"),
            "trend_score": moving_averages.get("trend_score", 0),
            "atr_pips": atr_data.get("atr_pips", 0),
            "volatility": atr_data.get("volatility", "N/A")
        })
        
        # 1. SINAL DETERMINÍSTICO (objetivo, sem LLM)
        det_signal, det_confidence, det_reasons = self._calculate_deterministic_signal(
            moving_averages=moving_averages,
            rsi_data=rsi_data,
            bollinger_data=bollinger_data
        )
        
        self.log("Deterministic signal calculated", {
            "signal": det_signal,
            "confidence": det_confidence,
            "reasons": det_reasons
        })
        
        # 2. VALIDAÇÃO LLM (opcional, pode confirmar ou divergir)
        llm_analysis = await self.reason(technical_data)
        llm_signal = llm_analysis.get("signal", "NEUTRAL")
        
        # 3. DECISÃO FINAL (híbrida)
        # Prioridade: determinístico, LLM como validação
        if det_signal != "NEUTRAL":
            # Confiamos no sinal determinístico
            final_signal = det_signal
            final_confidence = det_confidence
            
            # Bônus se LLM concordar
            if llm_signal == det_signal:
                final_confidence = min(final_confidence + 10, 95)
                self.log("LLM confirms deterministic signal", level="info")
        elif llm_signal != "NEUTRAL":
            # Determinístico é neutro, mas LLM viu algo
            final_signal = llm_signal
            final_confidence = llm_analysis.get("confidence_score", 55)
            self.log("Using LLM signal (deterministic was neutral)", level="info")
        else:
            # Ambos neutros
            final_signal = "NEUTRAL"
            final_confidence = det_confidence
        
        # Calcula níveis de TP/SL usando ATR dinâmico
        exit_levels = self._calculate_exit_levels(
            signal=final_signal,
            current_price=current_price,
            atr_data=atr_data,  # ATR como base principal
            bollinger=bollinger_data,
            rsi=rsi_data
        )
        
        self.log("Exit levels calculated (ATR-based)", {
            "take_profit": exit_levels["take_profit"],
            "stop_loss": exit_levels["stop_loss"],
            "risk_reward": exit_levels["risk_reward_ratio"],
            "tp_pips": exit_levels.get("tp_pips"),
            "sl_pips": exit_levels.get("sl_pips"),
            "volatility": exit_levels.get("volatility")
        })
        
        # ============== MULTI-TIMEFRAME ANALYSIS ==============
        # Busca confluência em M5, M15, H1, H4
        mtf_analysis = None
        mtf_confluence = None
        
        try:
            self.log("Running Multi-Timeframe Analysis")
            mtf_analysis = await twelve_data_client.get_multi_timeframe_analysis()
            mtf_confluence = mtf_analysis.get("confluence", {})
            
            self.log("MTF Analysis complete", {
                "confluence_direction": mtf_confluence.get("direction"),
                "confluence_score": mtf_confluence.get("score"),
                "signals": mtf_confluence.get("signals")
            })
            
            # AJUSTA CONFIANÇA baseado em confluência MTF
            if mtf_confluence.get("direction") == final_signal:
                # Confluência confirma nosso sinal - aumenta confiança
                confluence_bonus = min(mtf_confluence.get("score", 0) // 5, 15)  # Max +15%
                final_confidence = min(final_confidence + confluence_bonus, 98)
                det_reasons.append(f"MTF Confluência {mtf_confluence.get('direction')} ({mtf_confluence.get('bullish_count')}/{mtf_confluence.get('bearish_count')} TFs)")
                self.log(f"MTF confirms signal, +{confluence_bonus}% confidence", level="info")
            elif mtf_confluence.get("direction") in ["BULLISH", "BEARISH"] and mtf_confluence.get("direction") != final_signal:
                # Divergência - reduz confiança
                final_confidence = max(final_confidence - 10, 40)
                det_reasons.append(f"⚠️ Divergência MTF: {mtf_confluence.get('direction')}")
                self.log("MTF diverges from signal, -10% confidence", level="warning")
        except Exception as e:
            self.log(f"MTF Analysis failed: {e}", level="warning")
            mtf_analysis = {"error": str(e)}

        # ============== FLATTEN RAW_DATA FOR RISK COMMANDER ==============
        # Risk Commander expects flattened keys, not nested structures
        flattened_raw_data = {
            # Basic info
            "timestamp": technical_data["timestamp"],
            "symbol": technical_data.get("symbol", "EUR/USD"),
            "candles_analyzed": technical_data.get("candles_analyzed", 0),
            
            # Price (required by Risk Commander)
            "price": current_price,
            "current_price": current_price,
            
            # RSI (flattened)
            "rsi": rsi_data.get("rsi", 50),
            "rsi_condition": rsi_data.get("condition", "NEUTRAL"),
            
            # Bollinger Bands (flattened)
            "bb_upper": bollinger_data.get("upper", current_price * 1.01),
            "bb_middle": bollinger_data.get("middle", current_price),
            "bb_lower": bollinger_data.get("lower", current_price * 0.99),
            "bb_position": bollinger_data.get("position", "MIDDLE"),
            
            # ATR Volatility (NEW!)
            "atr": atr_data.get("atr", 0),
            "atr_pips": atr_data.get("atr_pips", 0),
            "volatility": atr_data.get("volatility", "NORMAL"),
            "volatility_factor": atr_data.get("volatility_factor", 1.0),
            
            # Moving Averages
            "trend": moving_averages.get("trend", "NEUTRAL"),
            "trend_score": moving_averages.get("trend_score", 0),
            "ma_signals": moving_averages.get("trend_signals", []),
            "ma_20": moving_averages.get("MA_20", 0),
            "ma_50": moving_averages.get("MA_50", 0),
            "ma_200": moving_averages.get("MA_200", 0),
            
            # Candlestick patterns
            "patterns": technical_data.get("candlestick_patterns", []),
            
            # Multi-Timeframe Analysis (NEW!)
            "mtf_confluence_direction": mtf_confluence.get("direction") if mtf_confluence else None,
            "mtf_confluence_score": mtf_confluence.get("score", 0) if mtf_confluence else 0,
            "mtf_confluence_message": mtf_confluence.get("message", "") if mtf_confluence else "",
            "mtf_signals": mtf_confluence.get("signals", []) if mtf_confluence else [],
            "mtf_divergence": mtf_confluence.get("divergence", False) if mtf_confluence else False,
            "mtf_timeframes": mtf_analysis.get("timeframes", {}) if mtf_analysis else {},
            
            # Original nested data (for reference)
            "moving_averages": moving_averages,
            "rsi_data": rsi_data,
            "bollinger_bands": bollinger_data,
            "mtf_analysis": mtf_analysis
        }
        
        # Combina dados técnicos com análise
        result = {
            "agent": self.name,
            "timestamp": technical_data["timestamp"],
            "raw_data": flattened_raw_data,
            "llm_analysis": llm_analysis,
            "deterministic_analysis": {
                "signal": det_signal,
                "confidence": det_confidence,
                "reasons": det_reasons
            },
            "deterministic_reasons": det_reasons,  # Also at top level for Risk Commander
            "signal": final_signal,
            "confidence": final_confidence,
            "exit_levels": exit_levels
        }
        
        # Log com destaque se não for neutro
        log_level = "warning" if final_signal != "NEUTRAL" else "info"
        self.log("Analysis complete", {
            "signal": result["signal"],
            "confidence": result["confidence"]
        }, level=log_level)
        
        return result



# Singleton
quant_analyst = QuantAnalystAgent()
