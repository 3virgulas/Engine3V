"use client";

interface ModernConfidenceGaugeProps {
    confidence: number;
    size?: number;
}

export function ModernConfidenceGauge({
    confidence,
    size = 180,
}: ModernConfidenceGaugeProps) {
    // Clamp confidence between 0 and 100
    const clampedConfidence = Math.min(100, Math.max(0, confidence));

    // Calculate arc properties
    const strokeWidth = 12;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const progress = (clampedConfidence / 100) * circumference;

    // Determine color based on confidence level
    const getColor = () => {
        if (clampedConfidence >= 70) return { stroke: "#22c55e", glow: "rgba(34,197,94,0.4)" };
        if (clampedConfidence >= 50) return { stroke: "#f59e0b", glow: "rgba(245,158,11,0.4)" };
        return { stroke: "#64748b", glow: "rgba(100,116,139,0.2)" };
    };

    const { stroke, glow } = getColor();

    // Determine confidence label
    const getLabel = () => {
        if (clampedConfidence >= 80) return "Muito Alta";
        if (clampedConfidence >= 60) return "Alta";
        if (clampedConfidence >= 40) return "Moderada";
        return "Baixa";
    };

    return (
        <div
            className="relative flex flex-col items-center justify-center
                 backdrop-blur-xl bg-slate-900/60 border border-slate-600/50
                 rounded-3xl p-6"
            style={{ boxShadow: `0 0 40px ${glow}` }}
        >
            <div className="text-xs uppercase tracking-widest text-slate-400 mb-4">
                Confiança do Sinal
            </div>

            <div className="relative" style={{ width: size, height: size }}>
                {/* Background circle */}
                <svg
                    width={size}
                    height={size}
                    className="transform -rotate-90"
                >
                    {/* Background track */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="transparent"
                        stroke="rgba(100,116,139,0.2)"
                        strokeWidth={strokeWidth}
                    />

                    {/* Progress arc */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="transparent"
                        stroke={stroke}
                        strokeWidth={strokeWidth}
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={circumference - progress}
                        style={{
                            transition: "stroke-dashoffset 1s ease-in-out, stroke 0.5s ease",
                            filter: `drop-shadow(0 0 10px ${glow})`,
                        }}
                    />
                </svg>

                {/* Center content */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span
                        className="text-4xl font-black"
                        style={{ color: stroke }}
                    >
                        {clampedConfidence}%
                    </span>
                    <span className="text-sm text-slate-400 mt-1">{getLabel()}</span>
                </div>
            </div>

            {/* Confidence breakdown */}
            <div className="mt-4 w-full space-y-2">
                <ConfidenceRow
                    label="Técnico"
                    value={Math.min(100, clampedConfidence + 10)}
                    color="#3b82f6"
                />
                <ConfidenceRow
                    label="Sentimento"
                    value={Math.max(0, clampedConfidence - 10)}
                    color="#8b5cf6"
                />
                <ConfidenceRow
                    label="Macro"
                    value={clampedConfidence}
                    color="#06b6d4"
                />
            </div>
        </div>
    );
}

interface ConfidenceRowProps {
    label: string;
    value: number;
    color: string;
}

function ConfidenceRow({ label, value, color }: ConfidenceRowProps) {
    return (
        <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 w-20">{label}</span>
            <div className="flex-1 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                        width: `${value}%`,
                        backgroundColor: color,
                        boxShadow: `0 0 6px ${color}`,
                    }}
                />
            </div>
            <span className="text-slate-400 w-8 text-right">{value}%</span>
        </div>
    );
}
