"use client";

interface SignalCardProps {
    decision: string | null;
    direction: string | null;
    pair: string;
    timestamp: string | null;
}

export function SignalCard({ decision, direction, pair, timestamp }: SignalCardProps) {
    // Determina cor e estilo baseado no sinal
    const getCardStyle = () => {
        switch (decision) {
            case "BUY":
            case "BUY_LONG":
                return {
                    bg: "from-emerald-500 to-green-600",
                    border: "border-emerald-400",
                    glow: "shadow-emerald-500/50",
                    emoji: "🚀",
                    label: "COMPRA",
                    sublabel: "LONG"
                };
            case "SELL":
            case "SELL_SHORT":
                return {
                    bg: "from-red-500 to-rose-600",
                    border: "border-red-400",
                    glow: "shadow-red-500/50",
                    emoji: "📉",
                    label: "VENDA",
                    sublabel: "SHORT"
                };
            case "VETO":
                return {
                    bg: "from-amber-500 to-orange-600",
                    border: "border-amber-400",
                    glow: "shadow-amber-500/50",
                    emoji: "🛡️",
                    label: "VETO",
                    sublabel: "MACRO RISK"
                };
            default:
                return {
                    bg: "from-slate-600 to-slate-700",
                    border: "border-slate-500",
                    glow: "shadow-slate-500/30",
                    emoji: "⏸️",
                    label: "AGUARDANDO",
                    sublabel: "HOLD"
                };
        }
    };

    const style = getCardStyle();

    return (
        <div className={`
      relative overflow-hidden rounded-2xl 
      bg-gradient-to-br ${style.bg}
      border-2 ${style.border}
      shadow-2xl ${style.glow}
      p-8 text-white
      transition-all duration-500
    `}>
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-10">
                <div className="absolute -right-4 -top-4 text-[200px] font-bold">
                    {style.emoji}
                </div>
            </div>

            {/* Content */}
            <div className="relative z-10">
                <div className="text-sm font-medium opacity-80 uppercase tracking-wider mb-2">
                    SINAL ATUAL • {pair}
                </div>

                <div className="flex items-center gap-4 mb-4">
                    <span className="text-6xl">{style.emoji}</span>
                    <div>
                        <h2 className="text-4xl font-bold tracking-tight">{style.label}</h2>
                        <p className="text-lg opacity-80">{style.sublabel}</p>
                    </div>
                </div>

                {direction && (
                    <div className="inline-block bg-white/20 backdrop-blur rounded-full px-4 py-1 text-sm font-medium">
                        Direção: {direction}
                    </div>
                )}

                {timestamp && (
                    <div className="mt-4 text-xs opacity-60">
                        Atualizado: {new Date(timestamp).toLocaleString("pt-BR")}
                    </div>
                )}
            </div>
        </div>
    );
}
