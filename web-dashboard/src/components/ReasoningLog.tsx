"use client";

interface ReasoningLogProps {
    reasoning: string | null;
    inputs: {
        technical?: { signal?: string };
        sentiment?: { score?: number };
        macro?: { alert?: string };
    } | null;
}

export function ReasoningLog({ reasoning, inputs }: ReasoningLogProps) {
    return (
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6">
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
                Raciocínio da IA
            </h3>

            {/* Indicadores */}
            {inputs && (
                <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-slate-700/50 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 mb-1">Técnico</div>
                        <div className={`font-bold ${inputs.technical?.signal === "BULLISH" ? "text-emerald-400" :
                                inputs.technical?.signal === "BEARISH" ? "text-red-400" :
                                    "text-slate-300"
                            }`}>
                            {inputs.technical?.signal || "N/A"}
                        </div>
                    </div>

                    <div className="bg-slate-700/50 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 mb-1">Sentimento</div>
                        <div className={`font-bold ${(inputs.sentiment?.score ?? 0) > 0.3 ? "text-emerald-400" :
                                (inputs.sentiment?.score ?? 0) < -0.3 ? "text-red-400" :
                                    "text-slate-300"
                            }`}>
                            {inputs.sentiment?.score?.toFixed(2) || "0.00"}
                        </div>
                    </div>

                    <div className="bg-slate-700/50 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 mb-1">Macro</div>
                        <div className={`font-bold text-xs ${inputs.macro?.alert === "LOW_RISK" ? "text-emerald-400" :
                                inputs.macro?.alert === "HIGH_RISK" ? "text-red-400" :
                                    "text-amber-400"
                            }`}>
                            {inputs.macro?.alert?.replace("_", " ") || "N/A"}
                        </div>
                    </div>
                </div>
            )}

            {/* Reasoning text */}
            <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm text-slate-300 
                      max-h-40 overflow-y-auto border border-slate-700">
                {reasoning || "Aguardando análise..."}
            </div>
        </div>
    );
}
