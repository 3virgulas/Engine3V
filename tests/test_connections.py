#!/usr/bin/env python3
"""
3V Engine - Connection Tests
=============================
Script de teste para validar conexões com todas as APIs externas.

Uso:
    python tests/test_connections.py
    
    Ou via pytest:
    pytest tests/test_connections.py -v
"""

import asyncio
import sys
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestTwelveDataConnection:
    """Testes de conexão com Twelve Data API."""
    
    @pytest.mark.asyncio
    async def test_twelve_data_connection(self):
        """Testa conexão básica com Twelve Data."""
        from utils.twelve_data import twelve_data_client
        
        result = await twelve_data_client.test_connection()
        assert result is True, "Twelve Data connection failed"
    
    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """Testa obtenção de preço atual."""
        from utils.twelve_data import twelve_data_client
        
        price = await twelve_data_client.get_current_price()
        assert "price" in price
        assert isinstance(price["price"], float)
        assert price["price"] > 0
    
    @pytest.mark.asyncio
    async def test_technical_analysis(self):
        """Testa análise técnica completa."""
        from utils.twelve_data import twelve_data_client
        
        analysis = await twelve_data_client.get_technical_analysis()
        
        assert "current_price" in analysis
        assert "moving_averages" in analysis
        assert "rsi" in analysis
        assert "bollinger_bands" in analysis


class TestFinnhubConnection:
    """Testes de conexão com Finnhub API (apenas News)."""
    
    @pytest.mark.asyncio
    async def test_finnhub_connection(self):
        """Testa conexão básica com Finnhub (news)."""
        from utils.finnhub import finnhub_client
        
        result = await finnhub_client.test_connection()
        assert result is True, "Finnhub connection failed"
    
    @pytest.mark.asyncio
    async def test_get_news_sentiment(self):
        """Testa obtenção de sentimento de notícias."""
        from utils.finnhub import finnhub_client
        
        sentiment = await finnhub_client.get_news_sentiment()
        
        assert "score" in sentiment
        assert "label" in sentiment
        assert sentiment["score"] >= -1 and sentiment["score"] <= 1


class TestForexFactoryConnection:
    """Testes de conexão com Forex Factory RSS."""
    
    @pytest.mark.asyncio
    async def test_forex_factory_connection(self):
        """Testa conexão com RSS do Forex Factory."""
        from utils.forex_factory import forex_factory_client
        
        result = await forex_factory_client.test_connection()
        assert result is True, "Forex Factory connection failed"
    
    @pytest.mark.asyncio
    async def test_get_high_impact_events(self):
        """Testa obtenção de eventos de alto impacto."""
        from utils.forex_factory import forex_factory_client
        
        events = await forex_factory_client.get_upcoming_high_impact_events()
        
        assert "alert" in events
        assert "message" in events
        assert events["alert"] in ["EXTREME_RISK", "HIGH_RISK", "MODERATE_RISK", "LOW_RISK"]


class TestSupabaseConnection:
    """Testes de conexão com Supabase."""
    
    def test_supabase_connection(self):
        """Testa conexão básica com Supabase."""
        try:
            from core.supabase_client import supabase_client
            
            # Tenta uma query simples
            result = supabase_client.client.table("agent_decisions").select("id").limit(1).execute()
            assert result is not None
        except Exception as e:
            pytest.skip(f"Supabase not configured or table not created: {e}")


async def run_all_tests():
    """Executa todos os testes de conexão."""
    print("\n" + "=" * 60)
    print("3V ENGINE - CONNECTION TESTS")
    print("=" * 60 + "\n")
    
    tests = [
        ("Twelve Data", test_twelve_data),
        ("Finnhub (News)", test_finnhub),
        ("Forex Factory (Calendar)", test_forex_factory),
        ("Supabase", test_supabase),
    ]
    
    results = {}
    
    for name, test_func in tests:
        print(f"🔌 Testing {name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            print(f"   ✅ {name}: OK")
            results[name] = True
        except Exception as e:
            print(f"   ❌ {name}: FAILED - {e}")
            results[name] = False
    
    print("\n" + "=" * 60)
    print("CONNECTION TEST SUMMARY")
    print("=" * 60)
    
    for name, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"  {emoji} {name}: {'PASSED' if status else 'FAILED'}")
    
    print("=" * 60 + "\n")
    
    return all(results.values())


async def test_twelve_data():
    """Teste individual Twelve Data."""
    from utils.twelve_data import twelve_data_client
    assert await twelve_data_client.test_connection()


async def test_finnhub():
    """Teste individual Finnhub (News)."""
    from utils.finnhub import finnhub_client
    assert await finnhub_client.test_connection()


async def test_forex_factory():
    """Teste individual Forex Factory Calendar."""
    from utils.forex_factory import forex_factory_client
    assert await forex_factory_client.test_connection()


def test_supabase():
    """Teste individual Supabase."""
    from core.supabase_client import supabase_client
    result = supabase_client.client.table("agent_decisions").select("id").limit(1).execute()
    assert result is not None


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
