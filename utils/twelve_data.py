"""
3V Engine - Twelve Data Client
===============================
Cliente assíncrono para API da Twelve Data.
Fornece dados OHLCV e indicadores técnicos em tempo real.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
import pandas as pd

from core.config import settings
from utils.logger import log_agent_action


class TwelveDataClient:
    """
    Cliente para consumo da API Twelve Data.
    Calcula indicadores técnicos para análise do @Quant_Analyst.
    
    IMPORTANTE: Twelve Data Free Tier tem limite de 8 chamadas/minuto.
    Este cliente inclui retry logic para lidar com rate limits.
    """
    
    # Rate limit: 8 chamadas por minuto no free tier
    MAX_RETRIES = 3
    RETRY_DELAY = 8.0  # segundos entre retries
    
    def __init__(self) -> None:
        self._base_url = settings.twelve_data_base_url
        self._api_key = settings.twelve_data_api_key
        # Forex deve usar símbolo COM barra: EUR/USD
        self._symbol = settings.trading_pair  # Mantém EUR/USD
    
    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Executa requisição à API com retry logic.
        
        Implementa retry para lidar com rate limits (8 req/min no free tier).
        """
        params = params or {}
        params["apikey"] = self._api_key
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{self._base_url}/{endpoint}",
                        params=params
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Verifica se a API retornou erro (ex: rate limit)
                    if "code" in data and data.get("code") in [429, 400]:
                        raise ValueError(data.get("message", "API rate limit"))
                    
                    # Verifica se 'price' está ausente em endpoint de preço
                    if endpoint == "price" and "price" not in data:
                        error_msg = data.get("message", "Response missing 'price' field")
                        raise ValueError(f"Invalid response: {error_msg}")
                    
                    return data
                    
            except (httpx.HTTPStatusError, ValueError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    log_agent_action(
                        "@TwelveData",
                        f"Rate limit hit, retry {attempt + 1}/{self.MAX_RETRIES}",
                        {"delay": self.RETRY_DELAY},
                        level="warning"
                    )
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue
                raise
        
        raise last_error or Exception("Max retries exceeded")
    
    async def get_price_data(
        self,
        interval: str = "5min",
        outputsize: int = 200
    ) -> pd.DataFrame:
        """
        Obtém dados OHLCV do par de moedas.
        
        Args:
            interval: Intervalo de tempo (1min, 5min, 15min, 1h, 1day)
            outputsize: Quantidade de candles (máximo 5000)
        
        Returns:
            DataFrame com colunas: datetime, open, high, low, close, volume
        """
        log_agent_action("@TwelveData", "Fetching price data", {"interval": interval})
        
        data = await self._request("time_series", {
            "symbol": self._symbol,  # EUR/USD com barra
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "America/Sao_Paulo"
        })
        
        if "values" not in data:
            raise ValueError(f"Erro ao obter dados: {data.get('message', 'Unknown error')}")
        
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Ordenar do mais antigo para o mais recente
        df = df.sort_values("datetime").reset_index(drop=True)
        
        return df
    
    async def get_current_price(self) -> dict[str, float]:
        """Obtém preço atual do par com retry logic."""
        data = await self._request("price", {"symbol": self._symbol})
        return {"price": float(data["price"])}
    
    def calculate_moving_averages(
        self,
        df: pd.DataFrame,
        periods: list[int] | None = None
    ) -> dict[str, float]:
        """
        Calcula Médias Móveis Simples.
        
        Args:
            df: DataFrame com coluna 'close'
            periods: Períodos das MAs (padrão: 20, 50, 200)
        
        Returns:
            Dict com valores das MAs
        """
        periods = periods or [20, 50, 200]
        result = {}
        
        for period in periods:
            if len(df) >= period:
                ma = df["close"].tail(period).mean()
                result[f"MA_{period}"] = round(ma, 5)
            else:
                result[f"MA_{period}"] = None
        
        # Sinal de tendência (RELAXADO para Day Trading)
        # Flexível para funcionar com 2 ou 3 MAs
        ma20 = result.get("MA_20")
        ma50 = result.get("MA_50")
        ma200 = result.get("MA_200")
        
        if ma20 and ma50:  # Mínimo necessário: MA20 e MA50
            current_price = df["close"].iloc[-1]
            
            # Sistema de pontuação: +1 bullish, -1 bearish
            score = 0
            signals = []
            
            # MA20 vs MA50 (curto prazo) - peso maior
            if ma20 > ma50:
                score += 2
                signals.append("MA20>MA50")
            elif ma20 < ma50:
                score -= 2
                signals.append("MA20<MA50")
            
            # MA50 vs MA200 (médio prazo) - apenas se MA200 disponível
            if ma200:
                if ma50 > ma200:
                    score += 1
                    signals.append("MA50>MA200")
                elif ma50 < ma200:
                    score -= 1
                    signals.append("MA50<MA200")
            
            # Preço vs MA20 (momentum imediato) - peso maior
            if current_price > ma20:
                score += 2
                signals.append("Price>MA20")
            elif current_price < ma20:
                score -= 2
                signals.append("Price<MA20")
            
            # Determina tendência baseada na pontuação
            # MODO AGRESSIVO: threshold baixo para mais sinais
            # Score range: -5 to +5 (ou -4 to +4 sem MA200)
            if score >= 1:
                result["trend"] = "BULLISH"
            elif score <= -1:
                result["trend"] = "BEARISH"
            else:
                result["trend"] = "NEUTRAL"
            
            result["trend_score"] = score
            result["trend_signals"] = signals
        
        return result
    
    def calculate_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> dict[str, Any]:
        """
        Calcula Relative Strength Index.
        
        Args:
            df: DataFrame com coluna 'close'
            period: Período do RSI (padrão: 14)
        
        Returns:
            Dict com RSI e zona (overbought/oversold/neutral)
        """
        if len(df) < period + 1:
            return {"rsi": None, "zone": "INSUFFICIENT_DATA"}
        
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = round(rsi.iloc[-1], 2)
        
        if current_rsi >= 70:
            zone = "OVERBOUGHT"
        elif current_rsi <= 30:
            zone = "OVERSOLD"
        else:
            zone = "NEUTRAL"
        
        return {"rsi": current_rsi, "zone": zone, "condition": zone}
    
    def calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> dict[str, Any]:
        """
        Calcula Average True Range (ATR) para volatilidade.
        
        O ATR mede a volatilidade média do mercado, essencial para:
        - Definir TP/SL proporcionais à volatilidade
        - Identificar quando o mercado está mais ou menos volátil
        - Calcular position sizing baseado em risco
        
        Args:
            df: DataFrame com colunas high, low, close
            period: Período do ATR (padrão: 14)
        
        Returns:
            Dict com ATR absoluto, ATR em pips, e classificação de volatilidade
        """
        if len(df) < period + 1:
            return {
                "atr": None,
                "atr_pips": None,
                "volatility": "INSUFFICIENT_DATA"
            }
        
        # True Range = max(H-L, |H-Prev Close|, |L-Prev Close|)
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = SMA do True Range
        atr = true_range.rolling(window=period).mean().iloc[-1]
        atr_rounded = round(atr, 5)
        
        # Converte ATR para pips (1 pip = 0.0001 para EUR/USD)
        atr_pips = round(atr * 10000, 1)
        
        # Classifica volatilidade baseado em ATR histórico
        atr_series = true_range.rolling(window=period).mean()
        atr_20_percentile = atr_series.quantile(0.20)
        atr_80_percentile = atr_series.quantile(0.80)
        
        if atr >= atr_80_percentile:
            volatility = "HIGH"
            volatility_factor = 1.5  # Aumenta TP/SL em mercado volátil
        elif atr <= atr_20_percentile:
            volatility = "LOW"
            volatility_factor = 0.75  # Reduz TP/SL em mercado calmo
        else:
            volatility = "NORMAL"
            volatility_factor = 1.0
        
        # Calcula níveis sugeridos de TP/SL baseados em ATR
        current_price = close.iloc[-1]
        
        # TP padrão = 2.5x ATR, SL padrão = 1.5x ATR (RR 1:1.67)
        suggested_sl_distance = atr * 1.5 * volatility_factor
        suggested_tp_distance = atr * 2.5 * volatility_factor
        
        return {
            "atr": atr_rounded,
            "atr_pips": atr_pips,
            "volatility": volatility,
            "volatility_factor": volatility_factor,
            "suggested_sl_distance": round(suggested_sl_distance, 5),
            "suggested_tp_distance": round(suggested_tp_distance, 5),
            "suggested_sl_pips": round(suggested_sl_distance * 10000, 1),
            "suggested_tp_pips": round(suggested_tp_distance * 10000, 1),
            "risk_reward_ratio": round(suggested_tp_distance / suggested_sl_distance, 2) if suggested_sl_distance > 0 else 0
        }
    
    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: int = 2
    ) -> dict[str, Any]:
        """
        Calcula Bandas de Bollinger.
        
        Args:
            df: DataFrame com coluna 'close'
            period: Período da média (padrão: 20)
            std_dev: Desvio padrão (padrão: 2)
        
        Returns:
            Dict com upper, middle, lower bands e posição do preço
        """
        if len(df) < period:
            return {"upper": None, "middle": None, "lower": None, "position": "INSUFFICIENT_DATA"}
        
        sma = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        current_price = df["close"].iloc[-1]
        current_upper = round(upper.iloc[-1], 5)
        current_lower = round(lower.iloc[-1], 5)
        current_middle = round(sma.iloc[-1], 5)
        
        # Posição relativa do preço nas bandas
        if current_price >= current_upper:
            position = "ABOVE_UPPER"
        elif current_price <= current_lower:
            position = "BELOW_LOWER"
        elif current_price > current_middle:
            position = "UPPER_HALF"
        else:
            position = "LOWER_HALF"
        
        return {
            "upper": current_upper,
            "middle": current_middle,
            "lower": current_lower,
            "position": position
        }
    
    def identify_candlestick_patterns(
        self,
        df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        """
        Identifica padrões de candlesticks nos últimos 5 candles.
        
        Args:
            df: DataFrame com colunas OHLC
        
        Returns:
            Lista de padrões encontrados
        """
        if len(df) < 5:
            return []
        
        patterns = []
        last_5 = df.tail(5)
        
        # Doji
        for _, candle in last_5.iterrows():
            body = abs(candle["close"] - candle["open"])
            wick = candle["high"] - candle["low"]
            if wick > 0 and body / wick < 0.1:
                patterns.append({
                    "pattern": "DOJI",
                    "signal": "INDECISION",
                    "datetime": str(candle["datetime"])
                })
        
        # Hammer / Hanging Man
        last = df.iloc[-1]
        body = abs(last["close"] - last["open"])
        lower_wick = min(last["open"], last["close"]) - last["low"]
        upper_wick = last["high"] - max(last["open"], last["close"])
        
        if lower_wick > body * 2 and upper_wick < body * 0.5:
            patterns.append({
                "pattern": "HAMMER",
                "signal": "BULLISH_REVERSAL",
                "datetime": str(last["datetime"])
            })
        
        if upper_wick > body * 2 and lower_wick < body * 0.5:
            patterns.append({
                "pattern": "SHOOTING_STAR",
                "signal": "BEARISH_REVERSAL",
                "datetime": str(last["datetime"])
            })
        
        # Engulfing
        if len(df) >= 2:
            prev = df.iloc[-2]
            curr = df.iloc[-1]
            
            prev_body_start = min(prev["open"], prev["close"])
            prev_body_end = max(prev["open"], prev["close"])
            curr_body_start = min(curr["open"], curr["close"])
            curr_body_end = max(curr["open"], curr["close"])
            
            if curr_body_start < prev_body_start and curr_body_end > prev_body_end:
                if curr["close"] > curr["open"]:
                    patterns.append({
                        "pattern": "BULLISH_ENGULFING",
                        "signal": "BULLISH",
                        "datetime": str(curr["datetime"])
                    })
                else:
                    patterns.append({
                        "pattern": "BEARISH_ENGULFING",
                        "signal": "BEARISH",
                        "datetime": str(curr["datetime"])
                    })
        
        return patterns
    
    async def get_technical_analysis(
        self,
        symbol: str | None = None,
        interval: str = "5min",
        outputsize: int = 200
    ) -> dict[str, Any]:
        """
        Executa análise técnica completa para o @Quant_Analyst.
        
        Args:
            symbol: Par de moedas (ex: EURUSD). Default: configuração global
            interval: Timeframe (1min, 5min, 15min, 1h, 4h)
            outputsize: Quantidade de candles
        
        Returns:
            Dict com todos os indicadores e padrões
        """
        # Permite override do símbolo para multi-pair scanner
        target_symbol = symbol or self._symbol.replace("/", "")
        
        log_agent_action("@TwelveData", "Running full technical analysis", {
            "symbol": target_symbol,
            "interval": interval
        })
        
        # Obtém dados de preço com símbolo customizado
        data = await self._request("time_series", {
            "symbol": target_symbol if "/" not in target_symbol else target_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "America/Sao_Paulo"
        })
        
        if "values" not in data:
            raise ValueError(f"Erro ao obter dados: {data.get('message', 'Unknown error')}")
        
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("datetime").reset_index(drop=True)
        
        current_price = df["close"].iloc[-1]
        
        # Calcula indicadores
        moving_averages = self.calculate_moving_averages(df)
        rsi = self.calculate_rsi(df)
        bollinger = self.calculate_bollinger_bands(df)
        patterns = self.identify_candlestick_patterns(df)
        atr = self.calculate_atr(df)  # NEW: ATR para TP/SL dinâmico
        
        # Ajusta cálculo de pip para pares com JPY
        if "JPY" in target_symbol.upper():
            if "atr_pips" in atr:
                atr["atr_pips"] = atr.get("atr", 0) / 0.01  # JPY usa 0.01
        
        return {
            "timestamp": datetime.now().isoformat(),
            "symbol": target_symbol,
            "price": round(current_price, 5),
            "current_price": round(current_price, 5),
            "moving_averages": moving_averages,
            "rsi": rsi,
            "bollinger_bands": bollinger,
            "atr": atr,  # NEW!
            "candlestick_patterns": patterns,
            "candles_analyzed": len(df)
        }
    
    async def get_multi_timeframe_analysis(self) -> dict[str, Any]:
        """
        Executa Multi-Timeframe Analysis (MTF) para identificar confluência.
        
        Timeframes analisados:
        - M5 (5min): Timing de entrada preciso
        - M15 (15min): Confirmação de tendência curta
        - H1 (1h): Direção intraday
        - H4 (4h): Tendência de swing
        
        Returns:
            Dict com análise de cada TF e score de confluência
        """
        log_agent_action("@TwelveData", "Running Multi-Timeframe Analysis (MTF)")
        
        timeframes = {
            "M5": "5min",
            "M15": "15min",
            "H1": "1h",
            "H4": "4h"
        }
        
        mtf_data = {}
        current_price = None
        
        for tf_name, interval in timeframes.items():
            try:
                log_agent_action("@TwelveData", f"Fetching {tf_name} data", {"interval": interval})
                
                # Obtém dados para este timeframe
                df = await self.get_price_data(interval=interval, outputsize=100)
                
                if current_price is None:
                    current_price = df["close"].iloc[-1]
                
                # Calcula indicadores para este TF
                ma = self.calculate_moving_averages(df, periods=[20, 50])
                rsi = self.calculate_rsi(df)
                bb = self.calculate_bollinger_bands(df)
                
                # Determina sinal deste TF
                trend = ma.get("trend", "NEUTRAL")
                trend_score = ma.get("trend_score", 0)
                rsi_value = rsi.get("rsi", 50)
                rsi_condition = rsi.get("condition", "NEUTRAL")
                bb_position = bb.get("position", "MIDDLE")
                
                # Calcula sinal do TF
                tf_signal = self._calculate_tf_signal(trend, trend_score, rsi_value, bb_position)
                
                mtf_data[tf_name] = {
                    "interval": interval,
                    "signal": tf_signal["signal"],
                    "strength": tf_signal["strength"],
                    "trend": trend,
                    "trend_score": trend_score,
                    "rsi": round(rsi_value, 2),
                    "rsi_condition": rsi_condition,
                    "bb_position": bb_position,
                    "ma_20": ma.get("MA_20"),
                    "ma_50": ma.get("MA_50")
                }
                
                # Rate limit: espera um pouco entre chamadas
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log_agent_action(
                    "@TwelveData",
                    f"Failed to fetch {tf_name} data: {e}",
                    level="warning"
                )
                mtf_data[tf_name] = {
                    "interval": interval,
                    "signal": "NEUTRAL",
                    "strength": 0,
                    "error": str(e)
                }
        
        # Calcula confluência entre timeframes
        confluence = self._calculate_confluence(mtf_data)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "symbol": settings.trading_pair,
            "current_price": round(current_price, 5) if current_price else 0,
            "timeframes": mtf_data,
            "confluence": confluence
        }
    
    def _calculate_tf_signal(
        self,
        trend: str,
        trend_score: int,
        rsi: float,
        bb_position: str
    ) -> dict[str, Any]:
        """
        Calcula sinal de um timeframe específico.
        
        Args:
            trend: BULLISH, BEARISH, NEUTRAL
            trend_score: -5 a +5
            rsi: Valor do RSI
            bb_position: Posição nas Bandas de Bollinger
        
        Returns:
            Dict com signal e strength
        """
        score = 0
        
        # Trend contribui com peso maior
        if trend == "BULLISH":
            score += min(trend_score, 3)  # Máx +3
        elif trend == "BEARISH":
            score += max(trend_score, -3)  # Mín -3
        
        # RSI contribui
        if rsi > 60:
            score += 1  # Momentum bullish
        elif rsi < 40:
            score -= 1  # Momentum bearish
        
        # Bollinger contribui
        if bb_position == "BELOW_LOWER":
            score += 1  # Potencial reversão para cima
        elif bb_position == "ABOVE_UPPER":
            score -= 1  # Potencial reversão para baixo
        elif bb_position == "LOWER_HALF":
            score -= 0.5  # Leve bearish
        elif bb_position == "UPPER_HALF":
            score += 0.5  # Leve bullish
        
        # Determina sinal
        if score >= 2:
            signal = "BULLISH"
            strength = min(int(score * 25), 100)
        elif score <= -2:
            signal = "BEARISH"
            strength = min(int(abs(score) * 25), 100)
        else:
            signal = "NEUTRAL"
            strength = int(abs(score) * 20)
        
        return {"signal": signal, "strength": strength}
    
    def _calculate_confluence(self, mtf_data: dict[str, Any]) -> dict[str, Any]:
        """
        Calcula confluência entre múltiplos timeframes.
        
        Regras:
        - 4/4 TFs no mesmo sentido = FORTE confluência (score 100)
        - 3/4 TFs no mesmo sentido = BOA confluência (score 75)
        - 2/4 TFs = FRACA confluência (score 50)
        - Divergência H1/H4 vs M5/M15 = WARNING
        
        Returns:
            Dict com score de confluência e mensagem
        """
        bullish_count = 0
        bearish_count = 0
        signals = []
        
        # Pesos por timeframe (H4 tem mais peso que M5)
        weights = {"M5": 1, "M15": 1.5, "H1": 2, "H4": 3}
        weighted_score = 0
        total_weight = 0
        
        for tf_name, data in mtf_data.items():
            if "error" in data:
                continue
                
            signal = data.get("signal", "NEUTRAL")
            weight = weights.get(tf_name, 1)
            total_weight += weight
            
            if signal == "BULLISH":
                bullish_count += 1
                weighted_score += weight
                signals.append(f"{tf_name}:BULL")
            elif signal == "BEARISH":
                bearish_count += 1
                weighted_score -= weight
                signals.append(f"{tf_name}:BEAR")
            else:
                signals.append(f"{tf_name}:NEUT")
        
        # Normaliza score para 0-100
        if total_weight > 0:
            normalized_score = (weighted_score / total_weight) * 50 + 50  # 0 a 100
        else:
            normalized_score = 50
        
        # Determina direção dominante
        if bullish_count >= 3:
            direction = "BULLISH"
            confluence_score = min(int(normalized_score), 100)
            message = f"Confluência BULLISH em {bullish_count}/4 timeframes"
        elif bearish_count >= 3:
            direction = "BEARISH"
            confluence_score = min(int(100 - normalized_score), 100)
            message = f"Confluência BEARISH em {bearish_count}/4 timeframes"
        elif bullish_count == bearish_count == 2:
            direction = "MIXED"
            confluence_score = 30
            message = "Divergência entre timeframes - aguardar"
        else:
            direction = "NEUTRAL"
            confluence_score = 40
            message = "Sem confluência clara"
        
        # Verifica divergência H4 vs M5 (warning)
        h4_signal = mtf_data.get("H4", {}).get("signal", "NEUTRAL")
        m5_signal = mtf_data.get("M5", {}).get("signal", "NEUTRAL")
        
        divergence = False
        if (h4_signal == "BULLISH" and m5_signal == "BEARISH") or \
           (h4_signal == "BEARISH" and m5_signal == "BULLISH"):
            divergence = True
            message += " | ⚠️ Divergência H4/M5"
        
        return {
            "direction": direction,
            "score": confluence_score,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "weighted_score": round(weighted_score, 2),
            "signals": signals,
            "message": message,
            "divergence": divergence
        }
    
    async def test_connection(self) -> bool:
        """Testa conexão com a API (inclui retry logic)."""
        try:
            price = await self.get_current_price()
            print(f"✅ Twelve Data Connection OK - {settings.trading_pair}: {price['price']}")
            return True
        except Exception as e:
            print(f"❌ Twelve Data Connection FAILED: {e}")
            return False


# Singleton
twelve_data_client = TwelveDataClient()
