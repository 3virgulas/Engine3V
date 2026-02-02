"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import TradeHistory from "@/components/TradeHistory";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TradingConfig {
    trading_mode: "AUTOMATIC" | "SIGNAL_ONLY";
    risk_per_trade: number;
    max_daily_loss: number;
}

interface AccountInfo {
    mode: string;
    balance: number;
    equity: number;
    daily_pnl: number;
    daily_pnl_percent: number;
    open_positions: number;
    timestamp: string;
}

export default function TradingDashboardPage() {
    const [config, setConfig] = useState<TradingConfig>({
        trading_mode: "SIGNAL_ONLY",
        risk_per_trade: 1.0,
        max_daily_loss: 3.0
    });
    const [originalConfig, setOriginalConfig] = useState<TradingConfig | null>(null);
    const [account, setAccount] = useState<AccountInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);

    // Fetch trading config
    const fetchConfig = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/admin/trading`);
            if (response.ok) {
                const data = await response.json();
                setConfig(data.config);
                setOriginalConfig(data.config);
            }
        } catch (error) {
            console.error("Failed to fetch config:", error);
        }
    }, []);

    // Fetch account info
    const fetchAccount = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/admin/account`);
            if (response.ok) {
                const data = await response.json();
                setAccount(data.account);
            }
        } catch (error) {
            console.error("Failed to fetch account:", error);
        }
    }, []);

    useEffect(() => {
        Promise.all([fetchConfig(), fetchAccount()]).finally(() => setLoading(false));

        // Refresh account every 30 seconds
        const interval = setInterval(fetchAccount, 30000);
        return () => clearInterval(interval);
    }, [fetchConfig, fetchAccount]);

    // Save config
    const handleSave = async () => {
        setSaving(true);
        setSaveResult(null);

        try {
            const response = await fetch(`${API_URL}/admin/trading`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config),
            });

            const data = await response.json();

            if (response.ok) {
                setOriginalConfig(config);
                setSaveResult({ success: true, message: "Configurações salvas com sucesso!" });
            } else {
                setSaveResult({ success: false, message: data.detail || "Erro ao salvar" });
            }
        } catch (error) {
            setSaveResult({ success: false, message: "Erro de conexão com a API" });
        } finally {
            setSaving(false);
        }
    };

    const hasChanges = JSON.stringify(config) !== JSON.stringify(originalConfig);
    const isAutomatic = config.trading_mode === "AUTOMATIC";

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            {/* Header */}
            <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link href="/admin" className="flex items-center gap-3 hover:opacity-80 transition">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 
                            flex items-center justify-center text-white font-bold text-lg">
                                🤖
                            </div>
                            <div>
                                <h1 className="text-xl font-bold text-white">Trading Automation</h1>
                                <p className="text-xs text-slate-400">3V Engine Control Panel</p>
                            </div>
                        </Link>
                    </div>

                    <div className="flex items-center gap-4">
                        <Link
                            href="/admin"
                            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white text-sm transition"
                        >
                            ⚙️ Modelo LLM
                        </Link>
                        <Link
                            href="/"
                            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white text-sm transition"
                        >
                            ← Dashboard
                        </Link>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <div className="container mx-auto px-6 py-8 max-w-4xl">
                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500" />
                    </div>
                ) : (
                    <>
                        {/* Account Monitor Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                            {/* Balance Card */}
                            <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
                                <div className="text-slate-400 text-sm mb-1">💰 Saldo {account?.mode === "SIMULATION" ? "(Simulado)" : ""}</div>
                                <div className="text-3xl font-bold text-white">
                                    ${account?.balance?.toLocaleString('en-US', { minimumFractionDigits: 2 }) || "0.00"}
                                </div>
                                <div className="text-xs text-slate-500 mt-2">
                                    Equity: ${account?.equity?.toLocaleString('en-US', { minimumFractionDigits: 2 }) || "0.00"}
                                </div>
                            </div>

                            {/* Daily P&L Card */}
                            <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
                                <div className="text-slate-400 text-sm mb-1">📊 Lucro do Dia</div>
                                <div className={`text-3xl font-bold ${(account?.daily_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {(account?.daily_pnl || 0) >= 0 ? '+' : ''}${account?.daily_pnl?.toFixed(2) || "0.00"}
                                </div>
                                <div className={`text-xs mt-2 ${(account?.daily_pnl_percent || 0) >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                    {(account?.daily_pnl_percent || 0) >= 0 ? '+' : ''}{account?.daily_pnl_percent?.toFixed(2) || "0.00"}%
                                </div>
                            </div>

                            {/* Status Card */}
                            <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
                                <div className="text-slate-400 text-sm mb-1">🔌 Status</div>
                                <div className="text-xl font-bold text-white flex items-center gap-2">
                                    <span className={`w-3 h-3 rounded-full ${account?.mode === "SIMULATION" ? 'bg-amber-400' : 'bg-emerald-400'} animate-pulse`} />
                                    {account?.mode || "Offline"}
                                </div>
                                <div className="text-xs text-slate-500 mt-2">
                                    Posições abertas: {account?.open_positions || 0}
                                </div>
                            </div>
                        </div>

                        {/* Main Control Panel */}
                        <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-8">
                            <h2 className="text-2xl font-bold text-white mb-6">⚙️ Controle de Automação</h2>

                            {/* Master Switch */}
                            <div className="mb-8">
                                <label className="block text-sm font-medium text-slate-300 mb-4">
                                    Modo de Operação
                                </label>
                                <div className="flex gap-4">
                                    <button
                                        onClick={() => setConfig({ ...config, trading_mode: "SIGNAL_ONLY" })}
                                        className={`flex-1 p-6 rounded-xl border-2 transition-all ${!isAutomatic
                                            ? 'border-amber-500 bg-amber-500/10'
                                            : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                                            }`}
                                    >
                                        <div className="text-3xl mb-2">📱</div>
                                        <div className={`font-bold text-lg ${!isAutomatic ? 'text-amber-400' : 'text-white'}`}>
                                            SIGNAL ONLY
                                        </div>
                                        <div className="text-sm text-slate-400 mt-1">
                                            Apenas envia sinais via Telegram
                                        </div>
                                    </button>

                                    <button
                                        onClick={() => setConfig({ ...config, trading_mode: "AUTOMATIC" })}
                                        className={`flex-1 p-6 rounded-xl border-2 transition-all ${isAutomatic
                                            ? 'border-emerald-500 bg-emerald-500/10'
                                            : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                                            }`}
                                    >
                                        <div className="text-3xl mb-2">🤖</div>
                                        <div className={`font-bold text-lg ${isAutomatic ? 'text-emerald-400' : 'text-white'}`}>
                                            AUTOMATIC
                                        </div>
                                        <div className="text-sm text-slate-400 mt-1">
                                            Executa ordens no MT5 automaticamente
                                        </div>
                                    </button>
                                </div>
                            </div>

                            {/* Risk Management */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                                {/* Risk Per Trade Slider */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        📊 Risco por Trade
                                    </label>
                                    <div className="flex items-center gap-4">
                                        <input
                                            type="range"
                                            min="0.5"
                                            max="5"
                                            step="0.5"
                                            value={config.risk_per_trade}
                                            onChange={(e) => setConfig({ ...config, risk_per_trade: parseFloat(e.target.value) })}
                                            className="flex-1 h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer
                                   [&::-webkit-slider-thumb]:appearance-none
                                   [&::-webkit-slider-thumb]:w-5
                                   [&::-webkit-slider-thumb]:h-5
                                   [&::-webkit-slider-thumb]:rounded-full
                                   [&::-webkit-slider-thumb]:bg-emerald-500
                                   [&::-webkit-slider-thumb]:cursor-pointer"
                                        />
                                        <div className="w-20 text-center bg-slate-700 rounded-lg py-2 px-3 text-emerald-400 font-mono font-bold">
                                            {config.risk_per_trade}%
                                        </div>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-2">
                                        Percentual do saldo arriscado por operação
                                    </div>
                                </div>

                                {/* Max Daily Loss Input */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        🛡️ Limite de Perda Diária
                                    </label>
                                    <div className="flex items-center gap-4">
                                        <input
                                            type="number"
                                            min="1"
                                            max="20"
                                            step="0.5"
                                            value={config.max_daily_loss}
                                            onChange={(e) => setConfig({ ...config, max_daily_loss: parseFloat(e.target.value) || 3 })}
                                            className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2
                                   text-white focus:ring-2 focus:ring-red-500 focus:border-transparent
                                   outline-none transition font-mono"
                                        />
                                        <div className="text-red-400 font-bold">%</div>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-2">
                                        Automação pausa se atingir este limite
                                    </div>
                                </div>
                            </div>

                            {/* Save Button */}
                            <button
                                onClick={handleSave}
                                disabled={saving || !hasChanges}
                                className={`w-full py-4 rounded-xl font-bold text-lg transition
                       flex items-center justify-center gap-3 ${hasChanges
                                        ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white'
                                        : 'bg-slate-700 text-slate-400 cursor-not-allowed'
                                    }`}
                            >
                                {saving ? (
                                    <>
                                        <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-white" />
                                        Salvando...
                                    </>
                                ) : (
                                    <>💾 Salvar Configurações</>
                                )}
                            </button>

                            {/* Save Result */}
                            {saveResult && (
                                <div className={`mt-4 p-4 rounded-lg border ${saveResult.success
                                    ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-300"
                                    : "bg-red-500/20 border-red-500/30 text-red-300"
                                    }`}>
                                    {saveResult.message}
                                </div>
                            )}
                        </div>

                        {/* Trade History */}
                        <div className="mt-8">
                            <TradeHistory />
                        </div>

                        {/* Warning Card */}
                        {isAutomatic && (
                            <div className="mt-6 p-6 bg-amber-500/10 rounded-xl border border-amber-500/30">
                                <h3 className="font-bold text-amber-400 mb-2">⚠️ Modo Automático Ativo</h3>
                                <p className="text-sm text-amber-300/80">
                                    O sistema irá executar ordens reais no MetaTrader 5.
                                    Certifique-se de que o MT5 está conectado e configurado corretamente.
                                    Use uma conta demo para testes iniciais.
                                </p>
                            </div>
                        )}

                        {/* Simulation Mode Notice */}
                        {account?.mode === "SIMULATION" && (
                            <div className="mt-6 p-6 bg-slate-800/30 rounded-xl border border-slate-700/50">
                                <h3 className="font-medium text-slate-300 mb-2">ℹ️ Modo Simulação</h3>
                                <p className="text-sm text-slate-400">
                                    O sistema está operando em modo simulação (MT5 não disponível neste SO).
                                    Ordens serão logadas mas não executadas. Para trading real, use Windows com MT5.
                                </p>
                            </div>
                        )}
                    </>
                )}
            </div>
        </main>
    );
}
