#!/usr/bin/env python3
"""
3V Engine - FastAPI Backend
============================
API REST para consulta de status e sinais do sistema.
Usado pelo dashboard web na Vercel.

Uso:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET /status  - Status do sistema e última análise
    GET /signals - Últimos 5 sinais para o dashboard
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Any

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import settings
from core.supabase_client import supabase_client


# ============== MODELS ==============

class StatusResponse(BaseModel):
    """Response do endpoint /status"""
    engine_active: bool
    pair: str
    analysis_interval_minutes: int
    last_analysis: dict[str, Any] | None
    timestamp: str


class SignalResponse(BaseModel):
    """Response do endpoint /signals"""
    count: int
    signals: list[dict[str, Any]]
    timestamp: str


# ============== APP ==============

app = FastAPI(
    title="3V Engine API",
    description="API REST para o sistema de sinais Forex 3V Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS para permitir acesso do frontend na Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
        "https://3virgulas.com.br",
        "https://www.3virgulas.com.br",
        "*"  # Em desenvolvimento, depois restringir
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============== ENDPOINTS ==============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "3V Engine API",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Retorna status do sistema e última análise.
    
    Usado para verificar se o loop está ativo e
    exibir a última decisão no dashboard.
    """
    try:
        # Busca última análise no Supabase
        result = supabase_client.client.table("agent_decisions") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        last_analysis = result.data[0] if result.data else None
        
        # Verifica se análise é recente (últimos 10 minutos)
        engine_active = False
        if last_analysis:
            created_at = datetime.fromisoformat(
                last_analysis["created_at"].replace("Z", "+00:00")
            )
            age_minutes = (datetime.now(created_at.tzinfo) - created_at).total_seconds() / 60
            engine_active = age_minutes < 10
        
        return StatusResponse(
            engine_active=engine_active,
            pair=settings.trading_pair,
            analysis_interval_minutes=settings.analysis_interval_minutes,
            last_analysis=last_analysis,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals", response_model=SignalResponse)
async def get_signals(limit: int = 5):
    """
    Retorna os últimos N sinais para o dashboard.
    
    Args:
        limit: Número de sinais a retornar (default: 5, max: 50)
    """
    try:
        # Limita máximo de resultados
        limit = min(limit, 50)
        
        # Busca sinais no Supabase
        result = supabase_client.client.table("agent_decisions") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return SignalResponse(
            count=len(result.data),
            signals=result.data,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/entry")
async def get_entry_signals(limit: int = 10):
    """
    Retorna apenas sinais de ENTRY (BUY/SELL).
    Filtra HOLDs para exibir apenas operações reais.
    """
    try:
        limit = min(limit, 50)
        
        # Busca sinais de entrada no Supabase
        result = supabase_client.client.table("agent_decisions") \
            .select("*") \
            .or_("final_decision.eq.BUY_LONG,final_decision.eq.SELL_SHORT,final_decision.eq.BUY,final_decision.eq.SELL") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return {
            "count": len(result.data),
            "signals": result.data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== STARTUP ==============

@app.on_event("startup")
async def startup():
    """Executa ao iniciar a API."""
    print("=" * 60)
    print("🚀 3V Engine API Started")
    print(f"📊 Pair: {settings.trading_pair}")
    print("📚 Docs: http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
