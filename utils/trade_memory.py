"""
Trade Memory Module - 3V Engine
Aprende com histórico de trades para melhorar decisões futuras.

Features:
- Armazena contexto de cada trade (indicadores, MTF, volatilidade)
- Analisa padrões de trades vencedores vs perdedores
- Fornece insights estatísticos para o RiskCommander
- Detecta condições de mercado favoráveis/desfavoráveis
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field

from core.supabase_client import supabase_client
from utils.logger import log_agent_action


@dataclass
class TradeContext:
    """Contexto completo de um trade para análise."""
    # Identificação
    ticket: str
    symbol: str
    timestamp: datetime
    
    # Trade info
    direction: str  # BUY or SELL
    entry_price: float
    exit_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Resultado
    status: str = "OPEN"  # OPEN, WIN, LOSS
    profit_pips: float = 0.0
    
    # Indicadores no momento da entrada
    rsi: float = 50.0
    trend: str = "NEUTRAL"
    trend_score: int = 0
    bb_position: str = "MIDDLE"
    volatility: str = "NORMAL"
    atr_pips: float = 0.0
    
    # Multi-Timeframe
    mtf_h1_trend: str = "NEUTRAL"
    mtf_h4_trend: str = "NEUTRAL"
    mtf_confluence: float = 0.0
    
    # Hora/Dia
    hour: int = 0
    weekday: int = 0  # 0=Monday, 6=Sunday


@dataclass
class TradingInsights:
    """Insights derivados da análise de trades históricos."""
    # Estatísticas gerais
    total_trades: int = 0
    win_rate: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    profit_factor: float = 0.0
    
    # Melhores/piores condições
    best_hour: int = 0
    best_hour_win_rate: float = 0.0
    worst_hour: int = 0
    worst_hour_win_rate: float = 0.0
    
    best_volatility: str = "NORMAL"
    best_volatility_win_rate: float = 0.0
    
    # MTF insights
    mtf_aligned_win_rate: float = 0.0
    mtf_divergent_win_rate: float = 0.0
    
    # RSI insights
    best_rsi_range: tuple[int, int] = (40, 60)
    
    # Recomendações
    recommendations: list[str] = field(default_factory=list)
    avoid_conditions: list[str] = field(default_factory=list)
    
    # Confiança nos insights
    confidence: float = 0.0  # 0-100, baseado em sample size


class TradeMemory:
    """
    Sistema de memória de trades para aprendizado contínuo.
    
    Analisa trades históricos para identificar padrões de sucesso
    e fornece insights para melhorar decisões futuras.
    """
    
    def __init__(self):
        self.name = "@TradeMemory"
        self.cache_ttl = 300  # 5 minutos
        self._insights_cache: TradingInsights | None = None
        self._cache_timestamp: datetime | None = None
        
    def log(self, message: str, data: dict | None = None, level: str = "info"):
        """Log com estrutura padronizada."""
        log_agent_action(self.name, message, data, level)
    
    async def save_trade_context(
        self,
        ticket: str,
        trade_data: dict[str, Any],
        indicators: dict[str, Any],
        mtf_data: dict[str, Any] | None = None
    ) -> bool:
        """
        Salva contexto completo do trade para análise futura.
        
        Args:
            ticket: ID do trade no MT5/Simulation
            trade_data: Dados básicos do trade
            indicators: Indicadores técnicos no momento
            mtf_data: Dados de Multi-Timeframe
        
        Returns:
            True se salvou com sucesso
        """
        try:
            now = datetime.now()
            
            context = {
                "ticket": ticket,
                "symbol": trade_data.get("symbol", "EURUSD"),
                "direction": trade_data.get("direction"),
                "entry_price": trade_data.get("price"),
                "stop_loss": trade_data.get("stop_loss"),
                "take_profit": trade_data.get("take_profit"),
                
                # Indicadores
                "rsi": indicators.get("rsi", 50),
                "trend": indicators.get("trend", "NEUTRAL"),
                "trend_score": indicators.get("trend_score", 0),
                "bb_position": indicators.get("bb_position", "MIDDLE"),
                "volatility": indicators.get("volatility", "NORMAL"),
                "atr_pips": indicators.get("atr_pips", 0),
                
                # MTF
                "mtf_h1_trend": mtf_data.get("h1_trend", "NEUTRAL") if mtf_data else "NEUTRAL",
                "mtf_h4_trend": mtf_data.get("h4_trend", "NEUTRAL") if mtf_data else "NEUTRAL",
                "mtf_confluence": mtf_data.get("confluence_score", 0) if mtf_data else 0,
                
                # Temporal
                "entry_hour": now.hour,
                "entry_weekday": now.weekday(),
                "timestamp": now.isoformat()
            }
            
            # Atualiza o trade com contexto
            supabase_client.client.table("execution_log") \
                .update({"context": context}) \
                .eq("ticket", ticket) \
                .execute()
            
            self.log(f"Trade context saved for ticket {ticket}")
            return True
            
        except Exception as e:
            self.log(f"Failed to save trade context: {e}", level="error")
            return False
    
    async def get_historical_trades(
        self,
        days: int = 30,
        status_filter: str | None = None,
        limit: int = 500
    ) -> list[dict[str, Any]]:
        """
        Busca trades históricos do Supabase.
        
        Args:
            days: Número de dias para buscar
            status_filter: Filtrar por status (WIN, LOSS, etc.)
            limit: Máximo de registros
        
        Returns:
            Lista de trades com contexto
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = supabase_client.client.table("execution_log") \
                .select("*") \
                .eq("type", "TRADE") \
                .gte("created_at", cutoff_date) \
                .order("created_at", desc=True) \
                .limit(limit)
            
            if status_filter:
                query = query.eq("status", status_filter)
            
            result = query.execute()
            
            trades = result.data or []
            self.log(f"Fetched {len(trades)} historical trades", {"days": days})
            
            return trades
            
        except Exception as e:
            self.log(f"Failed to fetch historical trades: {e}", level="error")
            return []
    
    async def analyze_patterns(
        self,
        trades: list[dict[str, Any]] | None = None,
        days: int = 30
    ) -> TradingInsights:
        """
        Analisa padrões nos trades históricos.
        
        Identifica:
        - Melhores/piores horários
        - Melhores condições de volatilidade
        - Impacto do MTF alignment
        - Padrões de RSI
        
        Args:
            trades: Lista de trades (ou busca automaticamente)
            days: Dias para análise se trades não for fornecido
        
        Returns:
            TradingInsights com estatísticas e recomendações
        """
        # Verifica cache
        if self._insights_cache and self._cache_timestamp:
            cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
            if cache_age < self.cache_ttl:
                self.log("Using cached insights")
                return self._insights_cache
        
        if trades is None:
            trades = await self.get_historical_trades(days=days)
        
        if not trades:
            return TradingInsights(
                recommendations=["Insufficient trade history for analysis"],
                confidence=0
            )
        
        insights = TradingInsights()
        
        # Filtra trades válidos (WIN ou LOSS)
        completed_trades = [
            t for t in trades 
            if t.get("status") in ["WIN", "LOSS", "CLOSED"]
        ]
        
        if not completed_trades:
            insights.recommendations = ["No completed trades for analysis"]
            insights.confidence = 0
            return insights
        
        insights.total_trades = len(completed_trades)
        
        # Classifica WIN/LOSS baseado no profit
        wins = [t for t in completed_trades if float(t.get("profit", 0)) > 0]
        losses = [t for t in completed_trades if float(t.get("profit", 0)) <= 0]
        
        # Win rate geral
        insights.win_rate = (len(wins) / len(completed_trades)) * 100 if completed_trades else 0
        
        # Avg win/loss
        if wins:
            insights.avg_win_pips = sum(float(t.get("profit", 0)) for t in wins) / len(wins)
        if losses:
            insights.avg_loss_pips = abs(sum(float(t.get("profit", 0)) for t in losses) / len(losses))
        
        # Profit Factor
        gross_profit = sum(float(t.get("profit", 0)) for t in wins) if wins else 0
        gross_loss = abs(sum(float(t.get("profit", 0)) for t in losses)) if losses else 0
        insights.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Análise por hora
        hourly_stats = self._analyze_by_hour(completed_trades)
        if hourly_stats:
            best = max(hourly_stats.items(), key=lambda x: x[1]["win_rate"])
            worst = min(hourly_stats.items(), key=lambda x: x[1]["win_rate"])
            insights.best_hour = best[0]
            insights.best_hour_win_rate = best[1]["win_rate"]
            insights.worst_hour = worst[0]
            insights.worst_hour_win_rate = worst[1]["win_rate"]
        
        # Análise por volatilidade
        volatility_stats = self._analyze_by_volatility(completed_trades)
        if volatility_stats:
            best_vol = max(volatility_stats.items(), key=lambda x: x[1]["win_rate"])
            insights.best_volatility = best_vol[0]
            insights.best_volatility_win_rate = best_vol[1]["win_rate"]
        
        # Análise MTF
        mtf_stats = self._analyze_mtf_alignment(completed_trades)
        insights.mtf_aligned_win_rate = mtf_stats.get("aligned_win_rate", 0)
        insights.mtf_divergent_win_rate = mtf_stats.get("divergent_win_rate", 0)
        
        # Gera recomendações
        insights.recommendations = self._generate_recommendations(insights, hourly_stats, volatility_stats)
        insights.avoid_conditions = self._generate_avoid_conditions(insights, hourly_stats, volatility_stats)
        
        # Confiança baseada em sample size
        if insights.total_trades >= 100:
            insights.confidence = 90
        elif insights.total_trades >= 50:
            insights.confidence = 75
        elif insights.total_trades >= 20:
            insights.confidence = 50
        else:
            insights.confidence = 25
        
        # Cache
        self._insights_cache = insights
        self._cache_timestamp = datetime.now()
        
        self.log("Pattern analysis complete", {
            "total_trades": insights.total_trades,
            "win_rate": f"{insights.win_rate:.1f}%",
            "confidence": insights.confidence
        })
        
        return insights
    
    def _analyze_by_hour(self, trades: list[dict]) -> dict[int, dict]:
        """Analisa trades por hora de entrada."""
        hourly = {}
        
        for trade in trades:
            context = trade.get("context", {})
            if not context:
                # Fallback: usa created_at
                created = trade.get("created_at", "")
                if created:
                    try:
                        hour = datetime.fromisoformat(created.replace("Z", "+00:00")).hour
                    except:
                        continue
                else:
                    continue
            else:
                hour = context.get("entry_hour", 0)
            
            if hour not in hourly:
                hourly[hour] = {"wins": 0, "losses": 0, "total": 0}
            
            hourly[hour]["total"] += 1
            if float(trade.get("profit", 0)) > 0:
                hourly[hour]["wins"] += 1
            else:
                hourly[hour]["losses"] += 1
        
        # Calcula win rate para cada hora
        for hour, stats in hourly.items():
            stats["win_rate"] = (stats["wins"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        return hourly
    
    def _analyze_by_volatility(self, trades: list[dict]) -> dict[str, dict]:
        """Analisa trades por nível de volatilidade."""
        by_vol = {}
        
        for trade in trades:
            context = trade.get("context", {})
            volatility = context.get("volatility", "UNKNOWN") if context else "UNKNOWN"
            
            if volatility not in by_vol:
                by_vol[volatility] = {"wins": 0, "losses": 0, "total": 0}
            
            by_vol[volatility]["total"] += 1
            if float(trade.get("profit", 0)) > 0:
                by_vol[volatility]["wins"] += 1
            else:
                by_vol[volatility]["losses"] += 1
        
        for vol, stats in by_vol.items():
            stats["win_rate"] = (stats["wins"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        return by_vol
    
    def _analyze_mtf_alignment(self, trades: list[dict]) -> dict[str, float]:
        """Analisa impacto do alinhamento MTF."""
        aligned = {"wins": 0, "total": 0}
        divergent = {"wins": 0, "total": 0}
        
        for trade in trades:
            context = trade.get("context", {})
            if not context:
                continue
            
            h1 = context.get("mtf_h1_trend", "NEUTRAL")
            h4 = context.get("mtf_h4_trend", "NEUTRAL")
            direction = trade.get("direction", "")
            
            expected = "BULLISH" if direction == "BUY" else "BEARISH"
            is_aligned = (h4 == expected) or (h1 == expected and h4 == "NEUTRAL")
            
            if is_aligned:
                aligned["total"] += 1
                if float(trade.get("profit", 0)) > 0:
                    aligned["wins"] += 1
            else:
                divergent["total"] += 1
                if float(trade.get("profit", 0)) > 0:
                    divergent["wins"] += 1
        
        return {
            "aligned_win_rate": (aligned["wins"] / aligned["total"]) * 100 if aligned["total"] > 0 else 0,
            "divergent_win_rate": (divergent["wins"] / divergent["total"]) * 100 if divergent["total"] > 0 else 0,
            "aligned_count": aligned["total"],
            "divergent_count": divergent["total"]
        }
    
    def _generate_recommendations(
        self,
        insights: TradingInsights,
        hourly: dict,
        volatility: dict
    ) -> list[str]:
        """Gera recomendações baseadas na análise."""
        recs = []
        
        # Melhores horários
        if insights.best_hour_win_rate > 60:
            recs.append(f"🎯 Best hour: {insights.best_hour:02d}:00 ({insights.best_hour_win_rate:.0f}% win rate)")
        
        # Volatilidade
        if insights.best_volatility_win_rate > 55:
            recs.append(f"📊 Prefer {insights.best_volatility} volatility ({insights.best_volatility_win_rate:.0f}% win rate)")
        
        # MTF alignment
        if insights.mtf_aligned_win_rate > insights.mtf_divergent_win_rate + 10:
            diff = insights.mtf_aligned_win_rate - insights.mtf_divergent_win_rate
            recs.append(f"🔄 MTF-aligned trades +{diff:.0f}% better win rate")
        
        # Profit factor
        if insights.profit_factor > 1.5:
            recs.append(f"✅ Profit Factor {insights.profit_factor:.2f} is healthy")
        elif insights.profit_factor > 1.0:
            recs.append(f"⚠️ Profit Factor {insights.profit_factor:.2f} - room for improvement")
        
        return recs
    
    def _generate_avoid_conditions(
        self,
        insights: TradingInsights,
        hourly: dict,
        volatility: dict
    ) -> list[str]:
        """Gera lista de condições a evitar."""
        avoid = []
        
        # Piores horários
        if insights.worst_hour_win_rate < 40:
            avoid.append(f"⛔ Avoid trading at {insights.worst_hour:02d}:00 ({insights.worst_hour_win_rate:.0f}% win rate)")
        
        # Volatilidade ruim
        for vol, stats in volatility.items():
            if stats["win_rate"] < 40 and stats["total"] >= 5:
                avoid.append(f"⛔ Avoid {vol} volatility ({stats['win_rate']:.0f}% win rate)")
        
        # MTF divergente
        if insights.mtf_divergent_win_rate < 35:
            avoid.append(f"⛔ Avoid trades against MTF trend ({insights.mtf_divergent_win_rate:.0f}% win rate)")
        
        return avoid
    
    def should_skip_trade(
        self,
        insights: TradingInsights,
        current_hour: int,
        volatility: str,
        mtf_aligned: bool
    ) -> tuple[bool, str]:
        """
        Verifica se deve pular trade baseado no histórico.
        
        Args:
            insights: Insights atuais
            current_hour: Hora atual
            volatility: Volatilidade atual
            mtf_aligned: Se MTF está alinhado
        
        Returns:
            Tuple (should_skip, reason)
        """
        # Verifica hora
        if insights.worst_hour == current_hour and insights.worst_hour_win_rate < 35:
            return True, f"Memory: Avoid hour {current_hour:02d}:00 (historical win rate: {insights.worst_hour_win_rate:.0f}%)"
        
        # Verifica MTF
        if not mtf_aligned and insights.mtf_divergent_win_rate < 35:
            return True, f"Memory: MTF divergent trades have {insights.mtf_divergent_win_rate:.0f}% historical win rate"
        
        # Verifica confiança mínima
        if insights.confidence < 25:
            return False, "Insufficient historical data"
        
        return False, ""
    
    def get_confidence_adjustment(self, insights: TradingInsights, mtf_aligned: bool) -> int:
        """
        Retorna ajuste de confiança baseado no histórico.
        
        Args:
            insights: Insights atuais
            mtf_aligned: Se MTF está alinhado
        
        Returns:
            Ajuste de -15 a +15
        """
        if insights.confidence < 25:
            return 0  # Dados insuficientes
        
        adjustment = 0
        
        # Bônus/penalidade por MTF
        if mtf_aligned and insights.mtf_aligned_win_rate > 60:
            adjustment += 10
        elif not mtf_aligned and insights.mtf_divergent_win_rate < 40:
            adjustment -= 10
        
        # Bônus por profit factor alto
        if insights.profit_factor > 2.0:
            adjustment += 5
        elif insights.profit_factor < 1.0:
            adjustment -= 5
        
        return max(-15, min(15, adjustment))
    
    def format_insights_for_prompt(self, insights: TradingInsights) -> str:
        """
        Formata insights para incluir no prompt do CIO.
        
        Args:
            insights: Insights do Trade Memory
        
        Returns:
            String formatada para o prompt
        """
        if insights.confidence < 25:
            return "Trade Memory: Insufficient historical data for recommendations."
        
        lines = [
            f"📚 TRADE MEMORY INSIGHTS (Confidence: {insights.confidence:.0f}%)",
            f"   Historical Win Rate: {insights.win_rate:.1f}% ({insights.total_trades} trades)",
            f"   Profit Factor: {insights.profit_factor:.2f}"
        ]
        
        if insights.recommendations:
            lines.append("   Recommendations:")
            for rec in insights.recommendations[:3]:
                lines.append(f"     {rec}")
        
        if insights.avoid_conditions:
            lines.append("   ⚠️ Avoid:")
            for avoid in insights.avoid_conditions[:2]:
                lines.append(f"     {avoid}")
        
        return "\n".join(lines)


# Singleton
trade_memory = TradeMemory()
