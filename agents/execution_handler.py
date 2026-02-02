"""
3V Engine - Execution Handler Agent
====================================
@Execution_Handler: Responsável pela execução automatizada no MetaTrader 5.
Gerencia conexão, ordens, trailing stop e informações de conta.

IMPORTANTE: MetaTrader5 só funciona no Windows.
No macOS/Linux, opera em modo simulação (loga sem executar).
"""

import asyncio
import sys
from datetime import datetime, date
from typing import Any, Literal

from agents.base import BaseAgent
from core.supabase_client import supabase_client
from utils.logger import log_agent_action

# Tenta importar MetaTrader5 (só disponível no Windows)
MT5_AVAILABLE = False
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None


TradeDirection = Literal["LONG", "SHORT"]


class ExecutionHandlerAgent(BaseAgent):
    """
    @Execution_Handler - Executor de Ordens MT5
    
    Responsabilidades:
    - Conectar ao terminal MetaTrader 5
    - Calcular lote baseado em risco percentual
    - Abrir/fechar ordens com SL/TP
    - Gerenciar trailing stop dinâmico
    - Monitorar saldo e P&L diário
    
    Segurança:
    - Retry automático em caso de desconexão
    - Limite de perda diária (max_daily_loss)
    - Log de todas as operações no Supabase
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 5.0
    
    def __init__(self) -> None:
        super().__init__()
        self._connected = False
        self._simulation_mode = not MT5_AVAILABLE
        self._daily_pnl = 0.0
        self._daily_pnl_date = date.today()
        self._open_orders: list[int] = []  # Lista de tickets
    
    @property
    def name(self) -> str:
        return "@Execution_Handler"
    
    @property
    def role(self) -> str:
        return """Executor de ordens no MetaTrader 5.
        
