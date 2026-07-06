# Agente de Inteligência Global em Educação

**Desafio Acelera AI · World Bank EdStats · Stack: Claude + n8n + Streamlit**

Pipeline automatizado ponta a ponta que coleta indicadores educacionais do World Bank (EdStats), processa e enriquece com Python, gera análises executivas com Claude (Anthropic API) via n8n, e expõe tudo através de uma interface web (Streamlit) com botão de acionamento, filtros, gráficos, alertas e downloads.

---

## Arquitetura

```
[Interface Streamlit]
   │ 1. roda fetch_worldbank.py + pipeline.py localmente (dados reais do World Bank)
   │ 2. POST /executar-analise (com analise_data já processado)
   ▼
[n8n — Webhook Trigger] ──┐
                          │
[n8n — Schedule Trigger] ─┤  (roda 1x/dia, busca dados reais direto da API do World Bank)
                          ▼
                 [Code: monta prompt]
                          │
                          ▼
     [AI Agent] ← [Anthropic Chat Model: Claude Sonnet 4.6]
          │      ← [Structured Output Parser: schema do relatório]
          ▼
  [Code: valida JSON] → [Data Table: histórico] → [Respond to Webhook]
                                                          │
                                                          ▼
                                        [Interface Streamlit] → tabelas,
                                        gráficos, alertas, relatório, downloads
```

## Agentes

| Agente | Responsabilidade | Tecnologia |
|--------|-----------------|------------|
| Data Engineer Agent | Ingestão, limpeza, filtro dos CSVs EdStats | Python (pandas/numpy) |
| Analytics Agent | Crescimento histórico, rankings, comparativos | Python (pandas/numpy) |
| Claude Intelligence Agent | Análise executiva + recomendações | Anthropic API (Claude Sonnet 4.6) via n8n AI Agent + Structured Output Parser |
| Orchestration Agent | Coordena o fluxo ponta a ponta — gatilho manual (Webhook) e periódico (Schedule) | n8n |
| Interface Agent | Dashboard interativo: acionamento, filtros, gráficos, alertas, downloads | Streamlit |

---

## Pré-requisitos

