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


# ============== ADMIN ENDPOINTS ==============

class ModelUpdateRequest(BaseModel):
    """Request para atualizar modelo."""
    model: str


@app.get("/admin/model")
async def get_active_model():
    """Retorna o modelo LLM ativo configurado no sistema."""
    try:
        result = supabase_client.client.table("system_settings") \
            .select("value") \
            .eq("key", "active_model") \
            .limit(1) \
            .execute()
        
        model = result.data[0]["value"] if result.data else settings.llm_model
        
        return {
            "model": model,
            "fallback": settings.llm_model,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "model": settings.llm_model,
            "fallback": settings.llm_model,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/admin/model")
async def set_active_model(request: ModelUpdateRequest):
    """Atualiza o modelo LLM ativo no sistema."""
    try:
        # Upsert - insere ou atualiza
        result = supabase_client.client.table("system_settings") \
            .upsert({
                "key": "active_model",
                "value": request.model,
                "updated_at": datetime.now().isoformat()
            }, on_conflict="key") \
            .execute()
        
        return {
            "success": True,
            "model": request.model,
            "message": f"Modelo atualizado para {request.model}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/model/test")
async def test_model_connection(request: ModelUpdateRequest):
    """Testa conexão com um modelo LLM específico."""
    import httpx
    
    try:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://3virgulas.com",
            "X-Title": "3V Engine - Model Test"
        }
        
        payload = {
            "model": request.model,
            "messages": [
                {"role": "user", "content": "Diga apenas 'OK, modelo funcionando!' em português."}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        return {
            "success": True,
            "model": request.model,
            "response": content,
            "tokens_used": data.get("usage", {}).get("total_tokens", 0),
            "timestamp": datetime.now().isoformat()
        }
        
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "model": request.model,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "model": request.model,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============== TRADING CONFIG ENDPOINTS ==============

class TradingConfigRequest(BaseModel):
    """Request para atualizar configurações de trading."""
    trading_mode: str | None = None  # AUTOMATIC ou SIGNAL_ONLY
    risk_per_trade: float | None = None  # % do capital
    max_daily_loss: float | None = None  # % máxima de perda


@app.get("/admin/trading")
async def get_trading_config():
    """
    Retorna configurações de trading automatizado.
    
    - trading_mode: AUTOMATIC (executa ordens) ou SIGNAL_ONLY (apenas sinais)
    - risk_per_trade: Percentual de risco por trade (ex: 1.0 = 1%)
    - max_daily_loss: Limite de perda diária (ex: 3.0 = 3%)
    """
    try:
        result = supabase_client.client.table("system_settings") \
            .select("key, value") \
            .in_("key", ["trading_mode", "risk_per_trade", "max_daily_loss"]) \
            .execute()
        
        # Converte para dict
        config = {
            "trading_mode": "SIGNAL_ONLY",
            "risk_per_trade": 1.0,
            "max_daily_loss": 3.0
        }
        
        for row in result.data:
            key = row["key"]
            value = row["value"]
            if key == "trading_mode":
                config["trading_mode"] = value
            elif key in ["risk_per_trade", "max_daily_loss"]:
                config[key] = float(value)
        
        return {
            "config": config,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/trading")
async def update_trading_config(request: TradingConfigRequest):
    """
    Atualiza configurações de trading automatizado.
    Apenas campos fornecidos serão atualizados.
    """
    try:
        updates = []
        
        if request.trading_mode is not None:
            if request.trading_mode not in ["AUTOMATIC", "SIGNAL_ONLY"]:
                raise HTTPException(400, "trading_mode deve ser AUTOMATIC ou SIGNAL_ONLY")
            updates.append(("trading_mode", request.trading_mode))
        
        if request.risk_per_trade is not None:
            if not 0.1 <= request.risk_per_trade <= 10.0:
                raise HTTPException(400, "risk_per_trade deve estar entre 0.1% e 10%")
            updates.append(("risk_per_trade", str(request.risk_per_trade)))
        
        if request.max_daily_loss is not None:
            if not 1.0 <= request.max_daily_loss <= 20.0:
                raise HTTPException(400, "max_daily_loss deve estar entre 1% e 20%")
            updates.append(("max_daily_loss", str(request.max_daily_loss)))
        
        if not updates:
            raise HTTPException(400, "Nenhum campo fornecido para atualização")
        
        # Upsert cada configuração
        for key, value in updates:
            supabase_client.client.table("system_settings").upsert({
                "key": key,
                "value": value,
                "updated_at": datetime.now().isoformat()
            }, on_conflict="key").execute()
        
        return {
            "success": True,
            "updated": dict(updates),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/account")
async def get_account_info():
    """
    Retorna informações da conta MT5 em tempo real.
    Para uso no dashboard de monitoramento.
    """
    try:
        from agents.execution_handler import execution_handler
        
        account_info = await execution_handler.get_account_info()
        
        return {
            "account": account_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "account": {"mode": "UNAVAILABLE", "error": str(e)},
            "timestamp": datetime.now().isoformat()
        }


@app.get("/admin/trades")
async def get_trade_history():
    """
    Retorna últimos 10 trades do execution_log.
    Para uso no dashboard de histórico.
    """
    try:
        result = supabase_client.client.table("execution_log") \
            .select("*") \
            .eq("type", "TRADE") \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute()
        
        return {
            "trades": result.data,
            "count": len(result.data),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "trades": [],
            "count": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============== STARTUP ==============

@app.on_event("startup")
async def startup():
    """Executa ao iniciar a API."""
    print("=" * 60)
    print("🚀 3V Engine API Started")
    print(f"📊 Pair: {settings.trading_pair}")
    print("📚 Docs: http://localhost:8000/docs")
    print("⚙️  Admin: http://localhost:3000/admin")
    print("🤖 Trading endpoints: /admin/trading")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

