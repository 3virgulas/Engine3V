"""
Multi-Pair Scanner - 3V Engine
==============================
Scanner inteligente para múltiplos pares de moedas.

Features:
- Suporta 8 pares principais do Forex
- Analisa todos os pares em paralelo
- Rankeia oportunidades por força do sinal
- Filtra por MTF alignment e volatilidade
- Detecta divergências entre moedas correlacionadas
"""
import asyncio
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

from utils.twelve_data import twelve_data_client
from utils.logger import log_agent_action


class CurrencyPair(str, Enum):
    """8 principais pares de Forex."""
    EURUSD = "EUR/USD"
    GBPUSD = "GBP/USD"
    USDJPY = "USD/JPY"
    USDCHF = "USD/CHF"
    AUDUSD = "AUD/USD"
    USDCAD = "USD/CAD"
    NZDUSD = "NZD/USD"
    EURGBP = "EUR/GBP"


# Correlações entre pares (positiva ou negativa)
PAIR_CORRELATIONS = {
    "EUR/USD": {"positive": ["GBP/USD", "AUD/USD", "NZD/USD"], "negative": ["USD/CHF", "USD/JPY", "USD/CAD"]},
    "GBP/USD": {"positive": ["EUR/USD", "AUD/USD"], "negative": ["USD/CHF", "USD/JPY"]},
    "USD/JPY": {"positive": ["USD/CHF", "USD/CAD"], "negative": ["EUR/USD", "GBP/USD"]},
    "USD/CHF": {"positive": ["USD/JPY", "USD/CAD"], "negative": ["EUR/USD", "GBP/USD"]},
    "AUD/USD": {"positive": ["NZD/USD", "EUR/USD"], "negative": ["USD/CAD"]},
    "USD/CAD": {"positive": ["USD/JPY", "USD/CHF"], "negative": ["AUD/USD", "NZD/USD"]},
    "NZD/USD": {"positive": ["AUD/USD", "EUR/USD"], "negative": ["USD/CAD"]},
    "EUR/GBP": {"positive": [], "negative": []}
}


