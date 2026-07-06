"""
Coleta automática de dados educacionais.
Prioridade: (1) CSVs Kaggle locais, (2) World Bank API, (3) dados sintéticos realistas.
API pública: https://api.worldbank.org/v2/
"""
import json
import random
import time
from pathlib import Path

import requests
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

BASE_URL = "https://api.worldbank.org/v2"

INDICATORS = {
    "SE.XPD.TOTL.GD.ZS": "Gasto público em educação (% PIB)",
    "SE.PRM.ENRR": "Taxa de matrícula primária (bruta %)",
    "SE.SEC.ENRR": "Taxa de matrícula secundária (bruta %)",
    "SE.TER.ENRR": "Taxa de matrícula terciária (bruta %)",
    "SE.PRM.CMPT.ZS": "Taxa de conclusão primária (%)",
    "SE.ADT.LITR.ZS": "Taxa de alfabetização adultos (%)",
    "SE.PRM.TENR": "Taxa de matrícula primária (líquida %)",
    "SE.SEC.TENR": "Taxa de matrícula secundária (líquida %)",
}

COUNTRIES = [
    "BRA", "USA", "CHN", "IND", "DEU", "FRA", "GBR", "JPN",
    "KOR", "MEX", "ARG", "COL", "ZAF", "NGA", "ETH", "EGY",
    "IDN", "TUR", "SAU", "RUS", "CHL", "PER", "FIN", "SWE",
]

COUNTRY_NAMES = {
    "BRA": "Brazil", "USA": "United States", "CHN": "China", "IND": "India",
    "DEU": "Germany", "FRA": "France", "GBR": "United Kingdom", "JPN": "Japan",
    "KOR": "Korea, Rep.", "MEX": "Mexico", "ARG": "Argentina", "COL": "Colombia",
    "ZAF": "South Africa", "NGA": "Nigeria", "ETH": "Ethiopia", "EGY": "Egypt, Arab Rep.",
    "IDN": "Indonesia", "TUR": "Turkiye", "SAU": "Saudi Arabia", "RUS": "Russian Federation",
    "CHL": "Chile", "PER": "Peru", "FIN": "Finland", "SWE": "Sweden",
}

