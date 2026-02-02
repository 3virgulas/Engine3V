"""
Backtester Module - 3V Engine
Valida a estratégia usando dados históricos.

Features:
- Simula trades baseados nos sinais do QuantAnalyst
- Usa ATR para TP/SL dinâmicos
- Calcula métricas de performance (Win Rate, Profit Factor, Sharpe, etc.)
- Suporta Multi-Timeframe Analysis
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from utils.twelve_data import twelve_data_client
from utils.logger import log_agent_action
from core.config import settings


@dataclass
class Trade:
    """Representa um trade simulado."""
    entry_time: datetime
    exit_time: datetime | None = None
    direction: str = "BUY"  # BUY ou SELL
    entry_price: float = 0.0
    exit_price: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    pnl_pips: float = 0.0
    result: str = "OPEN"  # WIN, LOSS, OPEN
    signal_strength: int = 0
    reason: str = ""
    mtf_aligned: bool = False  # NEW: Trade aligned with higher TFs
    mtf_h1_trend: str = ""     # NEW: H1 trend at entry
    mtf_h4_trend: str = ""     # NEW: H4 trend at entry


@dataclass
class BacktestResult:
    """Resultado do backtest."""
    # Métricas principais
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    
    # Métricas de profit
    total_pips: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    profit_factor: float = 0.0
    
    # Métricas de risco
    max_drawdown_pips: float = 0.0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    
    # MTF Metrics (NEW!)
    mtf_enabled: bool = False
    mtf_aligned_trades: int = 0
    mtf_aligned_win_rate: float = 0.0
    trades_filtered_by_mtf: int = 0
    
    # Detalhes
    trades: list[Trade] = field(default_factory=list)
    period_start: str = ""
    period_end: str = ""
    timeframe: str = ""


class Backtester:
    """
    Backtester para validar a estratégia do 3V Engine.
    
    Usa a mesma lógica do QuantAnalyst para gerar sinais
    e simula trades com ATR-based TP/SL.
    """
    
    def __init__(self):
        self.name = "@Backtester"
        self.trades: list[Trade] = []
        
    def log(self, message: str, data: dict | None = None, level: str = "info"):
        """Log com estrutura padronizada."""
        log_agent_action(self.name, message, data, level)
    
    def _calculate_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        lookback: int = 20
    ) -> tuple[str, int, list[str]]:
        """
        Calcula sinal para uma barra específica.
        
        Replica a lógica do QuantAnalyst usando indicadores
        calculados no momento (sem lookahead bias).
        
        Args:
            df: DataFrame com dados OHLCV
            idx: Índice da barra atual
            lookback: Período para cálculo de indicadores
        
        Returns:
            Tuple (signal, confidence, reasons)
        """
        if idx < lookback + 14:  # Precisa de dados suficientes
            return "NEUTRAL", 0, []
        
        # Seleciona dados até a barra atual (sem lookahead)
        data = df.iloc[:idx+1].copy()
        
        # Calcula MAs
        data['MA20'] = data['close'].rolling(20).mean()
        data['MA50'] = data['close'].rolling(50).mean()
        
        # Calcula RSI
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # Valores atuais
        current_price = data['close'].iloc[-1]
        ma20 = data['MA20'].iloc[-1]
        ma50 = data['MA50'].iloc[-1]
        rsi = data['RSI'].iloc[-1]
        
        # Lógica de sinal (mesma do QuantAnalyst)
        score = 0
        reasons = []
        
        # MA20 vs MA50
        if ma20 > ma50:
            score += 2
            reasons.append("MA20>MA50")
        elif ma20 < ma50:
            score -= 2
            reasons.append("MA20<MA50")
        
        # Preço vs MA20
        if current_price > ma20:
            score += 2
            reasons.append("Price>MA20")
        elif current_price < ma20:
            score -= 2
            reasons.append("Price<MA20")
        
        # RSI
        if rsi > 60:
            score += 1
            reasons.append("RSI>60")
        elif rsi < 40:
            score -= 1
            reasons.append("RSI<40")
        
        # Determina sinal
        if score >= 2:
            signal = "BULLISH"
            confidence = min(50 + (score * 10), 90)
        elif score <= -2:
            signal = "BEARISH"
            confidence = min(50 + (abs(score) * 10), 90)
        else:
            signal = "NEUTRAL"
            confidence = 30
        
        return signal, confidence, reasons
    
    def _calculate_atr(self, df: pd.DataFrame, idx: int, period: int = 14) -> float:
        """
        Calcula ATR para uma barra específica.
        
        Args:
            df: DataFrame com dados OHLCV
            idx: Índice da barra atual
            period: Período do ATR
        
        Returns:
            Valor do ATR
        """
        if idx < period:
            # Usa volatilidade simples como fallback
            return (df['high'].iloc[:idx+1] - df['low'].iloc[:idx+1]).mean()
        
        data = df.iloc[:idx+1].copy()
        
        high = data['high']
        low = data['low']
        close = data['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else 0.001
    
    def _calculate_higher_tf_trend(self, df: pd.DataFrame) -> str:
        """
        Calcula tendência de um timeframe superior.
        
        Usa MA20 vs MA50 e Price vs MA20 para determinar tendência.
        
        Args:
            df: DataFrame com dados do TF superior
        
        Returns:
            "BULLISH", "BEARISH", ou "NEUTRAL"
        """
        if len(df) < 50:
            return "NEUTRAL"
        
        # Calcula MAs
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma50 = df['close'].rolling(50).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        score = 0
        
        # MA20 vs MA50
        if ma20 > ma50:
            score += 2
        elif ma20 < ma50:
            score -= 2
        
        # Price vs MA20
        if current_price > ma20:
            score += 1
        elif current_price < ma20:
            score -= 1
        
        if score >= 2:
            return "BULLISH"
        elif score <= -2:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _check_mtf_alignment(
        self,
        signal: str,
        h1_trend: str,
        h4_trend: str,
        require_both: bool = False
    ) -> tuple[bool, str]:
        """
        Verifica se sinal está alinhado com TFs superiores.
        
        Args:
            signal: Sinal do TF de entrada (BULLISH/BEARISH)
            h1_trend: Tendência do H1
            h4_trend: Tendência do H4
            require_both: Se True, exige ambos TFs alinhados
        
        Returns:
            Tuple (is_aligned, reason)
        """
        if signal == "NEUTRAL":
            return False, "Signal is NEUTRAL"
        
        expected_trend = signal  # BULLISH para BUY, BEARISH para SELL
        
        h1_aligned = h1_trend == expected_trend or h1_trend == "NEUTRAL"
        h4_aligned = h4_trend == expected_trend or h4_trend == "NEUTRAL"
        
        # H4 tem prioridade (mais forte)
        if h4_trend == expected_trend:
            if h1_aligned:
                return True, f"H4+H1 aligned ({h4_trend})"
            else:
                return True, f"H4 aligned ({h4_trend}), H1 divergent"
        
        if require_both:
            if h1_aligned and h4_aligned:
                return True, f"Both TFs neutral/aligned"
            return False, f"MTF not aligned (H1={h1_trend}, H4={h4_trend})"
        
        # Modo relaxado: aceita se H1 estiver alinhado E H4 não estiver contra
        if h1_trend == expected_trend and h4_trend != ("BEARISH" if expected_trend == "BULLISH" else "BULLISH"):
            return True, f"H1 aligned ({h1_trend}), H4 neutral"
        
        # Bloqueia se H4 estiver contra
        if h4_trend == ("BEARISH" if expected_trend == "BULLISH" else "BULLISH"):
            return False, f"H4 against signal ({h4_trend})"
        
        return False, f"No clear alignment (H1={h1_trend}, H4={h4_trend})"
    
    def _simulate_trade(
        self,
        df: pd.DataFrame,
        entry_idx: int,
        signal: str,
        atr: float
    ) -> Trade | None:
        """
        Simula um trade a partir do ponto de entrada.
        
        Args:
            df: DataFrame com dados OHLCV
            entry_idx: Índice da barra de entrada
            signal: BULLISH ou BEARISH
            atr: ATR no momento da entrada
        
        Returns:
            Trade simulado ou None se não houver dados suficientes
        """
        if entry_idx >= len(df) - 1:
            return None
        
        entry_price = df['close'].iloc[entry_idx]
        entry_time = df.index[entry_idx]
        
        # Calcula TP/SL baseado em ATR
        sl_distance = atr * 1.5
        tp_distance = atr * 2.5
        
        if signal == "BULLISH":
            direction = "BUY"
            take_profit = entry_price + tp_distance
            stop_loss = entry_price - sl_distance
        else:  # BEARISH
            direction = "SELL"
            take_profit = entry_price - tp_distance
            stop_loss = entry_price + sl_distance
        
        # Simula trade nas barras seguintes
        trade = Trade(
            entry_time=entry_time,
            direction=direction,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        # Procura por TP ou SL hit
        for i in range(entry_idx + 1, len(df)):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            
            if direction == "BUY":
                # Verifica SL primeiro (conservador)
                if low <= stop_loss:
                    trade.exit_time = df.index[i]
                    trade.exit_price = stop_loss
                    trade.pnl_pips = -(sl_distance * 10000)  # Negativo
                    trade.result = "LOSS"
                    break
                # Verifica TP
                elif high >= take_profit:
                    trade.exit_time = df.index[i]
                    trade.exit_price = take_profit
                    trade.pnl_pips = tp_distance * 10000  # Positivo
                    trade.result = "WIN"
                    break
            else:  # SELL
                # Verifica SL primeiro
                if high >= stop_loss:
                    trade.exit_time = df.index[i]
                    trade.exit_price = stop_loss
                    trade.pnl_pips = -(sl_distance * 10000)
                    trade.result = "LOSS"
                    break
                # Verifica TP
                elif low <= take_profit:
                    trade.exit_time = df.index[i]
                    trade.exit_price = take_profit
                    trade.pnl_pips = tp_distance * 10000
                    trade.result = "WIN"
                    break
        
        # Se trade ainda está aberto no final dos dados
        if trade.result == "OPEN":
            trade.exit_time = df.index[-1]
            trade.exit_price = df['close'].iloc[-1]
            if direction == "BUY":
                trade.pnl_pips = (trade.exit_price - entry_price) * 10000
            else:
                trade.pnl_pips = (entry_price - trade.exit_price) * 10000
            trade.result = "WIN" if trade.pnl_pips > 0 else "LOSS"
        
        return trade
    
    async def run_backtest(
        self,
        interval: str = "5min",
        outputsize: int = 500,
        min_signal_strength: int = 60
    ) -> BacktestResult:
        """
        Executa backtest completo.
        
        Args:
            interval: Timeframe (5min, 15min, 1h, 4h)
            outputsize: Número de candles a analisar
            min_signal_strength: Confiança mínima para entrar (0-100)
        
        Returns:
            BacktestResult com métricas e trades
        """
        self.log("Starting backtest", {
            "interval": interval,
            "outputsize": outputsize,
            "min_strength": min_signal_strength
        })
        
        # Busca dados históricos
        df = await twelve_data_client.get_price_data(
            interval=interval,
            outputsize=outputsize
        )
        
        self.log(f"Fetched {len(df)} candles for backtest")
        
        trades = []
        last_trade_idx = 0
        
        # Itera pelas barras (deixa espaço para simulação)
        for idx in range(50, len(df) - 10):  # Starts at 50 for indicator warmup
            # Pula se ainda há trade aberto
            if trades and trades[-1].result == "OPEN":
                continue
            
            # Pula se muito próximo do último trade
            if idx < last_trade_idx + 5:  # Mínimo 5 barras entre trades
                continue
            
            # Calcula sinal
            signal, confidence, reasons = self._calculate_signal(df, idx)
            
            # Filtra por força mínima
            if signal == "NEUTRAL" or confidence < min_signal_strength:
                continue
            
            # Calcula ATR
            atr = self._calculate_atr(df, idx)
            
            # Simula trade
            trade = self._simulate_trade(df, idx, signal, atr)
            
            if trade:
                trade.signal_strength = confidence
                trade.reason = ", ".join(reasons)
                trades.append(trade)
                last_trade_idx = idx
                
                self.log(f"Trade #{len(trades)}: {trade.direction} @ {trade.entry_price:.5f}", {
                    "result": trade.result,
                    "pnl_pips": round(trade.pnl_pips, 1)
                })
        
        # Calcula métricas
        result = self._calculate_metrics(trades, df, interval)
        
        self.log("Backtest complete", {
            "total_trades": result.total_trades,
            "win_rate": f"{result.win_rate:.1f}%",
            "total_pips": round(result.total_pips, 1),
            "profit_factor": round(result.profit_factor, 2)
        })
        
        return result
    
    async def run_backtest_with_mtf(
        self,
        interval: str = "5min",
        outputsize: int = 500,
        min_signal_strength: int = 60,
        require_both_tf: bool = False
    ) -> BacktestResult:
        """
        Executa backtest com filtro Multi-Timeframe.
        
        Busca dados de H1 e H4 para filtrar trades que não estão
        alinhados com a tendência de timeframes superiores.
        
        Args:
            interval: Timeframe de entrada (5min, 15min)
            outputsize: Número de candles a analisar
            min_signal_strength: Confiança mínima para entrar
            require_both_tf: Se True, exige H1 E H4 alinhados
        
        Returns:
            BacktestResult com métricas incluindo MTF stats
        """
        self.log("Starting MTF-filtered backtest", {
            "interval": interval,
            "outputsize": outputsize,
            "min_strength": min_signal_strength,
            "require_both_tf": require_both_tf
        })
        
        # Busca dados do timeframe de entrada
        df = await twelve_data_client.get_price_data(
            interval=interval,
            outputsize=outputsize
        )
        self.log(f"Fetched {len(df)} candles for {interval}")
        
        # Busca dados de H1 e H4
        df_h1 = await twelve_data_client.get_price_data(
            interval="1h",
            outputsize=200
        )
        self.log(f"Fetched {len(df_h1)} candles for H1")
        
        df_h4 = await twelve_data_client.get_price_data(
            interval="4h",
            outputsize=100
        )
        self.log(f"Fetched {len(df_h4)} candles for H4")
        
        # Calcula tendências de TFs superiores
        h1_trend = self._calculate_higher_tf_trend(df_h1)
        h4_trend = self._calculate_higher_tf_trend(df_h4)
        
        self.log("Higher TF trends calculated", {
            "H1": h1_trend,
            "H4": h4_trend
        })
        
        trades = []
        last_trade_idx = 0
        trades_filtered = 0
        
        # Itera pelas barras
        for idx in range(50, len(df) - 10):
            # Pula se ainda há trade aberto
            if trades and trades[-1].result == "OPEN":
                continue
            
            # Pula se muito próximo do último trade
            if idx < last_trade_idx + 5:
                continue
            
            # Calcula sinal
            signal, confidence, reasons = self._calculate_signal(df, idx)
            
            # Filtra por força mínima
            if signal == "NEUTRAL" or confidence < min_signal_strength:
                continue
            
            # FILTRO MTF: Verifica alinhamento com TFs superiores
            is_aligned, mtf_reason = self._check_mtf_alignment(
                signal=signal,
                h1_trend=h1_trend,
                h4_trend=h4_trend,
                require_both=require_both_tf
            )
            
            if not is_aligned:
                trades_filtered += 1
                self.log(f"Trade filtered by MTF: {signal} blocked - {mtf_reason}", level="debug")
                continue
            
            # Calcula ATR
            atr = self._calculate_atr(df, idx)
            
            # Simula trade
            trade = self._simulate_trade(df, idx, signal, atr)
            
            if trade:
                trade.signal_strength = confidence
                trade.reason = ", ".join(reasons) + f" | MTF: {mtf_reason}"
                trade.mtf_aligned = True
                trade.mtf_h1_trend = h1_trend
                trade.mtf_h4_trend = h4_trend
                trades.append(trade)
                last_trade_idx = idx
                
                self.log(f"Trade #{len(trades)}: {trade.direction} @ {trade.entry_price:.5f}", {
                    "result": trade.result,
                    "pnl_pips": round(trade.pnl_pips, 1),
                    "mtf_aligned": True
                })
        
        # Calcula métricas
        result = self._calculate_metrics(trades, df, interval)
        
        # Adiciona métricas MTF
        result.mtf_enabled = True
        result.mtf_aligned_trades = len([t for t in trades if t.mtf_aligned])
        result.trades_filtered_by_mtf = trades_filtered
        
        if result.mtf_aligned_trades > 0:
            aligned_wins = sum(1 for t in trades if t.mtf_aligned and t.result == "WIN")
            result.mtf_aligned_win_rate = (aligned_wins / result.mtf_aligned_trades) * 100
        
        self.log("MTF Backtest complete", {
            "total_trades": result.total_trades,
            "trades_filtered": trades_filtered,
            "win_rate": f"{result.win_rate:.1f}%",
            "h1_trend": h1_trend,
            "h4_trend": h4_trend,
            "total_pips": round(result.total_pips, 1),
            "profit_factor": round(result.profit_factor, 2)
        })
        
        return result
    
    def _calculate_metrics(
        self,
        trades: list[Trade],
        df: pd.DataFrame,
        interval: str
    ) -> BacktestResult:
        """
        Calcula métricas de performance.
        
        Args:
            trades: Lista de trades executados
            df: DataFrame original
            interval: Timeframe do backtest
        
        Returns:
            BacktestResult com todas as métricas
        """
        result = BacktestResult(
            trades=trades,
            period_start=str(df.index[0]) if len(df) > 0 else "",
            period_end=str(df.index[-1]) if len(df) > 0 else "",
            timeframe=interval
        )
        
        if not trades:
            return result
        
        # Métricas básicas
        result.total_trades = len(trades)
        result.wins = sum(1 for t in trades if t.result == "WIN")
        result.losses = sum(1 for t in trades if t.result == "LOSS")
        result.win_rate = (result.wins / result.total_trades) * 100 if result.total_trades > 0 else 0
        
        # Métricas de profit
        result.total_pips = sum(t.pnl_pips for t in trades)
        
        winning_trades = [t for t in trades if t.result == "WIN"]
        losing_trades = [t for t in trades if t.result == "LOSS"]
        
        if winning_trades:
            result.avg_win_pips = sum(t.pnl_pips for t in winning_trades) / len(winning_trades)
        
        if losing_trades:
            result.avg_loss_pips = abs(sum(t.pnl_pips for t in losing_trades) / len(losing_trades))
        
        # Profit Factor
        gross_profit = sum(t.pnl_pips for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl_pips for t in losing_trades)) if losing_trades else 0
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max Drawdown
        cumulative = 0
        peak = 0
        drawdown = 0
        
        for trade in trades:
            cumulative += trade.pnl_pips
            if cumulative > peak:
                peak = cumulative
            current_dd = peak - cumulative
            if current_dd > drawdown:
                drawdown = current_dd
        
        result.max_drawdown_pips = drawdown
        
        # Max Consecutive Losses
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.result == "LOSS":
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        result.max_consecutive_losses = max_consecutive
        
        # Sharpe Ratio (simplificado)
        if len(trades) > 1:
            pnl_array = np.array([t.pnl_pips for t in trades])
            avg_return = pnl_array.mean()
            std_return = pnl_array.std()
            result.sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        
        return result
    
    def generate_report(self, result: BacktestResult) -> str:
        """
        Gera relatório formatado do backtest.
        
        Args:
            result: Resultado do backtest
        
        Returns:
            String formatada com o relatório
        """
        report = []
        report.append("=" * 60)
        report.append("📊 3V ENGINE BACKTEST REPORT")
        report.append("=" * 60)
        report.append(f"Period: {result.period_start[:10]} to {result.period_end[:10]}")
        report.append(f"Timeframe: {result.timeframe}")
        report.append("-" * 60)
        
        # Performance Overview
        report.append("\n📈 PERFORMANCE OVERVIEW")
        report.append(f"  Total Trades: {result.total_trades}")
        report.append(f"  Wins/Losses: {result.wins}/{result.losses}")
        report.append(f"  Win Rate: {result.win_rate:.1f}%")
        report.append(f"  Total P&L: {result.total_pips:+.1f} pips")
        
        # MTF Metrics (NEW!)
        if result.mtf_enabled:
            report.append("\n🔄 MULTI-TIMEFRAME ANALYSIS")
            report.append(f"  MTF Filter: ENABLED")
            report.append(f"  Trades Filtered by MTF: {result.trades_filtered_by_mtf}")
            report.append(f"  MTF-Aligned Trades: {result.mtf_aligned_trades}")
            report.append(f"  MTF-Aligned Win Rate: {result.mtf_aligned_win_rate:.1f}%")
            if result.trades and result.trades[0].mtf_h4_trend:
                report.append(f"  H4 Trend: {result.trades[0].mtf_h4_trend}")
                report.append(f"  H1 Trend: {result.trades[0].mtf_h1_trend}")
        
        # Risk Metrics
        report.append("\n⚠️ RISK METRICS")
        report.append(f"  Profit Factor: {result.profit_factor:.2f}")
        report.append(f"  Avg Win: {result.avg_win_pips:.1f} pips")
        report.append(f"  Avg Loss: {result.avg_loss_pips:.1f} pips")
        report.append(f"  Max Drawdown: {result.max_drawdown_pips:.1f} pips")
        report.append(f"  Max Consecutive Losses: {result.max_consecutive_losses}")
        report.append(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        
        # Trade Details
        if result.trades:
            report.append("\n📋 TRADE DETAILS (Last 10)")
            report.append("-" * 60)
            for trade in result.trades[-10:]:
                emoji = "✅" if trade.result == "WIN" else "❌"
                report.append(
                    f"  {emoji} {trade.direction} @ {trade.entry_price:.5f} → "
                    f"{trade.exit_price:.5f} | {trade.pnl_pips:+.1f} pips | "
                    f"{trade.reason}"
                )
        
        # Evaluation
        report.append("\n" + "=" * 60)
        report.append("📊 STRATEGY EVALUATION")
        
        if result.win_rate >= 55 and result.profit_factor >= 1.5:
            report.append("  ✅ STRATEGY APPROVED - Ready for live trading")
            report.append(f"     Win Rate {result.win_rate:.0f}% > 55% threshold")
            report.append(f"     Profit Factor {result.profit_factor:.2f} > 1.5 threshold")
        elif result.win_rate >= 50 and result.profit_factor >= 1.2:
            report.append("  ⚠️ STRATEGY ACCEPTABLE - Needs optimization")
            report.append("     Consider adjusting ATR multipliers or signal filters")
        else:
            report.append("  ❌ STRATEGY NEEDS WORK - Not ready for live")
            report.append("     Review signal logic and risk parameters")
        
        report.append("=" * 60)
        
        return "\n".join(report)


# Singleton
backtester = Backtester()


async def run_quick_backtest():
    """Função utilitária para rodar backtest rápido."""
    result = await backtester.run_backtest(
        interval="5min",
        outputsize=500,
        min_signal_strength=60
    )
    print(backtester.generate_report(result))
    return result


# CLI
if __name__ == "__main__":
    asyncio.run(run_quick_backtest())
