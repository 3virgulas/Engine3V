"use client";

import { useState } from "react";

interface SmartSignalCardProps {
    decision: string | null;
    direction: string | null;
    pair: string;
    timeframe?: string; // NEW: M5, M15, H1, etc.
    entryPrice?: number;
    takeProfit?: number;
    stopLoss?: number;
    marketBias?: string;
}

export function SmartSignalCard({
    decision,
    direction,
    pair,
    timeframe = "M5",
    entryPrice = 1.0850,
    takeProfit = 1.0900,
    stopLoss = 1.0800,
    marketBias = "Lateralizado",
}: SmartSignalCardProps) {
    const [copiedField, setCopiedField] = useState<string | null>(null);

    const isHold = !decision || decision === "HOLD";
    const isBuy = decision === "BUY";
    const isSell = decision === "SELL";

    const copyToClipboard = (value: number, field: string) => {
        navigator.clipboard.writeText(value.toFixed(5));
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
    };

    // Determine glow color based on signal
    const glowColor = isBuy
        ? "shadow-[0_0_80px_rgba(34,197,94,0.3)] border-emerald-500/50"
        : isSell
            ? "shadow-[0_0_80px_rgba(239,68,68,0.3)] border-red-500/50"
            : "shadow-[0_0_30px_rgba(148,163,184,0.1)] border-slate-700/50";

    const bgGradient = isBuy
        ? "bg-gradient-to-br from-emerald-950/40 via-slate-900/40 to-slate-900/40"
        : isSell
            ? "bg-gradient-to-br from-red-950/40 via-slate-900/40 to-slate-900/40"
            : "bg-slate-900/40";

    return (
        <div
            className={`
        relative overflow-hidden rounded-[2rem] p-8
        backdrop-blur-2xl ${bgGradient} border
        ${glowColor} transition-all duration-700 group
      `}
        >
            {/* Background Effects */}
            <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />

            {!isHold && (
                <div className="absolute top-0 right-0 w-64 h-64 bg-current opacity-10 blur-[100px] rounded-full translate-x-1/2 -translate-y-1/2 text-inherit" />
            )}

            {/* Content */}
            <div className="relative z-10 flex flex-col h-full justify-between">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-3">
                        <div className="flex flex-col">
                            <span className="text-sm font-medium text-slate-400">Paridade</span>
                            <span className="text-2xl font-bold text-white tracking-tight">{pair}</span>
                        </div>
                        <span className={`
                            px-2 py-1 rounded-lg text-xs font-bold border
                            ${timeframe === "M5" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" : "bg-slate-700/30 text-slate-400 border-slate-700"}
                        `}>
                            {timeframe}
                        </span>
                    </div>

                    {/* Status Badge */}
                    <div className={`
                        flex items-center gap-2 px-3 py-1.5 rounded-full border backdrop-blur-md
                        ${isBuy ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" :
                            isSell ? "bg-red-500/10 border-red-500/20 text-red-400" :
                                "bg-slate-700/30 border-slate-600/30 text-slate-300"}
                    `}>
                        <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${isHold ? "bg-slate-400" : "bg-current"}`} />
                        <span className="text-xs font-bold tracking-wider uppercase">
                            {isHold ? "Aguardando" : "Sinal Ativo"}
                        </span>
                    </div>
                </div>

                {/* Main Signal */}
                <div className="flex flex-col items-center justify-center py-4 mb-8">
                    <div className={`
                        text-7xl md:text-8xl font-black tracking-tighter transition-all duration-500
                        ${isBuy ? "text-transparent bg-clip-text bg-gradient-to-b from-emerald-300 to-emerald-600 drop-shadow-2xl" :
                            isSell ? "text-transparent bg-clip-text bg-gradient-to-b from-red-300 to-red-600 drop-shadow-2xl" :
                                "text-slate-700"}
                    `}>
                        {isBuy ? "BUY" : isSell ? "SELL" : "WAIT"}
                    </div>

                    {!isHold && direction && (
                        <div className={`
                            mt-2 text-lg font-medium tracking-widest uppercase
                            ${isBuy ? "text-emerald-400" : "text-red-400"}
                        `}>
                            {direction} ENTRY
                        </div>
                    )}
                </div>

                {/* Details Section */}
                {isHold ? (
                    <div className="bg-slate-800/30 rounded-2xl p-6 border border-white/5 backdrop-blur-sm">
                        <div className="text-sm text-slate-400 mb-4 font-medium uppercase tracking-wider">Viés de Mercado</div>
                        <div className="flex items-center justify-between">
                            <span className="text-xl text-white font-semibold">{marketBias}</span>
                            <div className={`
                                w-12 h-12 rounded-full flex items-center justify-center text-2xl
                                ${marketBias === "Alta" ? "bg-emerald-500/20 text-emerald-400" :
                                    marketBias === "Baixa" ? "bg-red-500/20 text-red-400" :
                                        "bg-amber-500/20 text-amber-400"}
                            `}>
                                {marketBias === "Alta" ? "↗" : marketBias === "Baixa" ? "↘" : "→"}
                            </div>
                        </div>
                        <div className="mt-4 h-1 w-full bg-slate-700/50 rounded-full overflow-hidden">
                            <div className="h-full w-1/3 bg-slate-500/50 rounded-full animate-indeterminate" />
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-3">
                        <PriceRow
                            label="ENTRY"
                            value={entryPrice}
                            color="text-white"
                            bgColor="bg-slate-800/40"
                            borderColor="border-slate-700/50"
                            onCopy={() => copyToClipboard(entryPrice, "entry")}
                            copied={copiedField === "entry"}
                        />
                        <div className="grid grid-cols-2 gap-3">
                            <PriceRow
                                label="TP"
                                value={takeProfit}
                                color="text-emerald-400"
                                bgColor="bg-emerald-950/20"
                                borderColor="border-emerald-500/20"
                                onCopy={() => copyToClipboard(takeProfit, "tp")}
                                copied={copiedField === "tp"}
                                compact
                            />
                            <PriceRow
                                label="SL"
                                value={stopLoss}
                                color="text-red-400"
                                bgColor="bg-red-950/20"
                                borderColor="border-red-500/20"
                                onCopy={() => copyToClipboard(stopLoss, "sl")}
                                copied={copiedField === "sl"}
                                compact
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

interface PriceRowProps {
    label: string;
    value: number;
    color: string;
    bgColor: string;
    borderColor: string;
    onCopy: () => void;
    copied: boolean;
    compact?: boolean;
}

function PriceRow({ label, value, color, bgColor, borderColor, onCopy, copied, compact }: PriceRowProps) {
    return (
        <div
            className={`
        ${bgColor} rounded-xl border ${borderColor}
        flex items-center justify-between
        hover:scale-[1.02] transition-transform
        ${compact ? "p-3" : "p-4"}
      `}
        >
            <div>
                <div className={`text-slate-400 font-medium ${compact ? "text-[10px] mb-0.5" : "text-xs mb-1"}`}>
                    {label}
                </div>
                <div className={`font-mono font-bold ${color} ${compact ? "text-lg" : "text-2xl"}`}>
                    {value.toFixed(5)}
                </div>
            </div>
            <button
                onClick={onCopy}
                className={`
          rounded-lg font-medium transition-all flex items-center justify-center
          ${compact ? "w-8 h-8 p-0" : "px-3 py-2 text-xs"}
          ${copied
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 border border-slate-600/50"
                    }
        `}
                title="Copiar"
            >
                {copied ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                )}
                {!compact && !copied && <span className="ml-1">Copiar</span>}
            </button>
        </div>
    );
}
