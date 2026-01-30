"use client";

interface ConfidenceGaugeProps {
    confidence: number;
}

export function ConfidenceGauge({ confidence }: ConfidenceGaugeProps) {
    // Calcula cor baseada na confiança
    const getColor = () => {
        if (confidence >= 80) return { stroke: "#10b981", text: "text-emerald-400" }; // Verde
        if (confidence >= 60) return { stroke: "#f59e0b", text: "text-amber-400" };   // Amarelo
        return { stroke: "#ef4444", text: "text-red-400" };                           // Vermelho
    };

    const color = getColor();
    const circumference = 2 * Math.PI * 45; // raio = 45
    const strokeDashoffset = circumference - (confidence / 100) * circumference;

    return (
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-6 text-center">
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
                Score de Confiança
            </h3>

            <div className="relative inline-flex items-center justify-center">
                <svg className="w-32 h-32 transform -rotate-90">
                    {/* Background circle */}
                    <circle
                        cx="64"
                        cy="64"
                        r="45"
                        fill="none"
                        stroke="#1e293b"
                        strokeWidth="12"
                    />
                    {/* Progress circle */}
                    <circle
                        cx="64"
                        cy="64"
                        r="45"
                        fill="none"
                        stroke={color.stroke}
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-1000 ease-out"
                    />
                </svg>

                {/* Center text */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-3xl font-bold ${color.text}`}>
                        {confidence}%
                    </span>
                </div>
            </div>

            <div className="mt-4 text-sm text-slate-400">
                {confidence >= 80 && "Alta confiança"}
                {confidence >= 60 && confidence < 80 && "Confiança moderada"}
                {confidence < 60 && "Baixa confiança"}
            </div>
        </div>
    );
}
