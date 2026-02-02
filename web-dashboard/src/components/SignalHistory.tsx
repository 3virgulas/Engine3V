"use client";

import { useEffect, useState, useCallback } from "react";

interface TradeResult {
    id: string;
    created_at: string;
    pair: string;
    direction: string;
    status: string;
    profit: number;
    entry_price?: number;
    close_price?: number;
}

interface SignalHistoryProps {
    refreshInterval?: number;
}

export function SignalHistory({ refreshInterval = 30000 }: SignalHistoryProps) {
    const [trades, setTrades] = useState<TradeResult[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHistory = useCallback(async () => {
        try {
            const response = await fetch("/api/signal-history");
            if (!response.ok) throw new Error("Failed to fetch history");

            const data = await response.json();
            setTrades(data.trades || []);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchHistory();
        const interval = setInterval(fetchHistory, refreshInterval);
        return () => clearInterval(interval);
    }, [fetchHistory, refreshInterval]);

    // Calculate stats
    const wins = trades.filter((t) => t.profit > 0).length;
    const losses = trades.filter((t) => t.profit < 0).length;
    const winRate = trades.length > 0 ? ((wins / trades.length) * 100).toFixed(0) : "0";
    const totalProfit = trades.reduce((sum, t) => sum + (t.profit || 0), 0);

    return (
        <div className="backdrop-blur-xl bg-slate-900/60 border border-slate-700/50 rounded-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-800/50 border-b border-slate-700/50">
                <div className="flex items-center gap-3">
                    <h3 className="text-sm font-semibold text-white">Historico de Sinais</h3>
                    <span className="text-xs text-slate-400">Ultimos 10</span>
                </div>

                {/* Stats badges */}
                <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 text-xs font-medium">
                        {wins} WIN
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-red-500/20 text-red-400 text-xs font-medium">
                        {losses} LOSS
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 text-xs font-medium">
                        {winRate}% Taxa
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="p-2">
                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="w-6 h-6 rounded-full border-2 border-emerald-500/30 border-t-emerald-500 animate-spin" />
                    </div>
                ) : error ? (
                    <div className="text-center py-6 text-red-400 text-sm">{error}</div>
                ) : trades.length === 0 ? (
                    <div className="text-center py-6 text-slate-500 text-sm">
                        Nenhum trade finalizado ainda
                    </div>
                ) : (
                    <div className="space-y-1">
                        {trades.map((trade) => (
                            <TradeRow key={trade.id} trade={trade} />
                        ))}
                    </div>
                )}
            </div>

            {/* Footer - Total */}
            {trades.length > 0 && (
                <div className="px-4 py-2 bg-slate-800/30 border-t border-slate-700/50">
                    <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-400">Lucro Total</span>
                        <span
                            className={`font-mono font-bold ${totalProfit >= 0 ? "text-emerald-400" : "text-red-400"
                                }`}
                        >
                            {totalProfit >= 0 ? "+" : ""}${totalProfit.toFixed(2)}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}

function TradeRow({ trade }: { trade: TradeResult }) {
    const isWin = trade.profit > 0;
    const time = new Date(trade.created_at).toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
    });

    // Calculate pips (approximate for forex)
    const pips = Math.abs(trade.profit / 10).toFixed(1);

    return (
        <div
            className={`
        flex items-center justify-between px-3 py-2 rounded-lg
        ${isWin ? "bg-emerald-500/5" : "bg-red-500/5"}
        hover:bg-slate-800/50 transition-colors
      `}
        >
            {/* Time + Pair */}
            <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500 font-mono w-12">{time}</span>
                <span className="text-sm text-white font-medium">{trade.pair}</span>
                <span
                    className={`
            text-xs font-medium px-1.5 py-0.5 rounded
            ${trade.direction === "LONG"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-red-500/20 text-red-400"
                        }
          `}
                >
                    {trade.direction === "LONG" ? "BUY" : "SELL"}
                </span>
            </div>

            {/* Result */}
            <div className="flex items-center gap-3">
                <span
                    className={`
            px-2 py-0.5 rounded-md text-xs font-bold
            ${isWin
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-red-500/20 text-red-400 border border-red-500/30"
                        }
          `}
                >
                    {isWin ? "WIN" : "LOSS"}
                </span>
                <span
                    className={`
            font-mono text-sm font-medium w-20 text-right
            ${isWin ? "text-emerald-400" : "text-red-400"}
          `}
                >
                    {isWin ? "+" : "-"}{pips} pips
                </span>
            </div>
        </div>
    );
}
