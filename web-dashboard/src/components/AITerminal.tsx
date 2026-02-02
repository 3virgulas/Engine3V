"use client";

import { useEffect, useRef } from "react";

interface AITerminalProps {
    reasoning: string | null;
    inputs?: {
        technical?: { signal?: string };
        sentiment?: { score?: number };
        macro?: { alert?: string };
    } | null;
}

export function AITerminal({ reasoning, inputs }: AITerminalProps) {
    const terminalRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new content arrives
    useEffect(() => {
        if (terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [reasoning]);

    const formatTimestamp = () => {
        return new Date().toISOString().replace("T", " ").slice(0, 19);
    };

    return (
        <div
            className="
        backdrop-blur-xl bg-slate-950/80 border border-slate-700/50
        rounded-2xl overflow-hidden h-full
      "
        >
            {/* Terminal Header */}
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-900/80 border-b border-slate-700/50">
                <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                    <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                    <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                </div>
                <span className="text-xs text-slate-400 font-mono ml-2">
                    3V_ENGINE_AI_TERMINAL v2.0
                </span>
                <div className="ml-auto flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs text-emerald-400 font-mono">LIVE</span>
                </div>
            </div>

            {/* Terminal Content */}
            <div
                ref={terminalRef}
                className="p-4 font-mono text-sm h-32 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-slate-800"
            >
                {/* System boot logs */}
                <TerminalLine
                    prefix="[SYSTEM]"
                    prefixColor="text-cyan-400"
                    text="3V Engine initialized successfully"
                />
                <TerminalLine
                    prefix="[AGENTS]"
                    prefixColor="text-purple-400"
                    text="@Quant_Analyst, @Sentiment_Pulse, @Macro_Watcher, @Risk_Commander online"
                />

                {/* Input analysis */}
                {inputs && (
                    <>
                        <div className="my-2 border-t border-slate-700/30" />
                        <TerminalLine
                            prefix="[TECH]"
                            prefixColor="text-blue-400"
                            text={`Signal: ${inputs.technical?.signal || "NEUTRAL"}`}
                        />
                        <TerminalLine
                            prefix="[SENT]"
                            prefixColor="text-violet-400"
                            text={`Score: ${inputs.sentiment?.score?.toFixed(2) || "0.00"}`}
                        />
                        <TerminalLine
                            prefix="[MACRO]"
                            prefixColor="text-teal-400"
                            text={`Alert: ${inputs.macro?.alert || "LOW_RISK"}`}
                        />
                    </>
                )}

                {/* AI Reasoning */}
                {reasoning && (
                    <>
                        <div className="my-2 border-t border-slate-700/30" />
                        <TerminalLine
                            prefix="[AI]"
                            prefixColor="text-emerald-400"
                            text={`${formatTimestamp()} Processing...`}
                        />
                        <div className="mt-2 pl-4 border-l-2 border-emerald-500/30">
                            <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
                                {reasoning}
                            </p>
                        </div>
                    </>
                )}

                {/* Blinking cursor */}
                <div className="mt-2 flex items-center gap-1">
                    <span className="text-emerald-400">$</span>
                    <span className="w-2 h-4 bg-emerald-400 animate-pulse" />
                </div>
            </div>
        </div>
    );
}

interface TerminalLineProps {
    prefix: string;
    prefixColor: string;
    text: string;
}

function TerminalLine({ prefix, prefixColor, text }: TerminalLineProps) {
    return (
        <div className="flex gap-2 mb-1">
            <span className={`${prefixColor} font-semibold`}>{prefix}</span>
            <span className="text-slate-400">{text}</span>
        </div>
    );
}
