"""
Interface Agent — Streamlit Dashboard
Macroprocesso 5: Interface de Controle e Visualização
Executa o pipeline completo em background thread, com progresso em tempo real.
"""
import json
import os
import threading
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

from fetch_worldbank import COUNTRY_NAMES
from pipeline import INDICATORS_PRIORITY

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
STATUS_FILE = OUTPUT_DIR / "pipeline_status.json"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

st.set_page_config(
    page_title="Educação Global — Acelera AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .main-title { font-size: 2.2rem; font-weight: 700; color: #1a4a7a; margin-bottom: 0; }
  .subtitle { color: #666; font-size: 0.95rem; margin-bottom: 1rem; }
  .stage-chip {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.82rem; font-weight: 600; margin: 2px;
  }
  .chip-done { background:#d4edda; color:#155724; }
  .chip-active { background:#fff3cd; color:#856404; }
  .chip-pending { background:#e2e3e5; color:#383d41; }
  .chip-error { background:#f8d7da; color:#721c24; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers de estado e status ──────────────────────────────────────────────

def read_status() -> dict:
    """Lê o status atual do pipeline (arquivo pipeline_status.json)."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"stage": "idle", "stage_label": "Aguardando", "progress_pct": 0, "error": None, "outputs": {}}


def load_artifact(name: str):
    """Lê um artefato do diretório de outputs."""
    path = OUTPUT_DIR / name
    if not path.exists():
        return None
    if name.endswith(".csv"):
        return pd.read_csv(path, encoding="utf-8-sig")
    if name.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    if name.endswith(".md"):
        return path.read_text(encoding="utf-8")
    return path.read_bytes()


# ─── Execução em background thread ───────────────────────────────────────────

def _pipeline_thread(api_key: str, params: dict):
    """Roda o pipeline completo em thread separada."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from run_all import run_full_pipeline
        run_full_pipeline(api_key=api_key)
    except Exception as exc:
        import traceback
        from run_all import write_status
        write_status("error", f"Erro: {exc}", 0, error=traceback.format_exc())


def _build_analise_data(params: dict) -> list:
    """Lê o analise_final.csv (gerado pelo pipeline.py local) e monta os registros
    no formato esperado pelo nó 'Preparar Dados e Prompt' do n8n, filtrando pelos
    países/indicadores selecionados na sidebar (se houver seleção)."""
    csv_path = OUTPUT_DIR / "analise_final.csv"
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    countries = params.get("countries") or []
    indicators = params.get("indicators") or []
    if countries:
        df = df[df["Country Code"].isin(countries)]
    if indicators:
        df = df[df["Indicator Code"].isin(indicators)]
    column_map = {
        "Country Code": "country_code",
        "Country Name": "country_name",
        "Indicator Code": "indicator_code",
        "Indicador Label": "indicator_label",
        "Valor Inicio": "val_start",
        "Valor Fim": "val_end",
        "Crescimento %": "growth_pct",
        "CAGR %": "cagr",
    }
    cols = [c for c in column_map if c in df.columns]
    return df[cols].rename(columns=column_map).to_dict("records")


# Limites de alerta por indicador (diferencial de bônus): sinaliza países cujo
# valor mais recente ficou abaixo do patamar considerado adequado.
INDICATOR_THRESHOLDS = {
    "SE.XPD.TOTL.GD.ZS": {"limite": 4.0, "rotulo": "Gasto público em educação abaixo de 4% do PIB"},
    "SE.PRM.ENRR": {"limite": 90.0, "rotulo": "Matrícula primária bruta abaixo de 90%"},
    "SE.SEC.ENRR": {"limite": 60.0, "rotulo": "Matrícula secundária bruta abaixo de 60%"},
    "SE.TER.ENRR": {"limite": 20.0, "rotulo": "Matrícula terciária bruta abaixo de 20%"},
    "SE.PRM.CMPT.ZS": {"limite": 80.0, "rotulo": "Conclusão do ensino primário abaixo de 80%"},
    "SE.ADT.LITR.ZS": {"limite": 80.0, "rotulo": "Alfabetização de adultos abaixo de 80%"},
}


def compute_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Sinaliza combinações país/indicador cujo valor mais recente ('Valor Fim')
    ficou abaixo do limite configurado em INDICATOR_THRESHOLDS."""
    if df is None or df.empty:
        return pd.DataFrame()
    flagged = []
    for indicator_code, cfg in INDICATOR_THRESHOLDS.items():
        subset = df[(df["Indicator Code"] == indicator_code) & (df["Valor Fim"] < cfg["limite"])]
        if subset.empty:
            continue
        flagged.append(subset.assign(Limite=cfg["limite"], Alerta=cfg["rotulo"])[
            ["Country Name", "Country Code", "Indicador Label", "Valor Fim", "Limite", "Alerta"]
        ])
    if not flagged:
        return pd.DataFrame()
    return pd.concat(flagged, ignore_index=True).rename(columns={"Valor Fim": "Valor Atual"})


# Rótulos legíveis para colunas técnicas exibidas nas tabelas do dashboard.
COLUMN_LABELS = {
    "Country Code": "Código",
    "Country Name": "País",
    "Indicador Label": "Indicador",
    "Valor Inicio": "Valor Inicial",
    "Valor Fim": "Valor Atual",
    "Crescimento %": "Crescimento (%)",
    "CAGR %": "CAGR (%)",
    "Rank Valor Atual": "Rank (Valor)",
    "Rank Crescimento %": "Rank (Crescimento)",
    "Media_CAGR": "CAGR Médio (%)",
    "Soma_Crescimento_Pct": "Soma do Crescimento (%)",
    "N_Indicadores": "Nº de Indicadores",
    **INDICATORS_PRIORITY,
}


def friendly_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas técnicas (códigos de indicador, nomes internos) para rótulos legíveis."""
    return df.rename(columns=COLUMN_LABELS)


def _webhook_thread(params: dict):
    """Roda a coleta + pipeline de dados localmente (World Bank real) e então
    dispara o webhook n8n com os dados já processados, para a análise via Claude."""
    from run_all import write_status, stage_coleta, stage_pipeline
    from claude_agent import build_markdown, generate_pdf
    try:
        write_status("fetching", "Etapa 1/3 — Coleta de dados do World Bank...", 5)
        stage_coleta()

        write_status("processing", "Etapa 2/3 — Processando dados com Python...", 25)
        stage_pipeline()

        write_status("analyzing", "Etapa 3/3 — Enviando dados reais para Claude via n8n...", 55)
        analise_data = _build_analise_data(params)
        payload = {**params, "analise_data": analise_data}

        resp = requests.post(WEBHOOK_URL, json=payload, timeout=300,
                             headers={"Content-Type": "application/json"})
        # Capturar texto bruto antes de tentar parsear
        raw_text = resp.text
        if resp.status_code != 200:
            write_status("error", f"n8n retornou HTTP {resp.status_code}", 0,
                         error=f"Status: {resp.status_code}\nBody: {raw_text[:800]}")
            return

        try:
            result = resp.json()
        except Exception as json_err:
            if not raw_text.strip():
                write_status(
                    "error",
                    "n8n não retornou resposta — a execução provavelmente falhou antes do fim "
                    "(ex.: erro na chamada ao Claude por falta de crédito na conta Anthropic).",
                    0,
                    error="Resposta vazia (0 chars). Verifique o histórico de execuções do "
                          "workflow no n8n para ver o erro real (node que falhou).",
                )
            else:
                write_status("error", f"Resposta n8n não é JSON: {json_err}", 0,
                             error=f"Resposta recebida ({len(raw_text)} chars):\n{raw_text[:800]}")
            return

        write_status("reporting", "Processando resposta do Claude...", 85)
        analysis = result.get("analysis")
        if result.get("status") == "success" and analysis:
            # Salvar JSON do Claude
            (OUTPUT_DIR / "relatorio.json").write_text(
                json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Reaproveita o mesmo formatador de MD/PDF usado no modo local (claude_agent.py)
            md_path = OUTPUT_DIR / "relatorio.md"
            md_path.write_text(build_markdown(analysis), encoding="utf-8")
            generate_pdf(md_path, OUTPUT_DIR / "relatorio.pdf")

            outputs = {
                "analise_final.csv": str(OUTPUT_DIR / "analise_final.csv"),
                "comparativo_paises.csv": str(OUTPUT_DIR / "comparativo_paises.csv"),
                "historico.csv": str(OUTPUT_DIR / "historico.csv"),
                "relatorio.json": str(OUTPUT_DIR / "relatorio.json"),
                "relatorio.md": str(md_path),
                "relatorio.pdf": str(OUTPUT_DIR / "relatorio.pdf"),
            }
            write_status("done", "Análise via n8n concluída com sucesso.", 100, outputs=outputs)
        else:
            err = result.get("error", "Resposta inesperada do n8n")
            write_status("error", f"Erro Claude: {err}", 0, error=err)

    except Exception as exc:
        import traceback
        write_status("error", f"Erro no pipeline/webhook: {exc}", 0, error=traceback.format_exc())


def start_execution(params: dict):
    """Inicia a execução em background e retorna imediatamente."""
    # Escrever status inicial imediatamente para o UI reagir
    STATUS_FILE.write_text(json.dumps(
        {"stage": "starting", "stage_label": "Iniciando...", "progress_pct": 1,
         "updated_at": "", "error": None, "outputs": {}},
        ensure_ascii=False
    ), encoding="utf-8")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if WEBHOOK_URL:
        t = threading.Thread(target=_webhook_thread, args=(params,), daemon=True)
    else:
        t = threading.Thread(target=_pipeline_thread, args=(api_key, params), daemon=True)
    t.start()


# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">🎓 Inteligência Educacional Global</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Desafio Acelera AI · World Bank EdStats · Claude + n8n + Streamlit</div>',
            unsafe_allow_html=True)
st.caption("Fonte dos dados: World Bank EdStats")
st.divider()


# ─── Filtros ─────────────────────────────────────────────────────────────────

st.subheader("🔎 Filtros")
col_f1, col_f2 = st.columns(2)
with col_f1:
    all_countries = list(COUNTRY_NAMES.keys())
    selected_countries = st.multiselect(
        "Países", all_countries,
        default=["BRA", "USA", "CHN", "IND", "DEU", "KOR", "ZAF"],
        format_func=lambda x: COUNTRY_NAMES.get(x, x),
    )
with col_f2:
    indicators_map = {
        "SE.XPD.TOTL.GD.ZS": "Gasto em educação (% PIB)",
        "SE.PRM.ENRR": "Matrícula primária",
        "SE.SEC.ENRR": "Matrícula secundária",
        "SE.TER.ENRR": "Matrícula terciária",
        "SE.PRM.CMPT.ZS": "Conclusão primária",
        "SE.ADT.LITR.ZS": "Alfabetização adultos",
    }
    selected_indicators = st.multiselect("Indicadores", list(indicators_map.keys()),
                                          default=list(indicators_map.keys())[:4],
                                          format_func=lambda x: indicators_map[x])
st.divider()


# ─── Painel de controle + progresso ──────────────────────────────────────────

status = read_status()
is_running = status["stage"] not in ("idle", "done", "error")
is_done = status["stage"] == "done"

col_btn, col_progress = st.columns([2, 5])

with col_btn:
    if st.button(
        "⏳ Executando..." if is_running else "🚀 Executar Análise",
        type="primary",
        disabled=is_running,
        use_container_width=True,
    ):
        start_execution({"countries": selected_countries, "indicators": selected_indicators})
        st.rerun()

    if is_done and st.button("🔄 Nova Análise", use_container_width=True):
        STATUS_FILE.unlink(missing_ok=True)
        st.rerun()

with col_progress:
    pct = status.get("progress_pct", 0)
    label = status.get("stage_label", "")
    stage = status.get("stage", "idle")

    STAGES = [
        ("fetching",    "1. Coleta"),
        ("processing",  "2. Tratamento"),
        ("analyzing",   "3. IA Claude"),
        ("reporting",   "4. Relatório"),
        ("done",        "Concluído"),
    ]

    # Chips de estágio
    chips_html = ""
    active_stages = [s[0] for s in STAGES]
    reached = False
    for s_key, s_label in STAGES:
        if stage == "error":
            cls = "chip-error"
        elif s_key == stage:
            cls = "chip-active"
            reached = True
        elif not reached:
            cls = "chip-done"
        else:
            cls = "chip-pending"
        chips_html += f'<span class="stage-chip {cls}">{s_label}</span>'

    st.markdown(chips_html, unsafe_allow_html=True)
    st.progress(pct / 100, text=label if label else "Aguardando execução")

    if stage == "error":
        st.error(f"Erro: {status.get('error', '')[:300]}")

# Auto-refresh enquanto rodando
if is_running:
    time.sleep(2)
    st.rerun()

st.divider()


# ─── Resultados ──────────────────────────────────────────────────────────────

df_growth = load_artifact("analise_final.csv")
df_comparative = load_artifact("comparativo_paises.csv")
df_historico = load_artifact("historico.csv")
analysis = load_artifact("relatorio.json")

# Aplica a seleção de países/indicadores da sidebar às tabelas e gráficos exibidos
# (mesma convenção usada no payload enviado ao Claude: seleção vazia = mostra tudo).
if df_growth is not None and selected_countries:
    df_growth = df_growth[df_growth["Country Code"].isin(selected_countries)]
if df_comparative is not None and selected_countries:
    df_comparative = df_comparative[df_comparative["Country Code"].isin(selected_countries)]
if df_historico is not None and selected_countries:
    df_historico = df_historico[df_historico["Country Code"].isin(selected_countries)]

has_data = df_growth is not None or analysis is not None

if not has_data:
    st.info("""
**Como usar:**
1. Clique em **Executar Análise** — o sistema coleta dados automaticamente do World Bank API
2. Aguarde o pipeline processar os dados (2–5 min dependendo da conexão)
3. A análise executiva é gerada via **Claude** com saída estruturada
4. Visualize tabelas, gráficos e relatório — e baixe todos os artefatos

> **Opcional:** coloque os CSVs do Kaggle (EdStatsData.csv, EdStatsCountry.csv, EdStatsSeries.csv)
> na pasta `data/` para usar dados completos ao invés da API.
""")
else:
    # Métricas
    if df_growth is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Países", df_growth["Country Code"].nunique())
        c2.metric("Indicadores", df_growth["Indicator Code"].nunique())
        anos = f"{int(df_growth['Ano Inicio'].min())}–{int(df_growth['Ano Fim'].max())}" if len(df_growth) else "—"
        c3.metric("Período", anos)
        c4.metric("Registros", f"{len(df_growth):,}")
        st.divider()

    df_alerts = compute_alerts(df_growth)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Rankings", "📈 Gráficos", "🤖 Relatório Claude", "⬇️ Downloads",
         f"⚠️ Alertas ({len(df_alerts)})" if len(df_alerts) else "⚠️ Alertas"]
    )

    # ── Tab 1: Rankings ───────────────────────────────────────────────────
    with tab1:
        if df_growth is not None and len(df_growth) > 0:
            st.subheader("Rankings por Indicador")
            all_ind = df_growth["Indicator Code"].unique().tolist()
            ind_opts = [i for i in all_ind if not selected_indicators or i in selected_indicators] or all_ind
            sel = st.selectbox("Indicador", ind_opts,
                                format_func=lambda x: df_growth[df_growth["Indicator Code"] == x]["Indicador Label"].iloc[0]
                                if "Indicador Label" in df_growth.columns else x)
            df_sel = df_growth[df_growth["Indicator Code"] == sel].sort_values("Crescimento %", ascending=False)
            show_cols = [c for c in ["Country Name","Country Code","Valor Inicio","Valor Fim",
                                      "Crescimento %","CAGR %","Rank Valor Atual","Rank Crescimento %"]
                         if c in df_sel.columns]
            st.dataframe(friendly_columns(df_sel[show_cols]), use_container_width=True, height=400)

            if df_comparative is not None:
                st.subheader("Comparativo entre Países")
                df_comp_display = df_comparative.copy()
                if "Country Code" in df_comp_display.columns and df_growth is not None:
                    name_map = df_growth.drop_duplicates("Country Code").set_index("Country Code")["Country Name"]
                    df_comp_display.insert(1, "Country Name", df_comp_display["Country Code"].map(name_map))
                st.dataframe(friendly_columns(df_comp_display), use_container_width=True, height=300)
        else:
            st.info("Dados não disponíveis — execute a análise.")

    # ── Tab 2: Gráficos ───────────────────────────────────────────────────
    with tab2:
        if df_growth is not None and len(df_growth) > 0:
            all_ind2 = df_growth["Indicator Code"].unique().tolist()
            ind_opts2 = [i for i in all_ind2 if not selected_indicators or i in selected_indicators] or all_ind2
            sel2 = st.selectbox("Indicador para gráficos", ind_opts2, key="g_ind",
                                 format_func=lambda x: df_growth[df_growth["Indicator Code"] == x]["Indicador Label"].iloc[0]
                                 if "Indicador Label" in df_growth.columns else x)

            # Barras: crescimento %
            df_bar = df_growth[df_growth["Indicator Code"] == sel2].dropna(subset=["Crescimento %"])
            df_bar = df_bar.sort_values("Crescimento %", ascending=True)
            if len(df_bar):
                fig = px.bar(df_bar, x="Crescimento %", y="Country Code", orientation="h",
                             color="Crescimento %", color_continuous_scale="RdYlGn",
                             title=f"Crescimento % — {sel2}", height=480)
                st.plotly_chart(fig, use_container_width=True)

            # Linha: série histórica
            if df_historico is not None:
                df_hist = df_historico[df_historico["Indicator Code"] == sel2].dropna(subset=["Valor"])
                if len(df_hist):
                    fig2 = px.line(df_hist, x="Ano", y="Valor", color="Country Code",
                                   title=f"Evolução histórica — {sel2}", height=400)
                    st.plotly_chart(fig2, use_container_width=True)

            # Heatmap CAGR
            st.subheader("Heatmap CAGR % — todos indicadores")
            df_heat = df_growth.pivot_table(index="Country Code", columns="Indicator Code", values="CAGR %")
            if not df_heat.empty:
                fig3 = px.imshow(df_heat, color_continuous_scale="RdYlGn",
                                  title="CAGR Anual Composto (%)", aspect="auto", height=500)
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Execute a análise para ver os gráficos.")

    # ── Tab 3: Relatório Claude ───────────────────────────────────────────
    with tab3:
        if analysis:
            st.info(analysis.get("sumario_executivo", ""))
            col_l, col_r = st.columns(2)

            with col_l:
                with st.expander("🚀 Países em Evolução", expanded=True):
                    for p in analysis.get("paises_em_evolucao", []):
                        st.markdown(f"**{p.get('pais','')}** — {p.get('indicador','')}  \n"
                                    f"`{p.get('taxa_crescimento','')}` {p.get('destaque','')}")
                        st.divider()
                with st.expander("📉 Países Estagnados"):
                    for p in analysis.get("paises_estagnados", []):
                        st.markdown(f"**{p.get('pais','')}** — {p.get('indicador','')}  \n"
                                    f"Período: `{p.get('periodo_observado','')}` {p.get('observacao','')}")
                        st.divider()

            with col_r:
                with st.expander("💰 Maior Investimento", expanded=True):
                    for p in analysis.get("maior_investimento", []):
                        st.markdown(f"**{p.get('pais','')}** — {p.get('valor_percentual','')}  \n"
                                    f"{p.get('relacao_desempenho','')}")
                        st.divider()
                with st.expander("🏆 Melhores Indicadores Gerais"):
                    for p in analysis.get("melhores_indicadores", []):
                        st.markdown(f"**{p.get('pais','')}** — {p.get('justificativa','')}")
                        for ind in p.get("indicadores_destaque", []):
                            st.markdown(f"  - {ind}")
                        st.divider()

            with st.expander("💡 Hipóteses Explicativas"):
                for h in analysis.get("explicacoes", []):
                    badge = {"alto":"🟢","médio":"🟡","baixo":"🔴"}.get(h.get("nivel_confianca",""),"⚪")
                    st.markdown(f"{badge} **[Hipótese — confiança {h.get('nivel_confianca','')}]**  \n"
                                f"{h.get('hipotese','')}  \n*Evidência: {h.get('evidencia','')}*")
                    st.divider()

            with st.expander("📋 Recomendações para Gestores"):
                for r in analysis.get("recomendacoes", []):
                    badge = {"alta":"🔴","média":"🟡","baixa":"🟢"}.get(r.get("prioridade",""),"⚪")
                    st.markdown(f"{badge} **[{r.get('prioridade','').upper()}]** {r.get('recomendacao','')}  \n"
                                f"*Público-alvo: {r.get('publico_alvo','')}*")
                    st.divider()
        else:
            relatorio_md = load_artifact("relatorio.md")
            if relatorio_md:
                st.markdown(relatorio_md)
            elif df_growth is not None and len(df_growth) > 0:
                st.warning("O pipeline de dados já rodou (veja as abas Rankings/Gráficos), mas o "
                           "relatório do Claude ainda não foi gerado — confira a mensagem de status "
                           "no topo da página para ver se houve erro na etapa de IA.")
            else:
                st.info("Execute a análise para ver o relatório gerado pelo Claude.")

    # ── Tab 4: Downloads ──────────────────────────────────────────────────
    with tab4:
        st.subheader("Download dos Artefatos")

        def dl_btn(label: str, fname: str, mime: str):
            path = OUTPUT_DIR / fname
            if path.exists():
                st.download_button(f"⬇️ {label}", path.read_bytes(), fname, mime,
                                   use_container_width=True)
            else:
                st.button(f"🔒 {label} (não gerado)", disabled=True, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        with c1: dl_btn("analise_final.csv", "analise_final.csv", "text/csv")
        with c2: dl_btn("Relatório Markdown", "relatorio.md", "text/markdown")
        with c3: dl_btn("Relatório PDF", "relatorio.pdf", "application/pdf")

        c4, c5, c6 = st.columns(3)
        with c4: dl_btn("comparativo_paises.csv", "comparativo_paises.csv", "text/csv")
        with c5: dl_btn("historico.csv", "historico.csv", "text/csv")
        with c6:
            if analysis:
                st.download_button("⬇️ relatorio.json", json.dumps(analysis, ensure_ascii=False, indent=2),
                                   "relatorio.json", "application/json", use_container_width=True)
            else:
                st.button("🔒 relatorio.json (não gerado)", disabled=True, use_container_width=True)

    # ── Tab 5: Alertas ─────────────────────────────────────────────────────
    with tab5:
        st.subheader("Alertas de Limite por Indicador")
        st.caption("Sinaliza países cujo valor mais recente ficou abaixo do patamar configurado. "
                   "Limites em `INDICATOR_THRESHOLDS` (dashboard.py).")
        if df_alerts is not None and len(df_alerts) > 0:
            st.warning(f"⚠️ {len(df_alerts)} alerta(s) encontrado(s).")
            st.dataframe(friendly_columns(df_alerts), use_container_width=True, height=400)
        else:
            st.success("✅ Nenhum indicador abaixo dos limites configurados para a seleção atual.")


# ─── Footer ──────────────────────────────────────────────────────────────────
st.divider()
st.caption("🤖 Agente de Inteligência Global em Educação · Desafio Acelera AI · Claude + n8n + Streamlit")
