# Agente de Inteligência Global em Educação

**Desafio Acelera AI · World Bank EdStats · Stack: Claude + n8n + Streamlit**

Pipeline automatizado ponta a ponta que coleta indicadores educacionais do World Bank (EdStats), processa e enriquece com Python, gera análises executivas com Claude (Anthropic API), orquestra via n8n, e expõe tudo através de uma interface web com botão de acionamento, visualização e downloads.

---

## Arquitetura

```
[Interface Streamlit]
       │ POST /executar-analise
       ▼
[n8n Webhook Trigger]
       │ Execute Command
       ▼
[pipeline.py] → analise_final.csv
       │
       ▼
[claude_agent.py] → relatorio.json + relatorio.md + relatorio.pdf
       │ Respond to Webhook
       ▼
[Interface Streamlit] → tabelas + gráficos + relatório + downloads
```

## Agentes

| Agente | Responsabilidade | Tecnologia |
|--------|-----------------|------------|
| Data Engineer Agent | Ingestão, limpeza, filtro dos CSVs EdStats | Python (pandas/numpy) |
| Analytics Agent | Crescimento histórico, rankings, comparativos | Python (pandas/numpy) |
| Claude Intelligence Agent | Análise executiva + recomendações | Anthropic API (claude-sonnet-4-6, tool use) |
| Orchestration Agent | Coordena o fluxo ponta a ponta | n8n (Webhook + Execute Command + Respond) |
| Interface Agent | Dashboard interativo, acionamento, downloads | Streamlit |

---

## Pré-requisitos

- Python 3.11+
- Conta Anthropic com API key
- n8n (self-hosted ou cloud) — opcional para MVP local
- CSVs do Kaggle: [World Bank EdStats](https://www.kaggle.com/datasets/theworldbank/world-bank-edstats)

## Instalação

```bash
# 1. Clonar o repositório
git clone <repo-url>
cd "Desafio Acelerai Kaggle"

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env: preencher ANTHROPIC_API_KEY (e WEBHOOK_URL se usar n8n)

# 4. Colocar os CSVs do Kaggle na pasta data/
# data/EdStatsData.csv
# data/EdStatsCountry.csv
# data/EdStatsSeries.csv
```

## Execução

### Modo local (sem n8n)

```bash
# Rodar apenas o pipeline de dados
python pipeline.py

# Rodar apenas o agente Claude (requer pipeline já executado)
python claude_agent.py

# Rodar o dashboard Streamlit (inclui botão para executar tudo direto)
streamlit run dashboard.py
```

### Modo completo (com n8n)

1. Importe `n8n_workflow.json` no n8n
2. Configure `PROJECT_DIR` nas variáveis do n8n
3. Adicione credencial Anthropic no n8n
4. Ative o workflow e copie a URL do Webhook para o `.env` (`WEBHOOK_URL=`)
5. Execute `streamlit run dashboard.py`
6. Clique em **Executar Análise** na interface

## Outputs gerados

| Arquivo | Descrição |
|---------|-----------|
| `outputs/analise_final.csv` | Rankings e crescimento histórico por país/indicador |
| `outputs/comparativo_paises.csv` | Tabela comparativa entre países |
| `outputs/historico.csv` | Série histórica completa filtrada |
| `outputs/relatorio.json` | Análise executiva estruturada (JSON do Claude) |
| `outputs/relatorio.md` | Relatório executivo em Markdown |
| `outputs/relatorio.pdf` | Relatório executivo em PDF |

## Uso do Claude Code

Este projeto foi desenvolvido integralmente com apoio do **Claude Code**:

- Geração da estrutura de agentes e macroprocessos a partir do documento de requisitos
- Implementação do `pipeline.py` (Data Engineer + Analytics Agent)
- Implementação do `claude_agent.py` com tool use da Anthropic API
- Implementação do `dashboard.py` (interface Streamlit completa)
- Geração do `n8n_workflow.json` exportável
- Documentação e README

---

*Desafio Acelera AI — Prazo: 06/07/2026*
