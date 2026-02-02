"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Lista de modelos disponíveis
const AVAILABLE_MODELS = [
    { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", provider: "Anthropic" },
    { id: "moonshotai/kimi-k2.5", name: "Kimi K2.5", provider: "Moonshot AI" },
    { id: "openai/gpt-4o", name: "GPT-4o", provider: "OpenAI" },
];

export default function AdminPage() {
    const [currentModel, setCurrentModel] = useState<string>("");
    const [selectedModel, setSelectedModel] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);

    // Fetch current model
    const fetchCurrentModel = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/admin/model`);
            if (response.ok) {
                const data = await response.json();
                setCurrentModel(data.model);
                setSelectedModel(data.model);
            }
        } catch (error) {
            console.error("Failed to fetch model:", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCurrentModel();
    }, [fetchCurrentModel]);

    // Save model
    const handleSave = async () => {
        setSaving(true);
        setSaveResult(null);

        try {
            const response = await fetch(`${API_URL}/admin/model`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: selectedModel }),
            });

            const data = await response.json();

            if (response.ok) {
                setCurrentModel(selectedModel);
                setSaveResult({ success: true, message: "Modelo atualizado com sucesso!" });
            } else {
                setSaveResult({ success: false, message: data.detail || "Erro ao salvar" });
            }
        } catch (error) {
            setSaveResult({ success: false, message: "Erro de conexão com a API" });
        } finally {
            setSaving(false);
        }
    };

    // Test model connection
    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);

        try {
            const response = await fetch(`${API_URL}/admin/model/test`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: selectedModel }),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                setTestResult({
                    success: true,
                    message: `✅ Modelo respondeu: "${data.response?.substring(0, 100)}..."`
                });
            } else {
                setTestResult({
                    success: false,
                    message: data.error || "Falha no teste"
                });
            }
        } catch (error) {
            setTestResult({ success: false, message: "Erro de conexão com a API" });
        } finally {
            setTesting(false);
        }
    };

    const hasChanges = selectedModel !== currentModel;

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            {/* Header */}
            <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 
                            flex items-center justify-center text-white font-bold text-lg">
                                ⚙️
                            </div>
                            <div>
                                <h1 className="text-xl font-bold text-white">Admin Panel</h1>
                                <p className="text-xs text-slate-400">3V Engine Configuration</p>
                            </div>
                        </Link>
                    </div>

                    <div className="flex items-center gap-3">
                        <Link
                            href="/admin/trading"
                            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-white text-sm transition"
                        >
                            🤖 Trading Automation
                        </Link>
                        <Link
                            href="/"
                            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white text-sm transition"
                        >
                            ← Voltar ao Dashboard
                        </Link>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <div className="container mx-auto px-6 py-8 max-w-2xl">
                <div className="bg-slate-800/50 backdrop-blur rounded-2xl border border-slate-700 p-8">
                    <h2 className="text-2xl font-bold text-white mb-2">Configuração do Modelo LLM</h2>
                    <p className="text-slate-400 mb-8">
                        Selecione qual modelo de IA será usado para análise de mercado.
                    </p>

                    {loading ? (
                        <div className="flex items-center justify-center h-32">
                            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500" />
                        </div>
                    ) : (
                        <>
                            {/* Model Selector */}
                            <div className="mb-6">
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Modelo Ativo
                                </label>
                                <select
                                    value={selectedModel}
                                    onChange={(e) => {
                                        setSelectedModel(e.target.value);
                                        setTestResult(null);
                                        setSaveResult(null);
                                    }}
                                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 
                           text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent
                           outline-none transition"
                                >
                                    {AVAILABLE_MODELS.map((model) => (
                                        <option key={model.id} value={model.id}>
                                            {model.name} ({model.provider})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Current Model Info */}
                            <div className="mb-6 p-4 bg-slate-700/50 rounded-lg border border-slate-600">
                                <div className="text-xs text-slate-400 mb-1">Modelo atual em uso:</div>
                                <div className="text-emerald-400 font-mono">{currentModel || "Não definido"}</div>
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-4 mb-6">
                                <button
                                    onClick={handleTest}
                                    disabled={testing}
                                    className="flex-1 px-4 py-3 bg-slate-600 hover:bg-slate-500 disabled:opacity-50 
                           disabled:cursor-not-allowed rounded-lg text-white font-medium transition
                           flex items-center justify-center gap-2"
                                >
                                    {testing ? (
                                        <>
                                            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-white" />
                                            Testando...
                                        </>
                                    ) : (
                                        <>🧪 Testar Conexão</>
                                    )}
                                </button>

                                <button
                                    onClick={handleSave}
                                    disabled={saving || !hasChanges}
                                    className={`flex-1 px-4 py-3 rounded-lg font-medium transition
                           flex items-center justify-center gap-2
                           ${hasChanges
                                            ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                                            : "bg-slate-700 text-slate-400 cursor-not-allowed"
                                        }`}
                                >
                                    {saving ? (
                                        <>
                                            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-white" />
                                            Salvando...
                                        </>
                                    ) : (
                                        <>💾 Salvar Alterações</>
                                    )}
                                </button>
                            </div>

                            {/* Test Result */}
                            {testResult && (
                                <div className={`p-4 rounded-lg border mb-4 ${testResult.success
                                    ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-300"
                                    : "bg-red-500/20 border-red-500/30 text-red-300"
                                    }`}>
                                    {testResult.message}
                                </div>
                            )}

                            {/* Save Result */}
                            {saveResult && (
                                <div className={`p-4 rounded-lg border ${saveResult.success
                                    ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-300"
                                    : "bg-red-500/20 border-red-500/30 text-red-300"
                                    }`}>
                                    {saveResult.message}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Info Card */}
                <div className="mt-6 p-6 bg-slate-800/30 rounded-xl border border-slate-700/50">
                    <h3 className="font-medium text-slate-300 mb-2">ℹ️ Sobre os Modelos</h3>
                    <ul className="text-sm text-slate-400 space-y-1">
                        <li><strong>Claude 3.5 Sonnet:</strong> Melhor equilíbrio qualidade/custo. Recomendado.</li>
                        <li><strong>Kimi K2.5:</strong> Modelo chinês, boa performance em raciocínio.</li>
                        <li><strong>GPT-4o:</strong> OpenAI, excelente mas mais caro.</li>
                    </ul>
                </div>
            </div>
        </main>
    );
}
