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
        
        # Sinal de tendência
        if all(result.get(f"MA_{p}") for p in periods):
            ma20, ma50, ma200 = result["MA_20"], result["MA_50"], result["MA_200"]
            if ma20 > ma50 > ma200:
                result["trend"] = "BULLISH"
            elif ma20 < ma50 < ma200:
                result["trend"] = "BEARISH"
            else:
                result["trend"] = "NEUTRAL"
        
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
        
        return {"rsi": current_rsi, "zone": zone}
    
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
    
    async def get_technical_analysis(self) -> dict[str, Any]:
        """
        Executa análise técnica completa para o @Quant_Analyst.
        
        Returns:
            Dict com todos os indicadores e padrões
        """
        log_agent_action("@TwelveData", "Running full technical analysis")
        
        # Obtém dados de preço
        df = await self.get_price_data(interval="5min", outputsize=200)
        current_price = df["close"].iloc[-1]
        
        # Calcula indicadores
        moving_averages = self.calculate_moving_averages(df)
        rsi = self.calculate_rsi(df)
        bollinger = self.calculate_bollinger_bands(df)
        patterns = self.identify_candlestick_patterns(df)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "symbol": settings.trading_pair,
            "current_price": round(current_price, 5),
            "moving_averages": moving_averages,
            "rsi": rsi,
            "bollinger_bands": bollinger,
            "candlestick_patterns": patterns,
            "candles_analyzed": len(df)
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
