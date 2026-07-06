"""
Data Engineer Agent + Analytics Agent
Prioridade 1: Pipeline Python ponta a ponta
World Bank EdStats -> analise_final.csv
"""
import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Indicadores educacionais prioritários (Indicator Code -> label)
INDICATORS_PRIORITY = {
    "SE.XPD.TOTL.GD.ZS": "Gasto público em educação (% PIB)",
    "SE.PRM.ENRR": "Taxa de matrícula primária (bruta %)",
    "SE.SEC.ENRR": "Taxa de matrícula secundária (bruta %)",
    "SE.TER.ENRR": "Taxa de matrícula terciária (bruta %)",
    "SE.PRM.CMPT.ZS": "Taxa de conclusão primária (%)",
    "SE.ADT.LITR.ZS": "Taxa de alfabetização adultos (%)",
    "SE.PRM.TENR": "Taxa de matrícula primária (líquida %)",
    "SE.SEC.TENR": "Taxa de matrícula secundária (líquida %)",
    "UIS.XUNIT.GDPCAP.02.FSGOV": "Gasto por aluno primário (% PIB per capita)",
}

# Países de interesse para análise comparativa
COUNTRIES_PRIORITY = [
    "BRA", "USA", "CHN", "IND", "DEU", "FRA", "GBR", "JPN",
    "KOR", "MEX", "ARG", "COL", "ZAF", "NGA", "ETH", "EGY",
    "IDN", "TUR", "SAU", "RUS", "CHL", "PER", "FIN", "SWE",
]

YEAR_START = 2000
YEAR_END = 2020


# ─── MACROPROCESSO 1: Aquisição e Preparação ─────────────────────────────────

def load_data():
    """Ingere os três CSVs do EdStats."""
    print("[1/6] Carregando datasets EdStats...")
    paths = {
        "data": DATA_DIR / "EdStatsData.csv",
        "country": DATA_DIR / "EdStatsCountry.csv",
        "series": DATA_DIR / "EdStatsSeries.csv",
    }
    for name, path in paths.items():
        if not path.exists():
            print(f"  ERRO: {path} não encontrado.")
            print("  Coloque os CSVs do Kaggle (World Bank EdStats) na pasta data/")
            sys.exit(1)

    df_data = pd.read_csv(paths["data"], low_memory=False)
    df_country = pd.read_csv(paths["country"], low_memory=False)
    df_series = pd.read_csv(paths["series"], low_memory=False)
    print(f"  EdStatsData: {len(df_data):,} linhas | {df_data.shape[1]} colunas")
    print(f"  EdStatsCountry: {len(df_country):,} países/regiões")
    print(f"  EdStatsSeries: {len(df_series):,} indicadores")
    return df_data, df_country, df_series


