"""
3V Engine - Telegram Bot Notifier
==================================
Cliente assíncrono para envio de alertas via Telegram.
Notifica apenas sinais de alta probabilidade (BUY/SELL).
"""

from datetime import datetime
from typing import Any, Literal

import httpx

from core.config import settings
from utils.logger import log_agent_action


class TelegramBot:
    """
    Bot para envio de notificações de trade signals via Telegram.
    
    Características:
    - Envia apenas sinais de ENTRY (BUY/SELL)
    - Ignora HOLD rotineiros para evitar spam
    - Formatação rica com emojis para leitura rápida
    """
    
    BASE_URL = "https://api.telegram.org/bot"
    
    # Emojis para cada tipo de sinal
    SIGNAL_EMOJIS = {
        "BUY": "🚀",
        "SELL": "📉",
        "HOLD": "⏸️",
        "VETO": "🛡️"
    }
    
    # Emojis para confiança
    CONFIDENCE_EMOJIS = {
        "high": "🔥",
        "medium": "⚡",
        "low": "⚠️"
    }
    
    def __init__(self) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._enabled = bool(self._token and self._chat_id)
    
    @property
    def is_enabled(self) -> bool:
        """Verifica se o bot está configurado."""
        return self._enabled
    
    async def _send_message(
        self,
        text: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """
        Envia mensagem via API do Telegram.
        
        Args:
            text: Texto da mensagem (suporta HTML)
            parse_mode: Modo de parsing (HTML ou Markdown)
        
        Returns:
            True se enviado com sucesso
        """
        if not self._enabled:
            log_agent_action(
                "@TelegramBot",
                "Bot not configured, skipping notification",
                level="warning"
            )
            return False
        
        url = f"{self.BASE_URL}{self._token}/sendMessage"
        
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                log_agent_action(
                    "@TelegramBot",
                    "Message sent successfully"
                )
                return True
                
        except httpx.HTTPStatusError as e:
            log_agent_action(
                "@TelegramBot",
                f"HTTP error: {e.response.status_code}",
                level="error"
            )
            return False
        except Exception as e:
            log_agent_action(
                "@TelegramBot",
                f"Failed to send: {e}",
                level="error"
            )
            return False
    
    def _get_confidence_emoji(self, confidence: int) -> str:
        """Retorna emoji baseado no nível de confiança."""
        if confidence >= 80:
            return self.CONFIDENCE_EMOJIS["high"]
        elif confidence >= 60:
            return self.CONFIDENCE_EMOJIS["medium"]
        return self.CONFIDENCE_EMOJIS["low"]
    
    def _format_trade_signal(
        self,
        decision: str,
        direction: str | None,
        confidence: int,
        reasoning: str,
        pair: str,
        inputs: dict[str, Any] | None = None,
        market_bias: str | None = None,
        scheduled_entry: dict[str, Any] | None = None,
        exit_levels: dict[str, Any] | None = None
    ) -> str:
        """
        Formata mensagem de sinal de trade com Professional Execution Strategy.
        
        Args:
            decision: BUY, SELL, HOLD, VETO
            direction: LONG, SHORT, None
            confidence: Score de confiança (0-100)
            reasoning: Justificativa do sinal
            pair: Par de moedas
            inputs: Dados dos indicadores
            market_bias: Viés do mercado (Alta/Baixa/Lateralizado)
            scheduled_entry: Janela de entrada recomendada
            exit_levels: Níveis de TP/SL
        
        Returns:
            Mensagem formatada em HTML
        """
        signal_emoji = self.SIGNAL_EMOJIS.get(decision, "❓")
        conf_emoji = self._get_confidence_emoji(confidence)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Header baseado no tipo de decisão
        if decision == "BUY":
            header = f"🔔 <b>3V ENGINE - SINAL DE ENTRADA</b>"
            direction_text = f"📊 {pair} • <b>BUY (Long)</b>"
        elif decision == "SELL":
            header = f"🔔 <b>3V ENGINE - SINAL DE ENTRADA</b>"
            direction_text = f"📊 {pair} • <b>SELL (Short)</b>"
        elif decision == "VETO":
            header = f"🛑 <b>3V ENGINE - VETO MACRO</b>"
            direction_text = f"📊 {pair} • <b>Operações Suspensas</b>"
        else:  # HOLD
            header = f"⏸️ <b>3V ENGINE - AGUARDAR</b>"
            direction_text = f"📊 {pair} • <b>HOLD</b>"
        
        # Extrai dados dos inputs
        tech_signal = "N/A"
        macro_alert = "N/A"
        
        if inputs:
            tech = inputs.get("technical", {})
            tech_signal = tech.get("signal", "N/A")
            
            macro = inputs.get("macro", {})
            macro_alert = macro.get("alert", "N/A")
        
        # Formata viés do mercado
        bias_text = f"🧭 <b>Viés do Mercado:</b> {market_bias or 'N/A'}"
        
        # Formata janela de entrada
        if scheduled_entry and decision in ["BUY", "SELL"]:
            entry_window = f"⏱️ <b>Janela de Entrada:</b> {scheduled_entry.get('start', 'N/A')} até {scheduled_entry.get('end', 'N/A')}"
            entry_instruction = f"📌 <i>{scheduled_entry.get('instruction', '')}</i>"
        else:
            entry_window = "⏱️ <b>Janela de Entrada:</b> Não aplicável"
            entry_instruction = ""
        
        # Formata níveis de saída
        if exit_levels and exit_levels.get("take_profit"):
            tp = exit_levels.get("take_profit", "N/A")
            sl = exit_levels.get("stop_loss", "N/A")
            exit_cond = exit_levels.get("exit_condition", "N/A")
            rr = exit_levels.get("risk_reward_ratio", 0)
            
            exit_section = f"""🎯 <b>Alvo Técnico (TP):</b> {tp}
🛡️ <b>Proteção (SL):</b> {sl}
⚖️ <b>Risk/Reward:</b> {rr}:1
⚠️ <b>Saída:</b> {exit_cond}"""
        else:
            exit_section = "📊 <b>Níveis:</b> Não calculados"
        
        # Monta mensagem
        message = f"""
{header}
━━━━━━━━━━━━━━━━━

{direction_text}
{bias_text}
{entry_window}
{entry_instruction}

{exit_section}

{conf_emoji} <b>Confiança:</b> {confidence}%

📝 <b>Motivo:</b>
<i>{reasoning[:300]}{'...' if len(reasoning) > 300 else ''}</i>

🕐 {timestamp} (GMT-3)
━━━━━━━━━━━━━━━━━
<code>3V Engine • Veredito de Ouro</code>
"""
        return message.strip()
    
    async def notify_trade_signal(
        self,
        decision: str,
        direction: str | None = None,
        confidence: int = 0,
        reasoning: str = "",
        pair: str = "EUR/USD",
        inputs: dict[str, Any] | None = None,
        market_bias: str | None = None,
        scheduled_entry: dict[str, Any] | None = None,
        exit_levels: dict[str, Any] | None = None
    ) -> bool:
        """
        Envia notificação de sinal de trade com Professional Execution Strategy.
        
        IMPORTANTE: Só envia para BUY, SELL, VETO, ou HOLD com confiança >= 70%.
        
        Args:
            decision: Decisão do Risk Commander
            direction: Direção do trade
            confidence: Score de confiança
            reasoning: Justificativa
            pair: Par de moedas
            inputs: Dados dos indicadores
            market_bias: Viés do mercado (Alta/Baixa/Lateralizado)
            scheduled_entry: Janela de entrada recomendada
            exit_levels: Níveis de TP/SL
        
        Returns:
            True se enviado com sucesso
        """
        # Filtro: notifica BUY, SELL, VETO, ou HOLD com confiança >= 70%
        should_notify = (
            decision in ["BUY", "SELL", "VETO"] or
            (decision == "HOLD" and confidence >= 70)
        )
        
        if not should_notify:
            log_agent_action(
                "@TelegramBot",
                f"Skipping {decision} (confidence {confidence}%) notification",
                level="debug"
            )
            return False
        
        message = self._format_trade_signal(
            decision=decision,
            direction=direction,
            confidence=confidence,
            reasoning=reasoning,
            pair=pair,
            inputs=inputs,
            market_bias=market_bias,
            scheduled_entry=scheduled_entry,
            exit_levels=exit_levels
        )
        
        return await self._send_message(message)
    
    async def notify_entry_confirmation(
        self,
        decision: str,
        direction: str,
        pair: str,
        entry_price: float,
        take_profit: float,
        stop_loss: float,
        confidence: int,
        reasoning: str
    ) -> bool:
        """
        Envia notificação de CONFIRMAÇÃO DE ENTRADA no horário agendado.
        
        Esta é a segunda notificação que vem no horário de execução,
        com os níveis de preço atuais.
        
        Args:
            decision: BUY ou SELL
            direction: LONG ou SHORT
            pair: Par de moedas (ex: EUR/USD)
            entry_price: Preço atual de entrada
            take_profit: Nível de Take Profit
            stop_loss: Nível de Stop Loss
            confidence: Score de confiança
            reasoning: Justificativa da entrada
        
        Returns:
            True se enviado com sucesso
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Determina emojis e texto baseado na direção
        if decision == "BUY":
            header = "🚀 <b>3V ENGINE - EXECUTAR COMPRA</b>"
            direction_emoji = "📈"
            direction_text = "BUY (Long)"
        else:
            header = "🔻 <b>3V ENGINE - EXECUTAR VENDA</b>"
            direction_emoji = "📉"
            direction_text = "SELL (Short)"
        
        # Calcula RR e pips
        pip_value = 0.0001 if "JPY" not in pair else 0.01
        
        if decision == "BUY":
            tp_pips = round((take_profit - entry_price) / pip_value, 1)
            sl_pips = round((entry_price - stop_loss) / pip_value, 1)
        else:
            tp_pips = round((entry_price - take_profit) / pip_value, 1)
            sl_pips = round((stop_loss - entry_price) / pip_value, 1)
        
        rr_ratio = round(tp_pips / sl_pips, 2) if sl_pips > 0 else 0
        conf_emoji = self._get_confidence_emoji(confidence)
        
        message = f"""
{header}
━━━━━━━━━━━━━━━━━

{direction_emoji} <b>{pair}</b> • <b>{direction_text}</b>

💰 <b>NÍVEIS DE EXECUÇÃO:</b>

🎯 <b>Entry Price:</b> <code>{entry_price:.5f}</code>
✅ <b>Take Profit:</b> <code>{take_profit:.5f}</code> (+{tp_pips} pips)
❌ <b>Stop Loss:</b> <code>{stop_loss:.5f}</code> (-{sl_pips} pips)

⚖️ <b>Risk/Reward:</b> 1:{rr_ratio}
{conf_emoji} <b>Confiança:</b> {confidence}%

📝 <b>Tese:</b>
<i>{reasoning[:200]}{'...' if len(reasoning) > 200 else ''}</i>

⚡️ <b>AÇÃO:</b> Executar ordem {direction_text} AGORA

🕐 {timestamp} (GMT-3)
━━━━━━━━━━━━━━━━━
<code>3V Engine • Hora de Executar!</code>
"""
        
        log_agent_action(
            "@TelegramBot",
            f"Sending ENTRY CONFIRMATION for {decision}",
            {"pair": pair, "entry_price": entry_price, "tp": take_profit, "sl": stop_loss}
        )
        
        return await self._send_message(message.strip())
    
    async def test_connection(self) -> bool:
        """Testa conexão com a API do Telegram."""
        if not self._enabled:
            print("⚠️ Telegram Bot not configured (missing token or chat_id)")
            return True  # Não falha o teste se não configurado
        
        try:
            url = f"{self.BASE_URL}{self._token}/getMe"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if data.get("ok"):
                    bot_name = data.get("result", {}).get("username", "Unknown")
                    print(f"✅ Telegram Bot OK - Connected as @{bot_name}")
                    return True
                else:
                    print(f"❌ Telegram Bot FAILED: {data}")
                    return False
                    
        except Exception as e:
            print(f"❌ Telegram Bot FAILED: {e}")
            return False


# Singleton
telegram_bot = TelegramBot()
