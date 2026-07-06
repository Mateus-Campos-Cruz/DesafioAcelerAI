---
name: executar-pipeline-educacao
description: Executa o pipeline ponta a ponta do Agente de Inteligência Global em Educação (Desafio Acelera AI) — coleta World Bank EdStats, processa com Python, gera análise executiva via Claude (local ou via n8n) e disponibiliza os artefatos para download.
---

Este projeto (Desafio Acelera AI — Agente de Inteligência Global em Educação) tem um pipeline automatizado ponta a ponta: World Bank EdStats → Python (pandas) → Claude (Anthropic API) → n8n → dashboard Streamlit.

Quando esta skill for invocada, execute o pipeline completo e reporte o resultado ao usuário:

1. Verifique o modo de execução em `.env`: se `WEBHOOK_URL` estiver configurada, a análise via Claude roda pelo n8n (a API key da Anthropic fica na credencial do próprio n8n, não em `.env`). Se `WEBHOOK_URL` não estiver configurada, o modo é 100% local e `ANTHROPIC_API_KEY` precisa estar em `.env` — se estiver ausente nesse caso, avise o usuário e pare.
2. Rode o orquestrador ponta a ponta:
   ```
   python run_all.py
   ```
   Isso executa, em sequência: coleta de dados (`fetch_worldbank.py`, com fallback World Bank API → dados sintéticos se os CSVs do Kaggle não estiverem em `data/`), processamento e enriquecimento (`pipeline.py`), análise executiva via Claude (`claude_agent.py`, usando tool use forçado da Anthropic API) e geração de `relatorio.md`/`relatorio.pdf`.
3. Se o usuário preferir disparar via n8n (fluxo com Webhook + AI Agent + Anthropic Chat Model, workflow `PplTjUrOU0h2E70s`), rode `streamlit run dashboard.py` e clique em "Executar Análise" — o dashboard roda a coleta/processamento localmente e envia os dados reais (`analise_data`) para o webhook do n8n, que por sua vez chama o Claude e retorna a análise estruturada.
4. Ao final, liste os artefatos gerados em `outputs/`: `analise_final.csv`, `comparativo_paises.csv`, `historico.csv`, `relatorio.json`, `relatorio.md`, `relatorio.pdf`. Se algum não foi gerado, explique o motivo (ex.: PDF não gerado por falta de `weasyprint`/`reportlab`).
5. Nunca invente dados que não estejam nos CSVs/outputs — se o pipeline falhar, reporte o erro real ao usuário em vez de simular um resultado.