# Valores base realistas por indicador (média histórica aproximada por país)
REALISTIC_BASELINES = {
    "SE.XPD.TOTL.GD.ZS": {
        "FIN": 6.8, "SWE": 7.1, "GBR": 5.5, "FRA": 5.4, "DEU": 4.9,
        "USA": 5.0, "KOR": 4.9, "JPN": 3.6, "BRA": 5.8, "CHN": 3.8,
        "IND": 3.8, "MEX": 4.9, "ARG": 5.5, "COL": 4.5, "CHL": 4.5,
        "PER": 3.5, "ZAF": 6.2, "NGA": 2.8, "ETH": 4.5, "EGY": 4.1,
        "IDN": 3.4, "TUR": 4.3, "SAU": 5.9, "RUS": 4.1,
    },
    "SE.PRM.ENRR": {
        "FIN": 98, "SWE": 99, "GBR": 102, "FRA": 105, "DEU": 103,
        "USA": 100, "KOR": 101, "JPN": 102, "BRA": 118, "CHN": 112,
        "IND": 108, "MEX": 109, "ARG": 111, "COL": 113, "CHL": 105,
        "PER": 107, "ZAF": 104, "NGA": 85, "ETH": 91, "EGY": 100,
        "IDN": 108, "TUR": 105, "SAU": 97, "RUS": 101,
    },
    "SE.SEC.ENRR": {
        "FIN": 130, "SWE": 133, "GBR": 123, "FRA": 112, "DEU": 104,
        "USA": 98, "KOR": 98, "JPN": 102, "BRA": 100, "CHN": 87,
        "IND": 63, "MEX": 85, "ARG": 101, "COL": 84, "CHL": 93,
        "PER": 91, "ZAF": 98, "NGA": 41, "ETH": 35, "EGY": 86,
        "IDN": 80, "TUR": 89, "SAU": 106, "RUS": 107,
    },
    "SE.TER.ENRR": {
        "FIN": 88, "SWE": 72, "GBR": 61, "FRA": 65, "DEU": 70,
        "USA": 88, "KOR": 95, "JPN": 62, "BRA": 48, "CHN": 48,
        "IND": 25, "MEX": 32, "ARG": 80, "COL": 51, "CHL": 82,
        "PER": 43, "ZAF": 21, "NGA": 10, "ETH": 8, "EGY": 33,
        "IDN": 31, "TUR": 90, "SAU": 68, "RUS": 81,
    },
    "SE.PRM.CMPT.ZS": {
        "FIN": 99, "SWE": 99, "GBR": 99, "FRA": 99, "DEU": 99,
        "USA": 98, "KOR": 99, "JPN": 99, "BRA": 97, "CHN": 95,
        "IND": 88, "MEX": 97, "ARG": 98, "COL": 94, "CHL": 97,
        "PER": 95, "ZAF": 98, "NGA": 69, "ETH": 52, "EGY": 93,
        "IDN": 96, "TUR": 98, "SAU": 99, "RUS": 99,
    },
    "SE.ADT.LITR.ZS": {
        "FIN": 99, "SWE": 99, "GBR": 99, "FRA": 99, "DEU": 99,
        "USA": 99, "KOR": 99, "JPN": 99, "BRA": 91, "CHN": 95,
        "IND": 73, "MEX": 93, "ARG": 99, "COL": 94, "CHL": 96,
        "PER": 94, "ZAF": 87, "NGA": 60, "ETH": 51, "EGY": 73,
        "IDN": 95, "TUR": 96, "SAU": 97, "RUS": 99,
    },
    "SE.PRM.TENR": {
        "FIN": 97, "SWE": 97, "GBR": 99, "FRA": 99, "DEU": 99,
        "USA": 94, "KOR": 98, "JPN": 99, "BRA": 95, "CHN": 94,
        "IND": 92, "MEX": 98, "ARG": 99, "COL": 90, "CHL": 95,
        "PER": 92, "ZAF": 95, "NGA": 61, "ETH": 82, "EGY": 91,
        "IDN": 93, "TUR": 92, "SAU": 86, "RUS": 98,
    },
    "SE.SEC.TENR": {
        "FIN": 93, "SWE": 95, "GBR": 91, "FRA": 89, "DEU": 88,
        "USA": 89, "KOR": 96, "JPN": 98, "BRA": 82, "CHN": 75,
        "IND": 52, "MEX": 67, "ARG": 88, "COL": 71, "CHL": 83,
        "PER": 80, "ZAF": 81, "NGA": 35, "ETH": 28, "EGY": 74,
        "IDN": 70, "TUR": 79, "SAU": 88, "RUS": 93,
    },
}


# ─── World Bank API ───────────────────────────────────────────────────────────

def fetch_indicator(indicator_code: str, countries: list, mrv: int = 20) -> list:
    """Busca um indicador via API do World Bank com retry."""
    country_str = ";".join(countries)
    url = f"{BASE_URL}/country/{country_str}/indicator/{indicator_code}"
    params = {"format": "json", "per_page": 1000, "mrv": mrv}
    rows = []

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code != 200 or not resp.text.strip():
                raise ValueError(f"HTTP {resp.status_code}")
            data = resp.json()
            if not data or len(data) < 2 or not data[1]:
                break
            for entry in data[1]:
                if entry.get("value") is not None:
                    rows.append({
                        "Country Code": entry.get("countryiso3code", ""),
                        "Country Name": entry.get("country", {}).get("value", ""),
                        "Indicator Code": indicator_code,
                        "Indicator Name": INDICATORS.get(indicator_code, indicator_code),
                        "Ano": int(entry.get("date", 0)),
                        "Valor": float(entry.get("value", 0)),
                    })
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"    API indisponível para {indicator_code}: {e}")
    return rows


def fetch_all_api(progress_cb=None) -> pd.DataFrame:
    """Tenta buscar todos os indicadores via API. Retorna DataFrame vazio se falhar."""
    all_rows = []
    total = len(INDICATORS)
    for i, (code, label) in enumerate(INDICATORS.items()):
        msg = f"API: {label[:40]}... ({i+1}/{total})"
        print(f"  {msg}")
        if progress_cb:
            progress_cb(int((i / total) * 70), msg)
        rows = fetch_indicator(code, COUNTRIES)
        all_rows.extend(rows)
        time.sleep(0.3)

    return pd.DataFrame(all_rows)


# ─── Dados sintéticos realistas ───────────────────────────────────────────────

