"use client";

import { useEffect, useState, useCallback } from "react";
import { SmartSignalCard } from "@/components/SmartSignalCard";
import { ModernConfidenceGauge } from "@/components/ModernConfidenceGauge";
import { AITerminal } from "@/components/AITerminal";
import { TradingViewChart } from "@/components/TradingViewChart";
import { SignalHistory } from "@/components/SignalHistory";

// Tipo para os dados da API
interface StatusData {
  engine_active: boolean;
  pair: string;
  analysis_interval_minutes: number;
  last_analysis: {
    id: string;
    pair: string;
    final_decision: string;
    reasoning: {
      verdict?: string;
      confidence?: number;
      inputs?: {
        technical?: { signal?: string };
        sentiment?: { score?: number };
        macro?: { alert?: string };
      };
    };
    market_bias?: string;
    exit_levels?: {
      take_profit?: number;
      stop_loss?: number;
    };
    created_at: string;
  } | null;
  timestamp: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REFRESH_INTERVAL = 30000; // 30 segundos

export default function Dashboard() {
  const [status, setStatus] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL / 1000);

  // Fetch data from API
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/status`);
      if (!response.ok) throw new Error("API não disponível");

      const data = await response.json();
      setStatus(data);
      setError(null);
      setLastUpdate(new Date());
      setCountdown(REFRESH_INTERVAL / 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-refresh a cada 30 segundos
  useEffect(() => {
    fetchStatus();

    const interval = setInterval(fetchStatus, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Countdown visual
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : REFRESH_INTERVAL / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Extrai dados do último sinal
  const lastAnalysis = status?.last_analysis;
  const decision = lastAnalysis?.final_decision?.split("_")[0] || null;
  const direction = lastAnalysis?.final_decision?.includes("LONG")
    ? "LONG"
    : lastAnalysis?.final_decision?.includes("SHORT")
      ? "SHORT"
      : null;
  const confidence = lastAnalysis?.reasoning?.confidence || 0;
  const reasoning = lastAnalysis?.reasoning?.verdict || null;
  const inputs = lastAnalysis?.reasoning?.inputs || null;
  const marketBias = lastAnalysis?.market_bias || "Lateralizado";
  const exitLevels = lastAnalysis?.exit_levels;

  // Calcula timeframe display
  const timeframeMinutes = status?.analysis_interval_minutes || 5;
  const timeframe = timeframeMinutes >= 60 ? `H${timeframeMinutes / 60}` : `M${timeframeMinutes}`;

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950">
      {/* Header - Minimal & Clean */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-slate-950/60 border-b border-slate-800/50">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 
                          flex items-center justify-center text-white font-black text-lg
                          shadow-lg shadow-emerald-500/20"
            >
              3V
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">
                3virgulas
              </h1>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">
                Signal Terminal
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {/* Status indicator */}
            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
              ${status?.engine_active
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${status?.engine_active
                  ? "bg-emerald-400 animate-pulse"
                  : "bg-red-400"
                  }`}
              />
              {status?.engine_active ? "LIVE" : "OFFLINE"}
            </div>

            {/* Countdown */}
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              {countdown}s
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - Bento Grid */}
      <div className="pt-16 p-4 h-screen">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full border-4 border-emerald-500/30 border-t-emerald-500 animate-spin" />
              <p className="text-slate-400 text-sm">Conectando ao 3V Engine...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full">
            <div className="backdrop-blur-xl bg-red-500/10 border border-red-500/30 rounded-3xl p-8 text-center max-w-md">
              <div className="text-5xl mb-4">⚠️</div>
              <h2 className="text-xl font-bold text-red-400 mb-2">
                Conexão Perdida
              </h2>
              <p className="text-slate-400 text-sm mb-4">{error}</p>
              <button
                onClick={fetchStatus}
                className="px-6 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 
                         rounded-xl text-red-400 font-medium transition-all hover:scale-105"
              >
                Reconectar
              </button>
            </div>
          </div>
        ) : (
          <div className="h-full grid grid-cols-12 grid-rows-6 gap-4">
            {/* Left Column - Signal & Confidence (30%) */}
            <div className="col-span-12 lg:col-span-4 xl:col-span-3 row-span-4 flex flex-col gap-4">
              {/* Smart Signal Card */}
              <SmartSignalCard
                decision={decision}
                direction={direction}
                pair={status?.pair || "EUR/USD"}
                timeframe={timeframe}
                entryPrice={1.085}
                takeProfit={exitLevels?.take_profit || 1.09}
                stopLoss={exitLevels?.stop_loss || 1.08}
                marketBias={marketBias}
              />

              {/* Confidence Gauge */}
              <ModernConfidenceGauge confidence={confidence} />
            </div>

            {/* Center/Right - TradingView Chart (70%) */}
            <div className="col-span-12 lg:col-span-8 xl:col-span-9 row-span-3">
              <TradingViewChart
                symbol="FX:EURUSD"
                interval="15"
              />
            </div>

            {/* Signal History - Below Chart */}
            <div className="col-span-12 lg:col-span-8 xl:col-span-9 row-span-1">
              <SignalHistory />
            </div>

            {/* Footer - AI Terminal (Left Column Only) */}
            <div className="col-span-12 lg:col-span-4 xl:col-span-3 row-span-2">
              <AITerminal reasoning={reasoning} inputs={inputs} />
            </div>
          </div>
        )}
      </div>

      {/* Ambient glow effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-1/2 -left-1/4 w-1/2 h-1/2 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-1/4 -right-1/4 w-1/2 h-1/2 bg-blue-500/5 rounded-full blur-3xl" />
      </div>
    </main>
  );
}
