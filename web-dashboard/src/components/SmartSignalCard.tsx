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
        ? "shadow-[0_0_60px_rgba(34,197,94,0.4)]"
        : isSell
            ? "shadow-[0_0_60px_rgba(239,68,68,0.4)]"
            : "shadow-[0_0_30px_rgba(100,116,139,0.2)]";

    const signalBorderColor = isBuy
        ? "border-emerald-500/50"
        : isSell
            ? "border-red-500/50"
            : "border-slate-600/50";

    const signalBgGradient = isBuy
        ? "from-emerald-500/10 to-transparent"
        : isSell
            ? "from-red-500/10 to-transparent"
            : "from-slate-500/10 to-transparent";

    return (
        <div
            className={`
        relative overflow-hidden rounded-3xl p-6
        backdrop-blur-xl bg-slate-900/60 border ${signalBorderColor}
        ${glowColor} transition-all duration-700
      `}
        >
            {/* Animated pulse background for active signals */}
            {!isHold && (
                <div
                    className={`
            absolute inset-0 animate-pulse opacity-20
            bg-gradient-to-br ${signalBgGradient}
          `}
                />
            )}

            {/* Signal Status */}
            <div className="relative z-10">
                {/* Header with Pair + Timeframe Badge */}
                <div className="flex items-center gap-3 mb-2">
                    <span className="text-xs uppercase tracking-widest text-slate-400">
                        {pair}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 text-xs font-bold border border-blue-500/30">
                        {timeframe}
                    </span>
                    <span className="text-xs text-slate-500">• Sinal Atual</span>
                </div>

                {/* Giant Signal Display */}
                <div className="flex items-center gap-4 mb-6">
                    <div
                        className={`
              text-6xl md:text-7xl font-black tracking-tight
              ${isBuy ? "text-emerald-400" : isSell ? "text-red-400" : "text-slate-400"}
            `}
                    >
                        {isBuy ? "BUY" : isSell ? "SELL" : "WAIT"}
                    </div>

                    {!isHold && direction && (
                        <div
                            className={`
                px-3 py-1 rounded-full text-sm font-medium
                ${isBuy ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}
              `}
                        >
                            {direction}
                        </div>
                    )}
                </div>

                {/* Price Levels or Market Bias */}
                {isHold ? (
                    <div className="space-y-3">
                        <div className="text-sm text-slate-400">Market Bias</div>
                        <div className="flex items-center gap-3">
                            <span
                                className={`
                  text-2xl font-bold
                  ${marketBias === "Alta" ? "text-emerald-400" : marketBias === "Baixa" ? "text-red-400" : "text-amber-400"}
                `}
                            >
                                {marketBias === "Alta" ? "↑" : marketBias === "Baixa" ? "↓" : "→"}
                            </span>
                            <span className="text-xl text-white font-semibold">{marketBias}</span>
                        </div>
                        <p className="text-sm text-slate-500">
                            Aguardando convergência de sinais...
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {/* Entry Price - Larger and more prominent */}
                        <PriceRow
                            label="Entry Price"
                            value={entryPrice}
                            color="text-white"
                            bgColor="bg-slate-800/80"
                            borderColor="border-slate-600/50"
                            onCopy={() => copyToClipboard(entryPrice, "entry")}
                            copied={copiedField === "entry"}
                        />
                        {/* Take Profit */}
                        <PriceRow
                            label="Take Profit"
                            value={takeProfit}
                            color="text-emerald-400"
                            bgColor="bg-emerald-500/10"
                            borderColor="border-emerald-500/30"
                            onCopy={() => copyToClipboard(takeProfit, "tp")}
                            copied={copiedField === "tp"}
                        />
                        {/* Stop Loss */}
                        <PriceRow
                            label="Stop Loss"
                            value={stopLoss}
                            color="text-red-400"
                            bgColor="bg-red-500/10"
                            borderColor="border-red-500/30"
                            onCopy={() => copyToClipboard(stopLoss, "sl")}
                            copied={copiedField === "sl"}
                        />
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
}

function PriceRow({ label, value, color, bgColor, borderColor, onCopy, copied }: PriceRowProps) {
    return (
        <div
            className={`
        ${bgColor} rounded-xl p-3 border ${borderColor}
        flex items-center justify-between
        hover:scale-[1.02] transition-transform
      `}
        >
            <div>
                <div className="text-xs text-slate-400 mb-0.5">{label}</div>
                <div className={`font-mono font-bold text-xl ${color}`}>
                    {value.toFixed(5)}
                </div>
            </div>
            <button
                onClick={onCopy}
                className={`
          px-3 py-2 rounded-lg text-xs font-medium transition-all
          ${copied
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 border border-slate-600/50"
                    }
        `}
            >
                {copied ? (
                    <span className="flex items-center gap-1">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Copiado
                    </span>
                ) : (
                    <span className="flex items-center gap-1">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Copiar
                    </span>
                )}
            </button>
        </div>
    );
}
