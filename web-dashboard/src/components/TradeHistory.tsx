"use client";

import { useState, useEffect, useCallback } from "react";



interface ExecutionLog {
    id: string;
    ticket: number;
    symbol: string;
    direction: string;
    volume: number;
    entry_price: number;
    stop_loss: number;
    take_profit: number;
    profit: number;
    status: string;
    mode: string;
    type: string;
    created_at: string;
}

export default function TradeHistory() {
    const [trades, setTrades] = useState<ExecutionLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchTrades = useCallback(async () => {
        try {
            const response = await fetch('/api/admin/trades');

            if (!response.ok) {
                throw new Error("Failed to fetch trades");
            }

            const data = await response.json();
            setTrades(data.trades || []);
            setError(null);
        } catch (err) {
            console.error("Failed to fetch trades:", err);
            setError("Erro ao carregar trades");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTrades();

        // Auto-update every 10 seconds
        const interval = setInterval(fetchTrades, 10000);
        return () => clearInterval(interval);
    }, [fetchTrades]);

    if (loading) {
        return (
            <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
                <h3 className="text-lg font-bold text-white mb-4">📋 Histórico de Trades</h3>
                <div className="flex items-center justify-center h-32">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500" />
                </div>
            </div>
        );
    }

    if (error || trades.length === 0) {
        return (
            <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
                <h3 className="text-lg font-bold text-white mb-4">📋 Histórico de Trades</h3>
                <div className="text-center py-8 text-slate-400">
                    <div className="text-4xl mb-2">📭</div>
                    <p>Nenhum trade executado ainda</p>
                    <p className="text-sm text-slate-500 mt-1">
                        Use <code className="bg-slate-700 px-2 py-0.5 rounded">python main.py --force-buy</code> para testar
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white">📋 Histórico de Trades</h3>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    Auto-refresh: 10s
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-700">
                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Ticket</th>
                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Símbolo</th>
                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Tipo</th>
                            <th className="text-right py-3 px-2 text-slate-400 font-medium">Lote</th>
                            <th className="text-right py-3 px-2 text-slate-400 font-medium">Preço</th>
                            <th className="text-right py-3 px-2 text-slate-400 font-medium">SL</th>
                            <th className="text-right py-3 px-2 text-slate-400 font-medium">TP</th>
                            <th className="text-right py-3 px-2 text-slate-400 font-medium">Lucro</th>
                            <th className="text-center py-3 px-2 text-slate-400 font-medium">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trades.map((trade) => {
                            const profit = trade.profit || 0;
                            const isLong = trade.direction === "LONG";
                            const isSimulation = trade.mode === "SIMULATION";

                            return (
                                <tr key={trade.id} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition">
                                    <td className="py-3 px-2 font-mono text-slate-300">
                                        #{trade.ticket}
                                    </td>
                                    <td className="py-3 px-2 text-white font-medium">
                                        {trade.symbol}
                                    </td>
                                    <td className="py-3 px-2">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${isLong
                                            ? 'bg-emerald-500/20 text-emerald-400'
                                            : 'bg-red-500/20 text-red-400'
                                            }`}>
                                            {isLong ? '📈 BUY' : '📉 SELL'}
                                        </span>
                                    </td>
                                    <td className="py-3 px-2 text-right font-mono text-slate-300">
                                        {trade.volume?.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-2 text-right font-mono text-slate-300">
                                        {trade.entry_price?.toFixed(5)}
                                    </td>
                                    <td className="py-3 px-2 text-right font-mono text-red-400">
                                        {trade.stop_loss?.toFixed(5)}
                                    </td>
                                    <td className="py-3 px-2 text-right font-mono text-emerald-400">
                                        {trade.take_profit?.toFixed(5)}
                                    </td>
                                    <td className={`py-3 px-2 text-right font-bold ${profit >= 0 ? 'text-emerald-400' : 'text-red-400'
                                        }`}>
                                        {profit >= 0 ? '+' : ''}{profit.toFixed(2)}
                                    </td>
                                    <td className="py-3 px-2 text-center">
                                        <span className={`px-2 py-1 rounded text-xs ${isSimulation
                                            ? 'bg-amber-500/20 text-amber-400'
                                            : 'bg-emerald-500/20 text-emerald-400'
                                            }`}>
                                            {isSimulation ? 'SIM' : 'LIVE'}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
