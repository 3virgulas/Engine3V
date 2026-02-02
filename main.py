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
    python main.py --force-buy        # Força ordem BUY para testar execução

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
    """Inicia loop de monitoramento contínuo com execução automática opcional."""
    logger.info("=" * 60)
    logger.info("🚀 3V ENGINE - Continuous Monitoring Mode")
    logger.info(f"💱 Pair: {settings.trading_pair}")
    logger.info(f"⏱️  Interval: {settings.analysis_interval_minutes} minutes")
    logger.info("=" * 60)
    
    from agents.execution_handler import execution_handler
    from core.supabase_client import supabase_client
    from utils.telegram_bot import telegram_bot
    from utils.twelve_data import twelve_data_client
    from datetime import datetime, timedelta
    
    orchestrator = get_orchestrator(pair=settings.trading_pair)
    analysis_count = 0
    
    # ============== PENDING ENTRIES QUEUE ==============
    # Armazena sinais pendentes para enviar confirmação no horário de entrada
    pending_entries = []
    
    async def check_and_send_entry_confirmations():
        """Verifica e envia notificações de confirmação de entrada agendadas."""
        nonlocal pending_entries
        now = datetime.now()
        entries_to_remove = []
        
        for idx, entry in enumerate(pending_entries):
            scheduled_time = entry.get("scheduled_time")
            
            # Verifica se já passou do horário de entrada
            if now >= scheduled_time:
                logger.info(f"⏰ Entry confirmation time reached for {entry.get('pair')}")
                
                try:
                    # Busca preço atual
                    current_price = await get_current_price(entry.get("pair"))
                    
                    if current_price:
                        # Recalcula TP/SL baseado no preço atual se necessário
                        await telegram_bot.notify_entry_confirmation(
                            decision=entry.get("decision"),
                            direction=entry.get("direction"),
                            pair=entry.get("pair"),
                            entry_price=current_price,
                            take_profit=entry.get("take_profit"),
                            stop_loss=entry.get("stop_loss"),
                            confidence=entry.get("confidence"),
                            reasoning=entry.get("reasoning")
                        )
                        logger.info(f"✅ Entry confirmation sent for {entry.get('decision')}")
                    else:
                        logger.warning(f"⚠️ Could not get current price for entry confirmation")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to send entry confirmation: {e}")
                
                entries_to_remove.append(idx)
        
        # Remove entradas processadas (em ordem reversa para não bagunçar índices)
        for idx in reversed(entries_to_remove):
            pending_entries.pop(idx)
    
    async def get_current_price(pair: str) -> float | None:
        """Obtém preço atual do par via API."""
        try:
            data = await twelve_data_client.get_price_data(
                pair.replace("/", ""),
                interval="1min",
                outputsize=1
            )
            if data and len(data) > 0:
                return data[0].get("close")
        except Exception as e:
            logger.warning(f"Failed to get current price: {e}")
        return None
    
    def schedule_entry_confirmation(decision_data: dict):
        """Agenda uma notificação de confirmação de entrada."""
        scheduled_entry = decision_data.get("scheduled_entry", {})
        exit_levels = decision_data.get("exit_levels", {})
        
        if not scheduled_entry or not scheduled_entry.get("start_iso"):
            logger.warning("No scheduled entry time, skipping confirmation scheduling")
            return
        
        try:
            # Parse do horário de entrada
            start_iso = scheduled_entry.get("start_iso")
            scheduled_time = datetime.fromisoformat(start_iso)
            
            entry = {
                "scheduled_time": scheduled_time,
                "decision": decision_data.get("decision"),
                "direction": decision_data.get("direction"),
                "pair": settings.trading_pair,
                "take_profit": exit_levels.get("take_profit", 0),
                "stop_loss": exit_levels.get("stop_loss", 0),
                "confidence": decision_data.get("confidence", 0),
                "reasoning": decision_data.get("reasoning", "")
            }
            
            pending_entries.append(entry)
            logger.info(f"📅 Entry confirmation scheduled for {scheduled_time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to schedule entry confirmation: {e}")
    
    # Conecta ao MT5 (modo simulação em macOS)
    await execution_handler.connect()
    
    async def get_trading_config():
        """Obtém configurações de trading do Supabase."""
        try:
            result = supabase_client.client.table("system_settings") \
                .select("key, value") \
                .in_("key", ["trading_mode", "risk_per_trade", "max_daily_loss"]) \
                .execute()
            
            config = {
                "trading_mode": "SIGNAL_ONLY",
                "risk_per_trade": 1.0,
                "max_daily_loss": 3.0
            }
            
            for row in result.data:
                if row["key"] == "trading_mode":
                    config["trading_mode"] = row["value"]
                elif row["key"] in ["risk_per_trade", "max_daily_loss"]:
                    config[row["key"]] = float(row["value"])
            
            return config
        except Exception as e:
            logger.warning(f"Failed to get trading config: {e}")
            return {"trading_mode": "SIGNAL_ONLY", "risk_per_trade": 1.0, "max_daily_loss": 3.0}
    
    try:
        while not shutdown_event.is_set():
            analysis_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Starting analysis #{analysis_count}")
            logger.info(f"{'='*60}")
            
            try:
                # ============== CHECK PENDING ENTRY CONFIRMATIONS ==============
                # Verifica se há notificações de confirmação agendadas para enviar
                await check_and_send_entry_confirmations()
                
                # ============== MONITOR OPEN TRADES ==============
                # Sempre monitora trades abertos, independente de novos sinais
                monitor_result = await execution_handler.monitor_open_trades()
                trades_monitored = monitor_result.get("trades_monitored", 0)
                if trades_monitored > 0:
                    trades_updated = monitor_result.get("trades_updated", 0)
                    trades_closed = monitor_result.get("trades_closed", 0)
                    logger.info(f"📈 Trades monitorados: {trades_monitored} | Atualizados: {trades_updated} | Fechados: {trades_closed}")
                
                # ============== TRADING CONFIG ==============
                # Obtém configurações de trading
                trading_config = await get_trading_config()
                trading_mode = trading_config["trading_mode"]
                risk_percent = trading_config["risk_per_trade"]
                max_daily_loss = trading_config["max_daily_loss"]
                
                logger.info(f"🤖 Trading Mode: {trading_mode}")
                
                # Verifica limite de perda diária
                if trading_mode == "AUTOMATIC":
                    limit_reached = await execution_handler.check_daily_loss_limit(max_daily_loss)
                    if limit_reached:
                        logger.warning("⚠️ Daily loss limit reached! Switching to SIGNAL_ONLY mode.")
                        trading_mode = "SIGNAL_ONLY"
                
                # Executa análise
                result = await orchestrator.run_analysis()
                
                # Exibe resultado resumido
                decision = result.get("final_decision", {})
                decision_type = decision.get("decision", "UNKNOWN")
                direction = decision.get("direction")
                confidence = decision.get("confidence", 0)
                
                print(f"\n✅ Analysis #{analysis_count} Complete:")
                print(f"   📊 Decision: {decision_type}")
                print(f"   🎯 Direction: {direction or 'N/A'}")
                print(f"   💯 Confidence: {confidence}%")
                
                # ============== AUTOMATIC EXECUTION ==============
                if trading_mode == "AUTOMATIC" and decision_type in ["BUY", "SELL"]:
                    exit_levels = decision.get("exit_levels", {})
                    
                    if exit_levels.get("take_profit") and exit_levels.get("stop_loss"):
                        logger.warning(f"🤖 AUTOMATIC MODE: Executing {decision_type} order...")
                        
                        # Converte par para formato MT5 (EUR/USD -> EURUSD)
                        mt5_symbol = settings.trading_pair.replace("/", "")
                        
                        trade_result = await execution_handler.place_trade(
                            symbol=mt5_symbol,
                            direction=direction,
                            stop_loss=exit_levels["stop_loss"],
                            take_profit=exit_levels["take_profit"],
                            risk_percent=risk_percent
                        )
                        
                        if trade_result.get("success"):
                            print(f"   🎯 ORDER PLACED: Ticket #{trade_result.get('ticket')}")
                            print(f"   📈 Entry: {trade_result.get('price')}")
                            print(f"   🛡️ SL: {exit_levels['stop_loss']} | TP: {exit_levels['take_profit']}")
                        else:
                            print(f"   ❌ ORDER FAILED: {trade_result.get('error')}")
                    else:
                        logger.warning("⚠️ Exit levels not available, skipping execution")
                
                elif trading_mode == "SIGNAL_ONLY":
                    if decision_type in ["BUY", "SELL"]:
                        print(f"   📱 Signal sent via Telegram (SIGNAL_ONLY mode)")
                        # Agenda notificação de confirmação para o horário de entrada
                        schedule_entry_confirmation(decision)
                
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}")
            
            # Verifica shutdown antes de aguardar
            if shutdown_event.is_set():
                break
            
            # Aguarda com countdown
            interval_seconds = settings.analysis_interval_minutes * 60
            logger.info(f"\n💤 Aguardando {settings.analysis_interval_minutes} minutos para a próxima análise...")
            
            # Countdown a cada 30 segundos (para verificar confirmações pendentes)
            for remaining in range(interval_seconds, 0, -30):
                if shutdown_event.is_set():
                    break
                
                # Verifica confirmações pendentes a cada iteração
                await check_and_send_entry_confirmations()
                
                minutes_left = remaining // 60
                if minutes_left > 0:
                    print(f"   ⏱️  Próxima análise em {minutes_left} minuto(s)...", end="\r")
                
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=min(30, remaining)
                    )
                    break  # Shutdown received
                except asyncio.TimeoutError:
                    pass  # Continue countdown
            
            print("   " + " " * 50, end="\r")  # Limpa linha
            
    finally:
        execution_handler.disconnect()
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