def filter_and_melt(df_data: pd.DataFrame, df_country: pd.DataFrame) -> pd.DataFrame:
    """Filtra indicadores/países prioritários e transforma em formato longo."""
    print("[2/6] Filtrando e limpando dados...")

    # Normalizar nome das colunas
    df_data.columns = df_data.columns.str.strip()

    # Identificar colunas de anos
    year_cols = [c for c in df_data.columns if c.strip().isdigit()]
    year_cols_filtered = [c for c in year_cols if YEAR_START <= int(c) <= YEAR_END]

    meta_cols = ["Country Name", "Country Code", "Indicator Name", "Indicator Code"]
    missing_meta = [c for c in meta_cols if c not in df_data.columns]
    if missing_meta:
        # Tentar nomes alternativos
        df_data.columns = df_data.columns.str.strip()
        meta_cols = [c for c in df_data.columns if "country" in c.lower() or "indicator" in c.lower()]

    # Filtrar indicadores prioritários
    indicator_codes = list(INDICATORS_PRIORITY.keys())
    df_filtered = df_data[df_data["Indicator Code"].isin(indicator_codes)].copy()

    # Filtrar países prioritários
    df_filtered = df_filtered[df_filtered["Country Code"].isin(COUNTRIES_PRIORITY)].copy()

    if df_filtered.empty:
        print("  AVISO: Nenhum dado encontrado com os filtros exatos. Usando top indicadores/países disponíveis.")
        df_filtered = df_data[df_data["Indicator Code"].isin(indicator_codes)].copy()
        if df_filtered.empty:
            df_filtered = df_data.head(5000).copy()

    # Melt para formato longo
    cols_to_keep = [c for c in meta_cols if c in df_data.columns] + year_cols_filtered
    cols_available = [c for c in cols_to_keep if c in df_filtered.columns]
    df_melted = df_filtered[cols_available].melt(
        id_vars=[c for c in meta_cols if c in df_filtered.columns],
        var_name="Ano",
        value_name="Valor"
    )
    df_melted["Ano"] = pd.to_numeric(df_melted["Ano"], errors="coerce")
    df_melted["Valor"] = pd.to_numeric(df_melted["Valor"], errors="coerce")

    # Remover NaNs
    df_melted = df_melted.dropna(subset=["Valor"])
    df_melted = df_melted[df_melted["Valor"].notna()]

    # Adicionar label descritivo
    df_melted["Indicador Label"] = df_melted["Indicator Code"].map(INDICATORS_PRIORITY).fillna(
        df_melted["Indicator Name"] if "Indicator Name" in df_melted.columns else "Desconhecido"
    )

    print(f"  Dados filtrados: {len(df_melted):,} registros | "
          f"{df_melted['Country Code'].nunique()} países | "
          f"{df_melted['Indicator Code'].nunique()} indicadores")
    return df_melted


# ─── MACROPROCESSO 2: Processamento e Enriquecimento Analítico ───────────────