Você é responsável por:
1. Executar ordens de compra/venda no terminal MT5
2. Calcular tamanho de lote baseado em risco percentual
3. Gerenciar Stop Loss e Take Profit
4. Implementar Trailing Stop dinâmico
5. Monitorar P&L diário e pausar se limite atingido"""
    
    async def analyze(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """Não usado - este agent usa métodos específicos."""
        return {"status": "execution_handler_ready", "connected": self._connected}
    
    # ============== CONNECTION ==============
    
    async def connect(self) -> bool:
        """
        Conecta ao terminal MetaTrader 5 com retry logic.
        
        Returns:
            True se conectado com sucesso
        """
        if self._simulation_mode:
            self.log("Running in SIMULATION mode (MT5 not available on this OS)")
            self._connected = True
            return True
        
        for attempt in range(self.MAX_RETRIES):
            try:
                if not mt5.initialize():
                    raise ConnectionError(f"MT5 initialize failed: {mt5.last_error()}")
                
                # Verifica se está conectado a uma conta
                account_info = mt5.account_info()
                if account_info is None:
                    raise ConnectionError("No account connected to MT5")
                
                self._connected = True
                self.log("Connected to MT5", {
                    "account": account_info.login,
                    "broker": account_info.company,
                    "balance": account_info.balance
                })
                
                return True
                
            except Exception as e:
                self.log(f"Connection attempt {attempt + 1}/{self.MAX_RETRIES} failed: {e}", 
                        level="warning")
                
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    self._connected = False
                    await self._log_error_to_supabase("CONNECTION_FAILED", str(e))
                    return False
        
        return False
    
    def disconnect(self) -> None:
        """Desconecta do MT5."""
        if MT5_AVAILABLE and not self._simulation_mode:
            mt5.shutdown()
        self._connected = False
        self.log("Disconnected from MT5")
    
    # ============== ACCOUNT INFO ==============
    
    async def get_account_info(self) -> dict[str, Any]:
        """
        Obtém informações da conta em tempo real.
        
        Returns:
            Dict com balance, equity, margin, free_margin, daily_pnl
        """
        if self._simulation_mode:
            return {
                "mode": "SIMULATION",
                "balance": 10000.0,
                "equity": 10000.0,
                "margin": 0.0,
                "free_margin": 10000.0,
                "daily_pnl": self._daily_pnl,
                "daily_pnl_percent": 0.0,
                "open_positions": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        if not self._connected:
            await self.connect()
        
        try:
            account = mt5.account_info()
            if account is None:
                raise ValueError("Failed to get account info")
            
            # Calcula P&L diário
            daily_pnl_percent = (self._daily_pnl / account.balance * 100) if account.balance > 0 else 0
            
            return {
                "mode": "LIVE",
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "free_margin": account.margin_free,
                "profit": account.profit,
                "daily_pnl": self._daily_pnl,
                "daily_pnl_percent": round(daily_pnl_percent, 2),
                "open_positions": mt5.positions_total(),
                "leverage": account.leverage,
                "currency": account.currency,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.log(f"Error getting account info: {e}", level="error")
            return {"error": str(e)}
    
    # ============== TRADING ==============
    
    def _calculate_lot_size(
        self,
        symbol: str,
        stop_loss_pips: float,
        risk_percent: float,
        account_balance: float
    ) -> float:
        """
        Calcula tamanho do lote baseado em risco percentual.
        
        Fórmula: Lot = (Balance * Risk%) / (SL_pips * Pip_value)
        
        Args:
            symbol: Par de moedas (ex: EURUSD)
            stop_loss_pips: Distância do SL em pips
            risk_percent: Percentual de risco (1.0 = 1%)
            account_balance: Saldo da conta
        
        Returns:
            Tamanho do lote (arredondado para 2 decimais)
        """
        if self._simulation_mode:
            # Simulação: retorna lote fixo pequeno
            return 0.01
        
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                self.log(f"Symbol {symbol} not found", level="error")
                return 0.01  # Lote mínimo
            
            # Valor do pip por lote standard
            pip_value = symbol_info.trade_tick_value * 10  # Assumindo 4 dígitos
            
            # Risco em valor monetário
            risk_amount = account_balance * (risk_percent / 100)
            
            # Calcula lote
            if stop_loss_pips <= 0 or pip_value <= 0:
                return 0.01
            
            lot_size = risk_amount / (stop_loss_pips * pip_value)
            
            # Respeita limites do símbolo
            lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
            
            # Arredonda para step do símbolo
            lot_step = symbol_info.volume_step
            lot_size = round(lot_size / lot_step) * lot_step
            
            return round(lot_size, 2)
            
        except Exception as e:
            self.log(f"Lot calculation error: {e}", level="error")
            return 0.01
    
    async def place_trade(
        self,
        symbol: str,
        direction: TradeDirection,
        stop_loss: float,
        take_profit: float,
        risk_percent: float = 1.0
    ) -> dict[str, Any]:
        """
        Abre uma ordem no MT5.
        
        Args:
            symbol: Par de moedas (ex: EURUSD)
            direction: LONG ou SHORT
            stop_loss: Preço do Stop Loss
            take_profit: Preço do Take Profit
            risk_percent: Percentual de risco por trade
        
        Returns:
            Dict com resultado da ordem (ticket, price, etc)
        """
        self.log(f"Placing {direction} trade", {
            "symbol": symbol,
            "sl": stop_loss,
            "tp": take_profit,
            "risk": f"{risk_percent}%"
        })
        
        if self._simulation_mode:
            # Modo simulação
            simulated_ticket = int(datetime.now().timestamp())
            result = {
                "success": True,
                "mode": "SIMULATION",
                "ticket": simulated_ticket,
                "symbol": symbol,
                "direction": direction,
                "volume": 0.01,
                "price": 1.08500,  # Preço simulado
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "timestamp": datetime.now().isoformat()
            }
            
            self._open_orders.append(simulated_ticket)
            await self._log_trade_to_supabase(result)
            
            self.log("SIMULATED order placed", result)
            return result
        
        if not self._connected:
            await self.connect()
        
        try:
            # Obtém preço atual
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise ValueError(f"Cannot get price for {symbol}")
            
            # Determina tipo de ordem e preço
            if direction == "LONG":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            
            # Calcula distância do SL em pips
            sl_distance = abs(price - stop_loss)
            symbol_info = mt5.symbol_info(symbol)
            point = symbol_info.point if symbol_info else 0.0001
            sl_pips = sl_distance / (point * 10)  # Converte para pips
            
            # Obtém saldo e calcula lote
            account = mt5.account_info()
            lot_size = self._calculate_lot_size(
                symbol=symbol,
                stop_loss_pips=sl_pips,
                risk_percent=risk_percent,
                account_balance=account.balance
            )
            
            # Prepara requisição
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,
                "magic": 3333,  # Magic number do 3V Engine
                "comment": "3V Engine Auto",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Envia ordem
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Order failed: {result.retcode} - {result.comment}"
                await self._log_error_to_supabase("ORDER_FAILED", error_msg)
                return {"success": False, "error": error_msg}
            
            trade_result = {
                "success": True,
                "mode": "LIVE",
                "ticket": result.order,
                "symbol": symbol,
                "direction": direction,
                "volume": lot_size,
                "price": result.price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "timestamp": datetime.now().isoformat()
            }
            
            self._open_orders.append(result.order)
            await self._log_trade_to_supabase(trade_result)
            
            self.log("Order placed successfully", trade_result, level="warning")
            return trade_result
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"Trade error: {error_msg}", level="error")
            await self._log_error_to_supabase("TRADE_ERROR", error_msg)
            return {"success": False, "error": error_msg}
    
    async def close_trade(self, ticket: int) -> dict[str, Any]:
        """
        Fecha uma ordem específica.
        
        Args:
            ticket: Número do ticket da ordem
        
        Returns:
            Dict com resultado do fechamento
        """
        self.log(f"Closing trade #{ticket}")
        
        if self._simulation_mode:
            if ticket in self._open_orders:
                self._open_orders.remove(ticket)
            return {
                "success": True,
                "mode": "SIMULATION",
                "ticket": ticket,
                "message": "Simulated close",
                "timestamp": datetime.now().isoformat()
            }
        
        if not self._connected:
            await self.connect()
        
        try:
            # Obtém posição
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return {"success": False, "error": f"Position {ticket} not found"}
            
            position = position[0]
            
            # Determina tipo de fechamento (inverso)
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            tick = mt5.symbol_info_tick(position.symbol)
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 3333,
                "comment": "3V Engine Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"success": False, "error": f"Close failed: {result.comment}"}
            
            # Atualiza P&L diário
            profit = position.profit
            self._update_daily_pnl(profit)
            
            if ticket in self._open_orders:
                self._open_orders.remove(ticket)
            
            return {
                "success": True,
                "mode": "LIVE",
                "ticket": ticket,
                "profit": profit,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.log(f"Close error: {e}", level="error")
            return {"success": False, "error": str(e)}
    
    async def update_trailing_stop(
        self,
        ticket: int,
        trailing_pips: float = 20
    ) -> dict[str, Any]:
        """
        Atualiza trailing stop de uma posição.
        
        Args:
            ticket: Número do ticket
            trailing_pips: Distância do trailing stop em pips
        
        Returns:
            Dict com resultado da modificação
        """
        if self._simulation_mode:
            return {"success": True, "mode": "SIMULATION", "message": "Trailing stop updated"}
        
        if not self._connected:
            await self.connect()
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return {"success": False, "error": "Position not found"}
            
            position = position[0]
            symbol_info = mt5.symbol_info(position.symbol)
            point = symbol_info.point
            
            tick = mt5.symbol_info_tick(position.symbol)
            
            # Calcula novo SL baseado na direção
            if position.type == mt5.ORDER_TYPE_BUY:
                new_sl = tick.bid - (trailing_pips * point * 10)
                # Só move se novo SL for maior que atual
                if new_sl <= position.sl:
                    return {"success": True, "message": "No update needed"}
            else:
                new_sl = tick.ask + (trailing_pips * point * 10)
                if new_sl >= position.sl:
                    return {"success": True, "message": "No update needed"}
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": ticket,
                "sl": new_sl,
                "tp": position.tp,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"success": False, "error": f"Modify failed: {result.comment}"}
            
            self.log(f"Trailing stop updated for #{ticket}", {"new_sl": new_sl})
            return {"success": True, "new_sl": new_sl}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== TRADE MONITORING ==============
    
    async def _get_current_price(self, symbol: str) -> float:
        """
        Obtém preço atual do par.
        
        Tenta via TwelveData, se falhar simula flutuação para mercado fechado.
        
        Args:
            symbol: Símbolo do par (ex: EURUSD)
        
        Returns:
            Preço atual (ou simulado)
        """
        import random
        from utils.twelve_data import twelve_data_client
        
        try:
            # Tenta obter preço real
            price_data = await twelve_data_client.get_current_price()
            return price_data.get("price", 1.0850)
        except Exception as e:
            self.log(f"Failed to get real price, using simulation: {e}", level="warning")
            # Simula flutuação pequena
            base_price = 1.0850  # Preço base para simulação
            return base_price * (1 + random.uniform(-0.0005, 0.0005))
    
    async def _close_trade_with_notification(
        self,
        trade: dict[str, Any],
        reason: str,
        current_price: float,
        profit: float
    ) -> bool:
        """
        Fecha trade no Supabase e envia notificação Telegram.
        
        Args:
            trade: Dados do trade do Supabase
            reason: "TAKE_PROFIT" ou "STOP_LOSS"
            current_price: Preço de saída
            profit: Lucro/prejuízo final
        
        Returns:
            True se fechado com sucesso
        """
        from utils.telegram_bot import telegram_bot
        
        try:
            ticket = trade.get("ticket")
            symbol = trade.get("symbol", "EURUSD")
            entry_price = trade.get("entry_price", 0)
            direction = trade.get("direction", "LONG")
            
            # Atualiza status no Supabase (apenas colunas existentes)
            supabase_client.client.table("execution_log").update({
                "status": "CLOSED",
                "profit": round(profit, 2),
                "data": {
                    **trade.get("data", {}),
                    "exit_price": current_price,
                    "closed_at": datetime.now().isoformat(),
                    "close_reason": reason
                }
            }).eq("ticket", ticket).execute()
            
            # Remove da lista de ordens abertas
            if ticket in self._open_orders:
                self._open_orders.remove(ticket)
            
            # Atualiza P&L diário
            self._update_daily_pnl(profit)
            
            # Monta mensagem de notificação
            if reason == "TAKE_PROFIT":
                emoji = "💰"
                header = "TAKE PROFIT ATINGIDO"
                color_emoji = "🟢" if profit > 0 else "🔴"
            else:
                emoji = "🛑"
                header = "STOP LOSS ATINGIDO"
                color_emoji = "🔴" if profit < 0 else "🟢"
            
            message = f"""
{emoji} <b>3V ENGINE - {header}</b>
━━━━━━━━━━━━━━━━━