async def force_buy():
    """
    Força uma ordem BUY para testar o execution_handler.
    Pula toda a análise e envia sinal fictício diretamente.
    """
    from agents.execution_handler import execution_handler
    
    print("\n" + "=" * 60)
    print("🧪 FORCE BUY TEST - Testing Execution Handler")
    print("=" * 60)
    
    # Conecta ao MT5 (ou modo simulação)
    await execution_handler.connect()
    
    # Sinal fictício para teste
    fake_signal = {
        "decision": "BUY",
        "direction": "LONG",
        "confidence": 99,
        "exit_levels": {
            "take_profit": 1.0900,
            "stop_loss": 1.0800
        }
    }
    
    print(f"\n📊 Fake Signal:")
    print(f"   Direction: {fake_signal['direction']}")
    print(f"   Confidence: {fake_signal['confidence']}%")
    print(f"   TP: {fake_signal['exit_levels']['take_profit']}")
    print(f"   SL: {fake_signal['exit_levels']['stop_loss']}")
    print("\n🚀 Sending to execution_handler.place_trade()...\n")
    
    # Converte par para formato MT5
    mt5_symbol = settings.trading_pair.replace("/", "")
    
    result = await execution_handler.place_trade(
        symbol=mt5_symbol,
        direction=fake_signal["direction"],
        stop_loss=fake_signal["exit_levels"]["stop_loss"],
        take_profit=fake_signal["exit_levels"]["take_profit"],
        risk_percent=1.0
    )
    
    print("\n" + "=" * 60)
    if result.get("success"):
        print("✅ ORDER PLACED SUCCESSFULLY")
        print(f"   Mode: {result.get('mode')}")
        print(f"   Ticket: {result.get('ticket')}")
        print(f"   Volume: {result.get('volume')} lots")
        print(f"   Entry Price: {result.get('price')}")
        print(f"   Stop Loss: {result.get('stop_loss')}")
        print(f"   Take Profit: {result.get('take_profit')}")
    else:
        print("❌ ORDER FAILED")
        print(f"   Error: {result.get('error')}")
    print("=" * 60 + "\n")
    
    execution_handler.disconnect()
    return result


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
        "--force-buy",
        action="store_true",
        help="Force a BUY order to test execution handler"
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
    elif args.force_buy:
        asyncio.run(force_buy())
        sys.exit(0)
    elif args.once:
        asyncio.run(run_once())
    else:
        asyncio.run(run_monitoring_loop())


if __name__ == "__main__":
    main()
