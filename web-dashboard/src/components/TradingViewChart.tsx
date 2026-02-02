"use client";

import { useEffect, useState } from "react";

interface TradingViewChartProps {
    symbol?: string;
    interval?: string;
}

export function TradingViewChart({
    symbol = "FX:EURUSD",
    interval = "15",
}: TradingViewChartProps) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        if (!mounted) return;

        // Clean up any existing widget
        const container = document.getElementById("tradingview_widget_container");
        if (container) {
            container.innerHTML = "";
        }

        // Create script element for TradingView widget
        const script = document.createElement("script");
        script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
        script.type = "text/javascript";
        script.async = true;
        script.innerHTML = JSON.stringify({
            autosize: true,
            symbol: symbol,
            interval: interval,
            timezone: "America/Sao_Paulo",
            theme: "dark",
            style: "1",
            locale: "pt_BR",
            allow_symbol_change: true,
            hide_volume: false,
            calendar: false,
            support_host: "https://www.tradingview.com",
            studies: [
                "MASimple@tv-basicstudies",
                "RSI@tv-basicstudies",
                "BB@tv-basicstudies",
            ],
        });

        const widgetContainer = document.getElementById("tradingview_widget_container");
        if (widgetContainer) {
            widgetContainer.appendChild(script);
        }

        return () => {
            // Cleanup on unmount
            if (container) {
                container.innerHTML = "";
            }
        };
    }, [mounted, symbol, interval]);

    if (!mounted) {
        return (
            <div className="w-full h-full rounded-2xl overflow-hidden border border-slate-700/30 bg-slate-900/60 flex items-center justify-center">
                <div className="text-center">
                    <div className="w-8 h-8 mx-auto mb-2 rounded-full border-2 border-emerald-500/30 border-t-emerald-500 animate-spin" />
                    <p className="text-sm text-slate-400">Carregando gráfico...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-full rounded-2xl overflow-hidden border border-slate-700/30 backdrop-blur-xl bg-slate-900/40">
            <div
                id="tradingview_widget_container"
                className="tradingview-widget-container w-full h-full"
                style={{ minHeight: "400px" }}
            >
                <div className="tradingview-widget-container__widget w-full h-full" />
            </div>
        </div>
    );
}