📊 <b>Par:</b> {symbol}
📈 <b>Direção:</b> {direction}

💵 <b>Entrada:</b> {entry_price:.5f}
🎯 <b>Saída:</b> {current_price:.5f}

{color_emoji} <b>Resultado:</b> ${profit:.2f}
🎫 <b>Ticket:</b> #{ticket}

🕐 {datetime.now().strftime("%H:%M:%S")} (GMT-3)
━━━━━━━━━━━━━━━━━
<code>3V Engine • Trade Fechado</code>
"""
            
            await telegram_bot._send_message(message.strip())
            
            self.log(f"Trade #{ticket} closed: {reason}, profit: ${profit:.2f}")
            return True
            
        except Exception as e:
            self.log(f"Failed to close trade with notification: {e}", level="error")
            return False
    
    async def monitor_open_trades(self) -> dict[str, Any]:
        """
        Monitora trades abertos, atualiza P&L e verifica TP/SL.
        
        Para cada trade OPEN:
        1. Obtém preço atual (real ou simulado)
        2. Calcula P&L
        3. Atualiza profit no Supabase
        4. Verifica se TP/SL foi atingido
        5. Se atingido, fecha trade e notifica
        
        Returns:
            Dict com resumo do monitoramento
        """
        try:
            # Busca trades abertos
            result = supabase_client.client.table("execution_log") \
                .select("*") \
                .eq("status", "OPEN") \
                .eq("type", "TRADE") \
                .execute()
            
            open_trades = result.data or []
            
            if not open_trades:
                return {"trades_monitored": 0, "message": "No open trades"}
            
            self.log(f"Monitoring {len(open_trades)} open trade(s)")
            
            trades_updated = 0
            trades_closed = 0
            
            for trade in open_trades:
                try:
                    symbol = trade.get("symbol", "EURUSD")
                    ticket = trade.get("ticket")
                    entry_price = float(trade.get("entry_price", 0))
                    stop_loss = float(trade.get("stop_loss", 0))
                    take_profit = float(trade.get("take_profit", 0))
                    direction = trade.get("direction", "LONG")
                    volume = float(trade.get("volume", 0.01))
                    mode = trade.get("mode", "SIMULATION")
                    
                    # Obtém preço atual
                    current_price = await self._get_current_price(symbol)
                    
                    # Calcula P&L
                    if direction == "LONG":
                        pnl = (current_price - entry_price) * volume * 100000
                    else:  # SHORT
                        pnl = (entry_price - current_price) * volume * 100000
                    
                    pnl = round(pnl, 2)
                    
                    # Verifica TP/SL
                    tp_hit = False
                    sl_hit = False
                    
                    if direction == "LONG":
                        if take_profit > 0 and current_price >= take_profit:
                            tp_hit = True
                        if stop_loss > 0 and current_price <= stop_loss:
                            sl_hit = True
                    else:  # SHORT
                        if take_profit > 0 and current_price <= take_profit:
                            tp_hit = True
                        if stop_loss > 0 and current_price >= stop_loss:
                            sl_hit = True
                    
                    if tp_hit:
                        # Recalcula P&L final com preço exato do TP
                        if direction == "LONG":
                            final_pnl = (take_profit - entry_price) * volume * 100000
                        else:
                            final_pnl = (entry_price - take_profit) * volume * 100000
                        
                        await self._close_trade_with_notification(
                            trade=trade,
                            reason="TAKE_PROFIT",
                            current_price=take_profit,
                            profit=round(final_pnl, 2)
                        )
                        trades_closed += 1
                        
                    elif sl_hit:
                        # Recalcula P&L final com preço exato do SL
                        if direction == "LONG":
                            final_pnl = (stop_loss - entry_price) * volume * 100000
                        else:
                            final_pnl = (entry_price - stop_loss) * volume * 100000
                        
                        await self._close_trade_with_notification(
                            trade=trade,
                            reason="STOP_LOSS",
                            current_price=stop_loss,
                            profit=round(final_pnl, 2)
                        )
                        trades_closed += 1
                        
                    else:
                        # Apenas atualiza profit no Supabase (apenas colunas existentes)
                        supabase_client.client.table("execution_log").update({
                            "profit": pnl,
                            "data": {
                                **trade.get("data", {}),
                                "current_price": current_price,
                                "last_update": datetime.now().isoformat()
                            }
                        }).eq("ticket", ticket).execute()
                        trades_updated += 1
                        
                        self.log(f"Trade #{ticket}: Price={current_price:.5f}, P&L=${pnl:.2f}")
                    
                except Exception as e:
                    self.log(f"Error monitoring trade {trade.get('ticket')}: {e}", level="error")
            
            return {
                "trades_monitored": len(open_trades),
                "trades_updated": trades_updated,
                "trades_closed": trades_closed
            }
            
        except Exception as e:
            self.log(f"Failed to monitor open trades: {e}", level="error")
            return {"error": str(e), "trades_monitored": 0}
    
    # ============== SAFETY ==============
    
    def _update_daily_pnl(self, profit: float) -> None:
        """Atualiza P&L diário."""
        # Reset se mudou o dia
        if date.today() != self._daily_pnl_date:
            self._daily_pnl = 0.0
            self._daily_pnl_date = date.today()
        
        self._daily_pnl += profit
    
    async def check_daily_loss_limit(self, max_loss_percent: float) -> bool:
        """
        Verifica se limite de perda diária foi atingido.
        
        Args:
            max_loss_percent: Limite máximo de perda (3.0 = 3%)
        
        Returns:
            True se limite foi atingido (deve pausar)
        """
        account = await self.get_account_info()
        
        if account.get("error"):
            return False
        
        balance = account.get("balance", 10000)
        loss_limit = balance * (max_loss_percent / 100)
        
        if self._daily_pnl < -loss_limit:
            self.log(f"DAILY LOSS LIMIT REACHED: {self._daily_pnl:.2f}", level="error")
            await self._log_error_to_supabase(
                "DAILY_LOSS_LIMIT",
                f"P&L: {self._daily_pnl:.2f}, Limit: -{loss_limit:.2f}"
            )
            return True
        
        return False
    
    # ============== LOGGING ==============
    
    async def _log_trade_to_supabase(self, trade_data: dict[str, Any]) -> None:
        """Loga trade no Supabase."""
        try:
            # Mapeia os dados para as colunas da tabela
            record = {
                "ticket": trade_data.get("ticket"),
                "symbol": trade_data.get("symbol"),
                "direction": trade_data.get("direction"),
                "volume": trade_data.get("volume", 0.01),
                "entry_price": trade_data.get("price"),
                "stop_loss": trade_data.get("stop_loss"),
                "take_profit": trade_data.get("take_profit"),
                "status": "OPEN",
                "profit": 0.0,
                "mode": trade_data.get("mode", "SIMULATION"),
                "type": "TRADE",
                "data": trade_data
            }
            
            supabase_client.client.table("execution_log").insert(record).execute()
        except Exception as e:
            self.log(f"Failed to log trade to Supabase: {e}", level="warning")
    
    async def _log_error_to_supabase(self, error_type: str, message: str) -> None:
        """Loga erro crítico no Supabase com prioridade alta."""
        try:
            supabase_client.client.table("execution_log").insert({
                "type": "ERROR",
                "priority": "HIGH",
                "error_type": error_type,
                "message": message,
                "mode": "SYSTEM",
                "status": "LOGGED"
            }).execute()
        except Exception as e:
            self.log(f"Failed to log error to Supabase: {e}", level="error")


# Singleton
execution_handler = ExecutionHandlerAgent()