@dataclass
class PairSignal:
    """Sinal de um par específico."""
    pair: str
    direction: str  # BUY, SELL, NEUTRAL
    strength: int  # 0-100
    
    # Indicadores
    price: float = 0.0
    rsi: float = 50.0
    trend: str = "NEUTRAL"
    trend_score: int = 0
    
    # MTF
    mtf_h1_trend: str = "NEUTRAL"
    mtf_h4_trend: str = "NEUTRAL"
    mtf_aligned: bool = False
    
    # Volatilidade
    atr_pips: float = 0.0
    volatility: str = "NORMAL"
    
    # Níveis sugeridos
    entry_price: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    risk_reward: float = 0.0
    
    # Reasoning
    reasons: list[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class ScannerResult:
    """Resultado do scan de múltiplos pares."""
    timestamp: str
    pairs_scanned: int = 0
    
    # Top oportunidades
    best_opportunity: PairSignal | None = None
    top_3_opportunities: list[PairSignal] = field(default_factory=list)
    
    # Todas as análises
    all_signals: dict[str, PairSignal] = field(default_factory=dict)
    
    # Análise de correlação
    correlation_warnings: list[str] = field(default_factory=list)
    usd_sentiment: str = "NEUTRAL"  # Agregado de sinais USD
    
    # Estatísticas
    bullish_pairs: list[str] = field(default_factory=list)
    bearish_pairs: list[str] = field(default_factory=list)
    neutral_pairs: list[str] = field(default_factory=list)


class MultiPairScanner:
    """
    Scanner inteligente para múltiplos pares de Forex.
    
    Analisa os 8 pares principais em paralelo e identifica
    as melhores oportunidades de trading baseado em:
    - Força do sinal técnico
    - Alinhamento MTF
    - Volatilidade adequada
    - Correlações inter-pares
    """
    
    # Configurações
    DEFAULT_PAIRS = [p.value for p in CurrencyPair]
    MIN_SIGNAL_STRENGTH = 60  # Mínimo para considerar oportunidade
    
    def __init__(self):
        self.name = "@MultiPairScanner"
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 180  # 3 minutos
        
    def log(self, message: str, data: dict | None = None, level: str = "info"):
        """Log com estrutura padronizada."""
        log_agent_action(self.name, message, data, level)
    
    async def scan_pair(self, pair: str) -> PairSignal:
        """
        Analisa um par específico.
        
        Args:
            pair: Par de moedas (ex: EUR/USD)
        
        Returns:
            PairSignal com análise completa
        """
        try:
            # TwelveData aceita EUR/USD (com barra)
            symbol = pair if "/" in pair else f"{pair[:3]}/{pair[3:]}"
            
            # Busca dados técnicos
            technical = await twelve_data_client.get_technical_analysis(symbol=symbol)
            
            # Extrai indicadores
            rsi_data = technical.get("rsi", {})
            ma_data = technical.get("moving_averages", {})
            bb_data = technical.get("bollinger_bands", {})
            atr_data = technical.get("atr", {})
            
            current_price = technical.get("price", 0)
            rsi = rsi_data.get("value", 50)
            trend = ma_data.get("trend", "NEUTRAL")
            trend_score = ma_data.get("trend_score", 0)
            
            # Determina direção e força
            direction = "NEUTRAL"
            strength = 0
            reasons = []
            
            # RSI Analysis
            rsi_condition = rsi_data.get("condition", "NEUTRAL")
            if rsi_condition == "OVERSOLD":
                strength += 20
                direction = "BUY"
                reasons.append(f"RSI Oversold ({rsi:.0f})")
            elif rsi_condition == "OVERBOUGHT":
                strength += 20
                direction = "SELL"
                reasons.append(f"RSI Overbought ({rsi:.0f})")
            
            # Trend Analysis
            if abs(trend_score) >= 3:
                strength += 25
                if trend == "BULLISH":
                    direction = "BUY"
                    reasons.append(f"Strong Bullish Trend (score: {trend_score})")
                elif trend == "BEARISH":
                    direction = "SELL"
                    reasons.append(f"Strong Bearish Trend (score: {trend_score})")
            elif abs(trend_score) >= 2:
                strength += 15
                if trend != "NEUTRAL":
                    reasons.append(f"Moderate {trend} Trend")
            
            # Bollinger Bands
            bb_position = bb_data.get("position", "MIDDLE")
            if bb_position == "LOWER" and direction != "SELL":
                strength += 15
                direction = "BUY" if direction == "NEUTRAL" else direction
                reasons.append("Price at Lower BB")
            elif bb_position == "UPPER" and direction != "BUY":
                strength += 15
                direction = "SELL" if direction == "NEUTRAL" else direction
                reasons.append("Price at Upper BB")
            
            # MA Cross Signals
            ma_signals = ma_data.get("signals", [])
            if ma_signals:
                for signal in ma_signals[:2]:
                    strength += 10
                    reasons.append(signal)
            
            # Busca MTF (H1 e H4)
            mtf_h1_trend = "NEUTRAL"
            mtf_h4_trend = "NEUTRAL"
            
            try:
                # H1
                h1_data = await twelve_data_client.get_technical_analysis(
                    symbol=symbol, interval="1h", outputsize=50
                )
                mtf_h1_trend = h1_data.get("moving_averages", {}).get("trend", "NEUTRAL")
                
                # H4
                h4_data = await twelve_data_client.get_technical_analysis(
                    symbol=symbol, interval="4h", outputsize=50
                )
                mtf_h4_trend = h4_data.get("moving_averages", {}).get("trend", "NEUTRAL")
            except Exception:
                pass  # MTF opcional
            
            # Verifica alinhamento MTF
            expected_trend = "BULLISH" if direction == "BUY" else "BEARISH" if direction == "SELL" else "NEUTRAL"
            mtf_aligned = False
            
            if expected_trend != "NEUTRAL":
                if mtf_h4_trend == expected_trend:
                    mtf_aligned = True
                    strength += 20
                    reasons.append(f"H4 aligned ({mtf_h4_trend})")
                elif mtf_h4_trend == "NEUTRAL" and mtf_h1_trend == expected_trend:
                    mtf_aligned = True
                    strength += 10
                    reasons.append(f"H1 aligned ({mtf_h1_trend})")
                elif mtf_h4_trend != "NEUTRAL" and mtf_h4_trend != expected_trend:
                    strength -= 15  # Penalidade por divergência
                    reasons.append(f"⚠️ H4 divergent ({mtf_h4_trend})")
            
            # ATR e Volatilidade
            atr_pips = atr_data.get("atr_pips", 0)
            volatility = atr_data.get("volatility", "NORMAL")
            
            # Calcula TP/SL baseado em ATR
            pip_value = 0.0001 if "JPY" not in pair else 0.01
            atr_value = atr_data.get("atr", 0)
            
            if direction == "BUY":
                entry_price = current_price
                stop_loss = current_price - (atr_value * 1.5)
                take_profit = current_price + (atr_value * 2.5)
            elif direction == "SELL":
                entry_price = current_price
                stop_loss = current_price + (atr_value * 1.5)
                take_profit = current_price - (atr_value * 2.5)
            else:
                entry_price = current_price
                stop_loss = 0
                take_profit = 0
            
            # Risk/Reward
            if stop_loss and take_profit and entry_price:
                sl_distance = abs(entry_price - stop_loss)
                tp_distance = abs(take_profit - entry_price)
                risk_reward = tp_distance / sl_distance if sl_distance > 0 else 0
            else:
                risk_reward = 0
            
            # Limita strength a 100
            strength = max(0, min(100, strength))
            
            return PairSignal(
                pair=pair,
                direction=direction,
                strength=strength,
                price=current_price,
                rsi=rsi,
                trend=trend,
                trend_score=trend_score,
                mtf_h1_trend=mtf_h1_trend,
                mtf_h4_trend=mtf_h4_trend,
                mtf_aligned=mtf_aligned,
                atr_pips=atr_pips,
                volatility=volatility,
                entry_price=entry_price,
                take_profit=take_profit,
                stop_loss=stop_loss,
                risk_reward=round(risk_reward, 2),
                reasons=reasons,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.log(f"Error scanning {pair}: {e}", level="warning")
            return PairSignal(
                pair=pair,
                direction="ERROR",
                strength=0,
                reasons=[f"Scan error: {str(e)}"],
                timestamp=datetime.now().isoformat()
            )
    
    async def scan_all_pairs(
        self,
        pairs: list[str] | None = None,
        min_strength: int = 60
    ) -> ScannerResult:
        """
        Scanneia todos os pares em paralelo.
        
        Args:
            pairs: Lista de pares (default: 8 principais)
            min_strength: Força mínima para considerar oportunidade
        
        Returns:
            ScannerResult com análise completa
        """
        if pairs is None:
            pairs = self.DEFAULT_PAIRS
        
        self.log(f"Scanning {len(pairs)} pairs", {"pairs": pairs})
        
        # Scan paralelo
        tasks = [self.scan_pair(pair) for pair in pairs]
        signals = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processa resultados
        result = ScannerResult(
            timestamp=datetime.now().isoformat(),
            pairs_scanned=len(pairs)
        )
        
        valid_signals: list[PairSignal] = []
        
        for signal in signals:
            if isinstance(signal, Exception):
                continue
            if isinstance(signal, PairSignal):
                result.all_signals[signal.pair] = signal
                
                if signal.direction == "BUY":
                    result.bullish_pairs.append(signal.pair)
                elif signal.direction == "SELL":
                    result.bearish_pairs.append(signal.pair)
                else:
                    result.neutral_pairs.append(signal.pair)
                
                if signal.strength >= min_strength and signal.direction != "NEUTRAL":
                    valid_signals.append(signal)
        
        # Ordena por força
        valid_signals.sort(key=lambda x: x.strength, reverse=True)
        
        # Top 3 oportunidades
        result.top_3_opportunities = valid_signals[:3]
        if valid_signals:
            result.best_opportunity = valid_signals[0]
        
        # Análise USD
        result.usd_sentiment = self._analyze_usd_sentiment(result.all_signals)
        
        # Warnings de correlação
        result.correlation_warnings = self._check_correlations(result.all_signals)
        
        self.log("Scan complete", {
            "bullish": len(result.bullish_pairs),
            "bearish": len(result.bearish_pairs),
            "neutral": len(result.neutral_pairs),
            "opportunities": len(valid_signals),
            "best": result.best_opportunity.pair if result.best_opportunity else "None"
        })
        
        return result
    
    def _analyze_usd_sentiment(self, signals: dict[str, PairSignal]) -> str:
        """
        Analisa sentimento geral do USD baseado nos pares.
        
        Se USD é base (USD/XXX) e BUY = USD forte
        Se USD é quote (XXX/USD) e SELL = USD forte
        """
        usd_strong = 0
        usd_weak = 0
        
        for pair, signal in signals.items():
            if signal.direction == "NEUTRAL":
                continue
            
            # USD como base (USD/JPY, USD/CHF, USD/CAD)
            if pair.startswith("USD"):
                if signal.direction == "BUY":
                    usd_strong += signal.strength
                else:
                    usd_weak += signal.strength
            
            # USD como quote (EUR/USD, GBP/USD, AUD/USD, NZD/USD)
            elif pair.endswith("USD"):
                if signal.direction == "SELL":
                    usd_strong += signal.strength
                else:
                    usd_weak += signal.strength
        
        diff = usd_strong - usd_weak
        
        if diff > 100:
            return "STRONG_USD"
        elif diff > 50:
            return "BULLISH_USD"
        elif diff < -100:
            return "WEAK_USD"
        elif diff < -50:
            return "BEARISH_USD"
        return "NEUTRAL"
    
    def _check_correlations(self, signals: dict[str, PairSignal]) -> list[str]:
        """
        Verifica divergências em pares correlacionados.
        
        Se EUR/USD é BUY e USD/CHF também é BUY, há divergência
        (eles deveriam ser opostos).
        """
        warnings = []
        
        for pair, signal in signals.items():
            if signal.direction == "NEUTRAL" or pair not in PAIR_CORRELATIONS:
                continue
            
            correlations = PAIR_CORRELATIONS[pair]
            
            # Verifica pares positivamente correlacionados
            for corr_pair in correlations.get("positive", []):
                if corr_pair in signals:
                    corr_signal = signals[corr_pair]
                    if corr_signal.direction != "NEUTRAL" and corr_signal.direction != signal.direction:
                        warnings.append(
                            f"⚠️ {pair} ({signal.direction}) vs {corr_pair} ({corr_signal.direction}) - "
                            f"Expected same direction (positive correlation)"
                        )
            
            # Verifica pares negativamente correlacionados
            for corr_pair in correlations.get("negative", []):
                if corr_pair in signals:
                    corr_signal = signals[corr_pair]
                    if corr_signal.direction != "NEUTRAL" and corr_signal.direction == signal.direction:
                        warnings.append(
                            f"⚠️ {pair} ({signal.direction}) and {corr_pair} ({corr_signal.direction}) - "
                            f"Expected opposite direction (negative correlation)"
                        )
        
        # Remove duplicatas
        return list(set(warnings))
    
    def generate_report(self, result: ScannerResult) -> str:
        """
        Gera relatório formatado do scan.
        
        Args:
            result: Resultado do scan
        
        Returns:
            String formatada com o relatório
        """
        lines = [
            "=" * 60,
            "🔍 MULTI-PAIR SCANNER REPORT",
            "=" * 60,
            f"Timestamp: {result.timestamp[:19]}",
            f"Pairs Scanned: {result.pairs_scanned}",
            f"USD Sentiment: {result.usd_sentiment}",
            "-" * 60
        ]
        
        # Top oportunidades
        lines.append("\n🎯 TOP OPPORTUNITIES")
        if result.top_3_opportunities:
            for i, opp in enumerate(result.top_3_opportunities, 1):
                mtf_icon = "✅" if opp.mtf_aligned else "⚠️"
                lines.append(
                    f"  {i}. {opp.pair} | {opp.direction} | Strength: {opp.strength}% {mtf_icon}"
                )
                lines.append(f"     Price: {opp.price:.5f} | RR: 1:{opp.risk_reward}")
                lines.append(f"     TP: {opp.take_profit:.5f} | SL: {opp.stop_loss:.5f}")
                lines.append(f"     Reasons: {', '.join(opp.reasons[:3])}")
                lines.append("")
        else:
            lines.append("  No strong opportunities found")
        
        # Resumo por direção
        lines.append("-" * 60)
        lines.append("📊 MARKET SUMMARY")
        lines.append(f"  🟢 Bullish ({len(result.bullish_pairs)}): {', '.join(result.bullish_pairs) or 'None'}")
        lines.append(f"  🔴 Bearish ({len(result.bearish_pairs)}): {', '.join(result.bearish_pairs) or 'None'}")
        lines.append(f"  ⚪ Neutral ({len(result.neutral_pairs)}): {', '.join(result.neutral_pairs) or 'None'}")
        
        # Warnings
        if result.correlation_warnings:
            lines.append("")
            lines.append("⚠️ CORRELATION WARNINGS")
            for warning in result.correlation_warnings[:3]:
                lines.append(f"  {warning}")
        
        # Tabela completa
        lines.append("")
        lines.append("-" * 60)
        lines.append("📋 ALL PAIRS")
        lines.append(f"{'Pair':<10} {'Dir':<6} {'Str':<5} {'RSI':<5} {'Trend':<10} {'MTF H4':<10}")
        lines.append("-" * 60)
        
        for pair in self.DEFAULT_PAIRS:
            if pair in result.all_signals:
                s = result.all_signals[pair]
                dir_icon = "🟢" if s.direction == "BUY" else "🔴" if s.direction == "SELL" else "⚪"
                lines.append(
                    f"{pair:<10} {dir_icon}{s.direction:<4} {s.strength:<5} {s.rsi:<5.0f} {s.trend:<10} {s.mtf_h4_trend:<10}"
                )
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Singleton
multi_pair_scanner = MultiPairScanner()