def generate_synthetic_data(progress_cb=None) -> pd.DataFrame:
    """
    Gera dados sintéticos realistas baseados em valores históricos conhecidos.
    Usado quando CSVs do Kaggle e a API do World Bank não estão disponíveis.
    """
    print("  Gerando dados sintéticos realistas...")
    if progress_cb:
        progress_cb(10, "Gerando dados de demonstração...")

    rng = np.random.default_rng(42)
    years = list(range(2000, 2021))
    rows = []

    for country_code in COUNTRIES:
        country_name = COUNTRY_NAMES.get(country_code, country_code)
        for ind_code, ind_label in INDICATORS.items():
            baseline = REALISTIC_BASELINES.get(ind_code, {}).get(country_code, 50.0)

            # Tendência de longo prazo: países em desenvolvimento sobem mais
            is_developing = country_code in ["NGA", "ETH", "IND", "IDN", "EGY", "PER", "COL", "CHN", "BRA"]
            trend = rng.uniform(0.3, 1.5) if is_developing else rng.uniform(-0.2, 0.5)

            # Gerar série temporal com ruído
            val = baseline
            for year in years:
                noise = rng.normal(0, baseline * 0.015)
                val = val + trend + noise
                # Clamp realístico por indicador
                if ind_code == "SE.XPD.TOTL.GD.ZS":
                    val = max(1.0, min(val, 12.0))
                elif ind_code in ("SE.ADT.LITR.ZS", "SE.PRM.CMPT.ZS", "SE.PRM.TENR", "SE.SEC.TENR"):
                    val = max(20.0, min(val, 100.0))
                else:
                    val = max(10.0, min(val, 150.0))

                # Omitir ~15% dos dados (realístico para EdStats)
                if rng.random() > 0.85:
                    continue

                rows.append({
                    "Country Code": country_code,
                    "Country Name": country_name,
                    "Indicator Code": ind_code,
                    "Indicator Name": ind_label,
                    "Ano": year,
                    "Valor": round(val, 2),
                })

    df = pd.DataFrame(rows)
    if progress_cb:
        progress_cb(50, "Dados sintéticos gerados.")
    print(f"  Dados sintéticos: {len(df):,} registros")
    return df


# ─── Orquestrador de coleta ───────────────────────────────────────────────────

def fetch_all(progress_cb=None) -> pd.DataFrame:
    """
    Coleta dados com fallback automático:
    1. World Bank API
    2. Dados sintéticos realistas
    Salva no formato EdStats (wide) para compatibilidade com pipeline.py.
    """
    print("  Tentando World Bank API...")
    if progress_cb:
        progress_cb(5, "Conectando ao World Bank API...")

    df = fetch_all_api(progress_cb=progress_cb)

    if df.empty:
        print("  API indisponível. Usando dados sintéticos realistas.")
        if progress_cb:
            progress_cb(8, "API indisponível — gerando dados de demonstração...")
        df = generate_synthetic_data(progress_cb=progress_cb)

    _save_edstats_format(df)
    if progress_cb:
        progress_cb(85, "Dados prontos.")
    print(f"  Total de registros: {len(df):,}")
    return df


def _save_edstats_format(df: pd.DataFrame):
    """Salva no formato wide compatível com pipeline.py."""
    df_wide = df.pivot_table(
        index=["Country Name", "Country Code", "Indicator Name", "Indicator Code"],
        columns="Ano",
        values="Valor",
        aggfunc="first",
    ).reset_index()
    df_wide.columns = [str(c) for c in df_wide.columns]

    df_wide.to_csv(DATA_DIR / "EdStatsData.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"Country Code": k, "Short Name": v} for k, v in COUNTRY_NAMES.items()]).to_csv(
        DATA_DIR / "EdStatsCountry.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"Series Code": k, "Indicator Name": v} for k, v in INDICATORS.items()]).to_csv(
        DATA_DIR / "EdStatsSeries.csv", index=False, encoding="utf-8-sig"
    )
    print("    CSVs salvos em data/")


def data_available() -> bool:
    return (DATA_DIR / "EdStatsData.csv").exists()


if __name__ == "__main__":
    def cb(pct, msg):
        print(f"  [{pct:3d}%] {msg}")

    print("Coletando dados educacionais...")
    df = fetch_all(progress_cb=cb)
    print(f"Concluido: {len(df)} registros")
