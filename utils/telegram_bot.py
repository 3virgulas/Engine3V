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
        inputs: dict[str, Any] | None = None
    ) -> str:
        """
        Formata mensagem de sinal de trade.
        
        Args:
            decision: BUY, SELL, HOLD, VETO
            direction: LONG, SHORT, None
            confidence: Score de confiança (0-100)
            reasoning: Justificativa do sinal
            pair: Par de moedas
            inputs: Dados dos indicadores
        
        Returns:
            Mensagem formatada em HTML
        """
        signal_emoji = self.SIGNAL_EMOJIS.get(decision, "❓")
        conf_emoji = self._get_confidence_emoji(confidence)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Header baseado no tipo de decisão
        if decision == "BUY":
            header = f"{signal_emoji} <b>SINAL DE COMPRA</b> {signal_emoji}"
            direction_text = "📈 Direção: LONG"
        elif decision == "SELL":
            header = f"{signal_emoji} <b>SINAL DE VENDA</b> {signal_emoji}"
            direction_text = "📉 Direção: SHORT"
        elif decision == "VETO":
            header = f"{signal_emoji} <b>VETO MACRO</b> {signal_emoji}"
            direction_text = "⛔ Operações suspensas"
        else:
            header = f"{signal_emoji} <b>HOLD</b> {signal_emoji}"
            direction_text = "⏸️ Aguardando"
        
        # Extrai dados dos inputs
        tech_signal = "N/A"
        sentiment = "N/A"
        macro_alert = "N/A"
        
        if inputs:
            tech = inputs.get("technical", {})
            tech_signal = tech.get("signal", "N/A")
            
            sent = inputs.get("sentiment", {})
            sentiment_score = sent.get("score", 0)
            sentiment = f"{sentiment_score:+.2f}"
            
            macro = inputs.get("macro", {})
            macro_alert = macro.get("alert", "N/A")
        
        # Monta mensagem
        message = f"""
{header}

💱 <b>Par:</b> {pair}
{direction_text}
{conf_emoji} <b>Confiança:</b> {confidence}%

📊 <b>Indicadores:</b>
• Técnico: {tech_signal}
• Sentimento: {sentiment}
• Macro: {macro_alert}

📝 <b>Motivo:</b>
<i>{reasoning}</i>

🕐 {timestamp}
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
        inputs: dict[str, Any] | None = None
    ) -> bool:
        """
        Envia notificação de sinal de trade.
        
        IMPORTANTE: Só envia para BUY, SELL e VETO.
        Ignora HOLD para evitar spam.
        
        Args:
            decision: Decisão do Risk Commander
            direction: Direção do trade
            confidence: Score de confiança
            reasoning: Justificativa
            pair: Par de moedas
            inputs: Dados dos indicadores
        
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
            inputs=inputs
        )
        
        return await self._send_message(message)
    
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