def calculate_growth(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula crescimento histórico por país/indicador."""
    print("[3/6] Calculando crescimento histórico...")
    results = []

    for (country_code, indicator_code), grp in df.groupby(["Country Code", "Indicator Code"]):
        grp_sorted = grp.sort_values("Ano")
        values = grp_sorted.dropna(subset=["Valor"])
        if len(values) < 2:
            continue

        val_inicio = values.iloc[0]["Valor"]
        val_fim = values.iloc[-1]["Valor"]
        ano_inicio = int(values.iloc[0]["Ano"])
        ano_fim = int(values.iloc[-1]["Ano"])
        n_anos = ano_fim - ano_inicio

        if n_anos > 0 and val_inicio > 0:
            crescimento_abs = val_fim - val_inicio
            crescimento_pct = ((val_fim - val_inicio) / abs(val_inicio)) * 100
            cagr = ((val_fim / val_inicio) ** (1 / n_anos) - 1) * 100
        else:
            crescimento_abs = crescimento_pct = cagr = np.nan

        results.append({
            "Country Code": country_code,
            "Country Name": values.iloc[0].get("Country Name", country_code),
            "Indicator Code": indicator_code,
            "Indicador Label": values.iloc[0].get("Indicador Label", indicator_code),
            "Ano Inicio": ano_inicio,
            "Ano Fim": ano_fim,
            "Valor Inicio": round(val_inicio, 4),
            "Valor Fim": round(val_fim, 4),
            "Crescimento Absoluto": round(crescimento_abs, 4) if not np.isnan(crescimento_abs) else None,
            "Crescimento %": round(crescimento_pct, 2) if not np.isnan(crescimento_pct) else None,
            "CAGR %": round(cagr, 3) if not np.isnan(cagr) else None,
            "N Obs": len(values),
        })

    df_growth = pd.DataFrame(results)
    print(f"  Crescimento calculado: {len(df_growth):,} combinações país/indicador")
    return df_growth


def generate_rankings(df_growth: pd.DataFrame) -> pd.DataFrame:
    """Gera rankings por indicador baseados no valor final e crescimento."""
    print("[4/6] Gerando rankings...")
    dfs = []
    for indicator_code, grp in df_growth.groupby("Indicator Code"):
        grp = grp.copy()
        grp["Rank Valor Atual"] = grp["Valor Fim"].rank(ascending=False, method="min")
        grp["Rank Crescimento %"] = grp["Crescimento %"].rank(ascending=False, method="min")
        dfs.append(grp)

    df_ranked = pd.concat(dfs, ignore_index=True) if dfs else df_growth.copy()
    print(f"  Rankings gerados para {df_ranked['Indicator Code'].nunique()} indicadores")
    return df_ranked


def generate_comparatives(df_melted: pd.DataFrame, df_growth: pd.DataFrame) -> pd.DataFrame:
    """Gera tabela comparativa entre países para o último ano disponível."""
    print("[5/6] Gerando comparativos entre países...")
    latest_year = int(df_melted["Ano"].max())

    # Pegar valor mais recente por país/indicador
    df_latest = df_melted[df_melted["Ano"] == latest_year].copy()
    if df_latest.empty:
        # Fallback: último valor disponível por país/indicador
        df_latest = df_melted.sort_values("Ano").groupby(
            ["Country Code", "Indicator Code"]
        ).last().reset_index()

    df_pivot = df_latest.pivot_table(
        index="Country Code",
        columns="Indicator Code",
        values="Valor",
        aggfunc="mean"
    ).reset_index()

    # Merge com info de crescimento
    df_summary = df_growth.groupby("Country Code").agg(
        Media_CAGR=("CAGR %", "mean"),
        Soma_Crescimento_Pct=("Crescimento %", "sum"),
        N_Indicadores=("Indicator Code", "nunique"),
    ).reset_index()

    df_comparative = df_pivot.merge(df_summary, on="Country Code", how="left")
    print(f"  Comparativo: {len(df_comparative)} países x {df_comparative.shape[1]} colunas")
    return df_comparative


def export_final_csv(df_growth: pd.DataFrame, df_comparative: pd.DataFrame, df_melted: pd.DataFrame):
    """Exporta analise_final.csv com todas as métricas."""
    print("[6/6] Exportando analise_final.csv...")

    # Arquivo principal de análise (rankings e crescimento)
    out_path = OUTPUT_DIR / "analise_final.csv"
    df_growth.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  Salvo: {out_path}")

    # Arquivo comparativo
    comp_path = OUTPUT_DIR / "comparativo_paises.csv"
    df_comparative.to_csv(comp_path, index=False, encoding="utf-8-sig")
    print(f"  Salvo: {comp_path}")

    # Dados históricos completos
    hist_path = OUTPUT_DIR / "historico.csv"
    df_melted.to_csv(hist_path, index=False, encoding="utf-8-sig")
    print(f"  Salvo: {hist_path}")

    # Metadata do pipeline
    meta = {
        "n_registros": len(df_growth),
        "n_paises": int(df_growth["Country Code"].nunique()),
        "n_indicadores": int(df_growth["Indicator Code"].nunique()),
        "ano_inicio": int(df_growth["Ano Inicio"].min()) if len(df_growth) > 0 else YEAR_START,
        "ano_fim": int(df_growth["Ano Fim"].max()) if len(df_growth) > 0 else YEAR_END,
    }
    with open(OUTPUT_DIR / "pipeline_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  Meta: {meta}")
    return out_path


# ─── MAIN ────────────────────────────────────────────────────────────────────

def run_pipeline():
    print("=" * 60)
    print("PIPELINE EDUCAÇÃO GLOBAL - World Bank EdStats")
    print("=" * 60)
    df_data, df_country, df_series = load_data()
    df_melted = filter_and_melt(df_data, df_country)
    df_growth = calculate_growth(df_melted)
    df_ranked = generate_rankings(df_growth)
    df_comparative = generate_comparatives(df_melted, df_ranked)
    out_path = export_final_csv(df_ranked, df_comparative, df_melted)
    print("=" * 60)
    print(f"Pipeline concluído com sucesso! -> {out_path}")
    print("=" * 60)
    return str(out_path)


if __name__ == "__main__":
    run_pipeline()