- Python 3.11+
- Conta Anthropic — a API key fica **apenas na credencial do n8n** (não é necessária localmente se for usar o modo n8n, que é o recomendado)
- Conta n8n (cloud ou self-hosted) com o workflow importado e publicado
- CSVs do Kaggle (opcional): [World Bank EdStats](https://www.kaggle.com/datasets/theworldbank/world-bank-edstats) — se ausentes, o sistema busca da API pública do World Bank ou gera dados sintéticos de demonstração como fallback

## Instalação

```bash
# 1. Clonar o repositório
git clone <repo-url>
cd "Desafio Acelerai Kaggle"

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env: preencher WEBHOOK_URL (modo n8n) e/ou ANTHROPIC_API_KEY (modo 100% local, sem n8n)

# 4. (Opcional) Colocar os CSVs do Kaggle na pasta data/
# data/EdStatsData.csv, data/EdStatsCountry.csv, data/EdStatsSeries.csv

# 5. Validar o ambiente antes de rodar
python check_setup.py
```

## Execução

### Modo completo (com n8n) — recomendado

1. Importe `n8n_workflow.json` no n8n (ou use o workflow já publicado)
2. Associe a credencial Anthropic API ao node **Anthropic Chat Model**
3. Ative o workflow e copie a URL do Webhook para `.env` (`WEBHOOK_URL=`)
4. Execute `streamlit run dashboard.py` e clique em **Executar Análise**
   - O dashboard roda a coleta + `pipeline.py` localmente (dados reais do World Bank) e envia o resultado real ao n8n via `analise_data`
5. O workflow também roda sozinho 1x por dia (Schedule Trigger), buscando dados reais direto da API do World Bank — sem depender do dashboard

### Modo local (sem n8n)

```bash
python pipeline.py          # roda só o pipeline de dados
python claude_agent.py      # roda só o agente Claude (requer ANTHROPIC_API_KEY e pipeline já executado)
streamlit run dashboard.py  # dashboard completo com botão "Executar Análise"
```

### Testes

```bash
python -m pytest tests/ -v
```

## Outputs gerados

| Arquivo | Descrição |
|---------|-----------|
| `outputs/analise_final.csv` | Rankings e crescimento histórico por país/indicador |
| `outputs/comparativo_paises.csv` | Tabela comparativa entre países |
| `outputs/historico.csv` | Série histórica completa filtrada |
| `outputs/relatorio.json` | Análise executiva estruturada (JSON do Claude) |
| `outputs/relatorio.md` | Relatório executivo em Markdown |
| `outputs/relatorio.pdf` | Relatório executivo em PDF |

## Diferenciais implementados (bônus)

- ✅ Dashboard interativo (Streamlit)
- ✅ Exportação para PDF
- ✅ Gráficos automáticos (barras de crescimento, série histórica, heatmap de CAGR)
- ✅ Agendamento periódico no n8n (Schedule Trigger diário, com coleta real da API pública do World Bank)
- ✅ Alertas quando um indicador ultrapassa um limite configurado (aba "⚠️ Alertas")

## Como o Codex (ou Claude Code) foi utilizado

Este projeto foi desenvolvido integralmente com apoio do **Claude Code**, incluindo uma sessão dedicada de auditoria e correção do código já escrito, frente aos requisitos do desafio. Tarefas realizadas:

- **Criar funções Python**: `pipeline.py` (ingestão, limpeza, cálculo de crescimento/CAGR, rankings, comparativos), `fetch_worldbank.py`, `claude_agent.py` e `dashboard.py`.
- **Escrever testes**: suíte `tests/test_pipeline.py` (pytest) cobrindo `calculate_growth`, `generate_rankings`, `generate_comparatives` e `filter_and_melt`.
- **Gerar documentação**: este README, docstrings dos módulos e a Skill em `.claude/skills/executar-pipeline-educacao/`.
- **Criar docstrings**: revisão e complementação da cobertura de docstrings em `dashboard.py`, `pipeline.py`, `claude_agent.py`, `run_all.py` e `fetch_worldbank.py`.
- **Melhorar performance**: troca de `iterrows()` por `rename()` + `to_dict("records")` vetorizado em `dashboard.py` (`_build_analise_data`).
- **Identificar bugs**: durante a auditoria, foi encontrado que o fluxo via n8n sempre usava dados **sintéticos** em vez dos dados reais do World Bank (o dashboard nunca enviava `analise_data`), e que a seleção de países/indicadores na sidebar não afetava as tabelas/gráficos exibidos — ambos corrigidos e validados com testes automatizados (`streamlit.testing.v1.AppTest`). Já com a conta Anthropic com crédito ativo, uma nova execução real revelou outro bug: o node **Anthropic Chat Model** no n8n (e o `claude_agent.py` no modo local) usava `max_tokens=4096`, insuficiente para o schema completo — o Claude ficava sem tokens antes de terminar a saída estruturada, retornando um objeto vazio. Corrigido para `max_tokens=8192` (sem custo adicional, já que a cobrança é pelos tokens realmente gerados) e validado com **duas execuções reais consecutivas bem-sucedidas** (com seleções de países diferentes em cada uma), ambas gerando análises executivas coerentes, específicas e não genéricas.
- **Refatorar código**: unificação da geração de `relatorio.md`/`relatorio.pdf` entre o modo local e o modo n8n (reaproveitando `claude_agent.build_markdown`/`generate_pdf` em vez de duplicar a lógica em `dashboard.py`); `n8n_workflow.json` resincronizado com o workflow real publicado, que antes estava desatualizado; simplificação da interface removendo a sidebar (informações técnicas de modo/API key) em favor de uma seção de Filtros na própria tela, com países exibidos por nome e um filtro de período.
- **Criar scripts auxiliares**: `check_setup.py`, que valida dependências, `.env` e dados de entrada antes de rodar o pipeline ou o dashboard.

---

*Desafio Acelera AI — Prazo: 06/07/2026*
