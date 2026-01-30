#!/usr/bin/env python3
"""
3V Engine - Forex Multi-Agent System
=====================================
Sistema multi-agentes para análise e sinalização de operações no mercado Forex.
Desenvolvido sob a marca 3virgulas.

Uso:
    python main.py                    # Inicia loop de monitoramento
    python main.py --once             # Executa uma única análise
    python main.py --test             # Testa conexões com APIs
    python main.py --test-telegram    # Testa notificação Telegram

Author: 3Vírgulas Team
Version: 1.0.0
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import settings
from core.orchestrator import get_orchestrator
from utils.logger import logger


# Flag global para graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Handler para SIGINT (Ctrl+C)."""
    logger.warning("🛑 Shutdown signal received. Stopping gracefully...")
    shutdown_event.set()


async def run_once():
    """Executa uma única rodada de análise."""
    logger.info("=" * 60)
    logger.info("3V ENGINE - Single Analysis Mode")
    logger.info("=" * 60)
    
    orchestrator = get_orchestrator(pair=settings.trading_pair)
    result = await orchestrator.run_analysis()
    
    # Exibe resultado
    decision = result.get("final_decision", {})
    print("\n" + "=" * 60)
    print(f"📊 RESULT: {decision.get('decision', 'UNKNOWN')}")
    print(f"🎯 Direction: {decision.get('direction', 'N/A')}")
    print(f"💯 Confidence: {decision.get('confidence', 0)}%")
    print(f"📝 Reasoning: {decision.get('reasoning', 'N/A')}")
    print("=" * 60 + "\n")
    
    return result


async def test_telegram():
    """Envia mensagem de teste para o Telegram."""
    from utils.telegram_bot import telegram_bot
    
    print("\n" + "=" * 60)
    print("📱 TELEGRAM TEST - Sending test BUY signal...")
    print("=" * 60 + "\n")
    
    # Simula um sinal de BUY para teste
    success = await telegram_bot.notify_trade_signal(
        decision="BUY",
        direction="LONG",
        confidence=88,
        reasoning="[TESTE] Entrada validada por convergência técnica e sentimento positivo, sem riscos macro próximos.",
        pair="EUR/USD",
        inputs={
            "technical": {"signal": "BULLISH"},
            "sentiment": {"score": 0.45},
            "macro": {"alert": "LOW_RISK"}
        }
    )
    
    if success:
        print("✅ Mensagem enviada com sucesso! Verifique seu Telegram.")
    else:
        print("❌ Falha ao enviar. Verifique TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env")
    
    return success


async def run_monitoring_loop():
    """Inicia loop de monitoramento contínuo."""
    logger.info("=" * 60)
    logger.info("🚀 3V ENGINE - Continuous Monitoring Mode")
    logger.info(f"💱 Pair: {settings.trading_pair}")
    logger.info(f"⏱️  Interval: {settings.analysis_interval_minutes} minutes")
    logger.info("=" * 60)
    
    orchestrator = get_orchestrator(pair=settings.trading_pair)
    analysis_count = 0
    
    try:
        while not shutdown_event.is_set():
            analysis_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Starting analysis #{analysis_count}")
            logger.info(f"{'='*60}")
            
            try:
                result = await orchestrator.run_analysis()
                
                # Exibe resultado resumido
                decision = result.get("final_decision", {})
                print(f"\n✅ Analysis #{analysis_count} Complete:")
                print(f"   📊 Decision: {decision.get('decision', 'UNKNOWN')}")
                print(f"   🎯 Direction: {decision.get('direction', 'N/A')}")
                print(f"   💯 Confidence: {decision.get('confidence', 0)}%")
                
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}")
            
            # Verifica shutdown antes de aguardar
            if shutdown_event.is_set():
                break
            
            # Aguarda com countdown
            interval_seconds = settings.analysis_interval_minutes * 60
            logger.info(f"\n💤 Aguardando {settings.analysis_interval_minutes} minutos para a próxima análise...")
            
            # Countdown a cada 60 segundos
            for remaining in range(interval_seconds, 0, -60):
                if shutdown_event.is_set():
                    break
                
                minutes_left = remaining // 60
                if minutes_left > 0:
                    print(f"   ⏱️  Próxima análise em {minutes_left} minuto(s)...", end="\r")
                
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=min(60, remaining)
                    )
                    break  # Shutdown received
                except asyncio.TimeoutError:
                    pass  # Continue countdown
            
            print("   " + " " * 50, end="\r")  # Limpa linha
            
    finally:
        orchestrator.stop()
        logger.info("🛑 3V Engine stopped successfully")


async def test_connections():
    """Testa conexões com todas as APIs."""
    logger.info("=" * 60)
    logger.info("3V ENGINE - Connection Test")
    logger.info("=" * 60)
    
    from utils.twelve_data import twelve_data_client
    from utils.finnhub import finnhub_client
    from utils.forex_factory import forex_factory_client
    
    results = {}
    
    # Teste Twelve Data
    print("\n🔌 Testing Twelve Data API...")
    results["twelve_data"] = await twelve_data_client.test_connection()
    
    # Teste Finnhub (News)
    print("\n🔌 Testing Finnhub API (News)...")
    results["finnhub"] = await finnhub_client.test_connection()
    
    # Teste Forex Factory (Calendar)
    print("\n🔌 Testing Forex Factory (Calendar)...")
    results["forex_factory"] = await forex_factory_client.test_connection()
    
    # Teste Supabase
    print("\n🔌 Testing Supabase connection...")
    try:
        from core.supabase_client import supabase_client
        # Tenta uma query simples
        supabase_client.client.table("agent_decisions").select("id").limit(1).execute()
        print("✅ Supabase Connection OK")
        results["supabase"] = True
    except Exception as e:
        print(f"❌ Supabase Connection FAILED: {e}")
        results["supabase"] = False
    
    # Resumo
    print("\n" + "=" * 60)
    print("CONNECTION TEST SUMMARY")
    print("=" * 60)
    for service, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"  {emoji} {service}: {'OK' if status else 'FAILED'}")
    print("=" * 60 + "\n")
    
    all_ok = all(results.values())
    return all_ok


def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="3V Engine - Forex Multi-Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              Start continuous monitoring
  python main.py --once       Run single analysis
  python main.py --test       Test API connections
        """
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single analysis cycle and exit"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connections to all APIs"
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send test notification to Telegram"
    )
    parser.add_argument(
        "--pair",
        type=str,
        default=None,
        help="Trading pair to analyze (default: from .env)"
    )
    
    args = parser.parse_args()
    
    # Override do par se especificado
    if args.pair:
        import os
        os.environ["TRADING_PAIR"] = args.pair
    
    # Registra handler de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Executa modo selecionado
    if args.test:
        success = asyncio.run(test_connections())
        sys.exit(0 if success else 1)
    elif args.test_telegram:
        success = asyncio.run(test_telegram())
        sys.exit(0 if success else 1)
    elif args.once:
        asyncio.run(run_once())
    else:
        asyncio.run(run_monitoring_loop())


if __name__ == "__main__":
    main()
