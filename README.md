# 3V Engine - Forex Multi-Agent System

Sistema multi-agentes em Python para análise e sinalização de operações no mercado Forex.

## 🚀 Quick Start

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Copiar e configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves de API

# 3. Testar conexões
python main.py --test

# 4. Executar uma análise
python main.py --once

# 5. Iniciar monitoramento contínuo
python main.py
```

## 📁 Estrutura do Projeto

```
├── agents/           # Agentes especializados
│   ├── base.py           # Classe base abstrata
│   ├── quant_analyst.py  # @Quant_Analyst - Análise técnica
│   ├── sentiment_pulse.py # @Sentiment_Pulse - Sentimento
│   ├── macro_watcher.py  # @Macro_Watcher - Calendário
│   └── risk_commander.py # @Risk_Commander - Decisões
├── core/             # Infraestrutura
│   ├── config.py         # Configurações
│   ├── supabase_client.py # Database
│   ├── llm_client.py     # OpenRouter/Claude
│   └── orchestrator.py   # LangGraph
├── utils/            # Integrações
│   ├── twelve_data.py    # Twelve Data API
│   ├── finnhub.py        # Finnhub API
│   ├── fmp_calendar.py   # FMP Calendar API
│   └── logger.py         # Logging estruturado
├── tests/            # Testes
├── logs/             # Logs locais
└── main.py           # Entry point
```

## 🔑 APIs Necessárias

| Serviço | Uso | Link |
|---------|-----|------|
| Twelve Data | Dados técnicos | https://twelvedata.com |
| Finnhub | Sentimento | https://finnhub.io |
| FMP | Calendário | https://financialmodelingprep.com |
| OpenRouter | LLM | https://openrouter.ai |
| Supabase | Database | https://supabase.com |

## 📊 Agentes

- **@Quant_Analyst**: Análise técnica (MA, RSI, Bollinger, Candlesticks)
- **@Sentiment_Pulse**: Score de sentimento das notícias (-1 a +1)
- **@Macro_Watcher**: Alertas de eventos de alto impacto
- **@Risk_Commander**: Decisão final (ENTRY/HOLD/VETO)

## ⚙️ Configuração

Edite o arquivo `.env` com suas chaves:

```env
TWELVE_DATA_API_KEY=sua_chave
FINNHUB_API_KEY=sua_chave
FMP_API_KEY=sua_chave
OPENROUTER_API_KEY=sua_chave
SUPABASE_URL=sua_url
SUPABASE_SERVICE_KEY=sua_chave
TRADING_PAIR=EUR/USD
ANALYSIS_INTERVAL_MINUTES=5
```

---

Desenvolvido por **3Vírgulas** 🚀
