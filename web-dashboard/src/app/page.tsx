"use client";

import { useEffect, useState, useCallback } from "react";
import { SignalCard } from "@/components/SignalCard";
import { ConfidenceGauge } from "@/components/ConfidenceGauge";
import { ReasoningLog } from "@/components/ReasoningLog";

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
  const direction = lastAnalysis?.final_decision?.includes("LONG") ? "LONG" :
    lastAnalysis?.final_decision?.includes("SHORT") ? "SHORT" : null;
  const confidence = lastAnalysis?.reasoning?.confidence || 0;
  const reasoning = lastAnalysis?.reasoning?.verdict || null;
  const inputs = lastAnalysis?.reasoning?.inputs || null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 
                          flex items-center justify-center text-white font-bold text-lg">
              3V
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">3V Engine</h1>
              <p className="text-xs text-slate-400">Forex Signal Dashboard</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Status indicator */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm
              ${status?.engine_active
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-red-500/20 text-red-400 border border-red-500/30"
              }`}>
              <span className={`w-2 h-2 rounded-full ${status?.engine_active ? "bg-emerald-400 animate-pulse" : "bg-red-400"
                }`} />
              {status?.engine_active ? "Engine Ativo" : "Engine Offline"}
            </div>

            {/* Countdown */}
            <div className="text-xs text-slate-400">
              Atualiza em {countdown}s
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500" />
          </div>
        ) : error ? (
          <div className="bg-red-500/20 border border-red-500/30 rounded-2xl p-8 text-center">
            <div className="text-4xl mb-4">❌</div>
            <h2 className="text-xl font-bold text-red-400 mb-2">Erro de Conexão</h2>
            <p className="text-slate-400">{error}</p>
            <p className="text-sm text-slate-500 mt-4">
              Certifique-se que a API está rodando em {API_URL}
            </p>
            <button
              onClick={fetchStatus}
              className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition"
            >
              Tentar Novamente
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Signal Card - Spans 2 columns */}
            <div className="lg:col-span-2">
              <SignalCard
                decision={decision}
                direction={direction}
                pair={status?.pair || "EUR/USD"}
                timestamp={lastAnalysis?.created_at || null}
              />
            </div>

            {/* Confidence Gauge */}
            <div>
              <ConfidenceGauge confidence={confidence} />
            </div>

            {/* Reasoning Log - Full width */}
            <div className="lg:col-span-3">
              <ReasoningLog reasoning={reasoning} inputs={inputs} />
            </div>
          </div>
        )}

        {/* Footer info */}
        {lastUpdate && (
          <div className="mt-8 text-center text-xs text-slate-500">
            Última atualização: {lastUpdate.toLocaleString("pt-BR")}
          </div>
        )}
      </div>
    </main>
  );
}
