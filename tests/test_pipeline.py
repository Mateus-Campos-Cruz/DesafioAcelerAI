"""Testes unitarios do pipeline de dados (pipeline.py)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import calculate_growth, filter_and_melt, generate_comparatives, generate_rankings


def _sample_long_df() -> pd.DataFrame:
    rows = []
    for country, code, offset in [("Brazil", "BRA", 0.0), ("Finland", "FIN", 1.0)]:
        for year, val in zip([2010, 2015, 2020], [4.0, 5.0, 6.0]):
            rows.append({
                "Country Code": code,
                "Country Name": country,
                "Indicator Code": "SE.XPD.TOTL.GD.ZS",
                "Indicador Label": "Gasto publico em educacao (% PIB)",
                "Ano": year,
                "Valor": val + offset,
            })
    return pd.DataFrame(rows)


def test_calculate_growth_basic():
    growth = calculate_growth(_sample_long_df())
    bra = growth[growth["Country Code"] == "BRA"].iloc[0]
    assert bra["Ano Inicio"] == 2010
    assert bra["Ano Fim"] == 2020
    assert bra["Valor Inicio"] == 4.0
    assert bra["Valor Fim"] == 6.0
    assert bra["Crescimento %"] == 50.0
    assert bra["N Obs"] == 3


def test_calculate_growth_skips_single_observation():
    df = _sample_long_df()
    single_point = df[(df["Country Code"] == "BRA") & (df["Ano"] == 2010)]
    assert calculate_growth(single_point).empty


def test_generate_rankings_adds_rank_columns():
    ranked = generate_rankings(calculate_growth(_sample_long_df()))
    assert {"Rank Valor Atual", "Rank Crescimento %"} <= set(ranked.columns)
    top = ranked.sort_values("Rank Valor Atual").iloc[0]
    assert top["Country Code"] == "FIN"


def test_generate_comparatives_pivots_by_country():
    df = _sample_long_df()
    ranked = generate_rankings(calculate_growth(df))
    comparative = generate_comparatives(df, ranked)
    assert "SE.XPD.TOTL.GD.ZS" in comparative.columns
    assert set(comparative["Country Code"]) == {"BRA", "FIN"}
    assert "Media_CAGR" in comparative.columns


def test_filter_and_melt_keeps_only_priority_countries_and_indicators():
    df_data = pd.DataFrame([
        {
            "Country Name": "Brazil", "Country Code": "BRA",
            "Indicator Name": "Gasto publico em educacao", "Indicator Code": "SE.XPD.TOTL.GD.ZS",
            "2010": 4.0, "2015": 5.0, "2020": 6.0,
        },
        {
            "Country Name": "Nowhere", "Country Code": "ZZZ",
            "Indicator Name": "Indicador fora da lista", "Indicator Code": "XX.YY.ZZ",
            "2010": 1.0, "2015": 2.0, "2020": 3.0,
        },
    ])
    result = filter_and_melt(df_data, df_country=pd.DataFrame())
    assert set(result["Country Code"]) == {"BRA"}
    assert set(result["Ano"]) == {2010, 2015, 2020}
    assert "Indicador Label" in result.columns
