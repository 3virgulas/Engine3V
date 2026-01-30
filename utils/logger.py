"""
3V Engine - Structured Logger
==============================
Sistema de logging estruturado usando structlog.
Logs são salvos em arquivo e exibidos no console.
"""

import logging
import sys
from pathlib import Path

import structlog
from rich.console import Console
from rich.logging import RichHandler

from core.config import settings


def setup_logger() -> structlog.BoundLogger:
    """
    Configura e retorna o logger estruturado do sistema.
    
    Returns:
        Logger configurado com output para console e arquivo
    """
    # Diretório de logs
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "3v_engine.log"
    
    # Configuração do logging padrão
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RichHandler(
                console=Console(stderr=True),
                show_time=True,
                show_path=False,
                rich_tracebacks=True
            ),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )
    
    # Configuração do structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )
    
    return structlog.get_logger("3v_engine")


# Logger singleton
logger = setup_logger()


def log_agent_action(
    agent_name: str,
    action: str,
    data: dict | None = None,
    level: str = "info"
) -> None:
    """
    Log especializado para ações dos agentes.
    
    Args:
        agent_name: Nome do agente (ex: @Quant_Analyst)
        action: Ação sendo executada
        data: Dados adicionais (opcional)
        level: Nível do log (debug, info, warning, error)
    """
    log_func = getattr(logger, level, logger.info)
    log_func(
        f"{agent_name} - {action}",
        agent=agent_name,
        action=action,
        **(data or {})
    )


def log_trade_signal(
    signal: str,
    confidence: float,
    reasoning: str
) -> None:
    """
    Log especializado para sinais de trade.
    
    Args:
        signal: Tipo do sinal (ENTRY, HOLD, EXIT)
        confidence: Confiança do sinal (0-100)
        reasoning: Justificativa
    """
    emoji = {
        "ENTRY": "🟢",
        "EXIT": "🔴",
        "HOLD": "🟡"
    }.get(signal, "⚪")
    
    logger.info(
        f"{emoji} TRADE SIGNAL: {signal}",
        signal=signal,
        confidence=confidence,
        reasoning=reasoning
    )
