"""
Claude Intelligence Agent
Macroprocesso 3: Geração de Inteligência via Claude (Anthropic API)
Lê analise_final.csv -> relatório executivo estruturado (JSON + Markdown + PDF)
"""
import os
import json
import sys
from pathlib import Path

import anthropic
import pandas as pd

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# Tool definition para saída estruturada garantida
ANALYSIS_TOOL = {
    "name": "registrar_analise_educacional",
    "description": "Registra a análise executiva estruturada sobre indicadores educacionais globais.",
    "input_schema": {
        "type": "object",
        "properties": {
            "paises_em_evolucao": {
                "type": "array",
                "description": "Países com maior evolução positiva nos indicadores educacionais.",
                "items": {
                    "type": "object",
                    "properties": {
                        "pais": {"type": "string"},
                        "indicador": {"type": "string"},
                        "taxa_crescimento": {"type": "string"},
                        "destaque": {"type": "string"},
                    },
                    "required": ["pais", "indicador", "taxa_crescimento"],
                },
            },
            "paises_estagnados": {
                "type": "array",
                "description": "Países com estagnação ou retrocesso em indicadores educacionais.",
                "items": {
                    "type": "object",
                    "properties": {
                        "pais": {"type": "string"},
                        "indicador": {"type": "string"},
                        "periodo_observado": {"type": "string"},
                        "observacao": {"type": "string"},
                    },
                    "required": ["pais", "indicador", "periodo_observado"],
                },
            },
            "maior_investimento": {
                "type": "array",
                "description": "Países com maior investimento público em educação.",
                "items": {
                    "type": "object",
                    "properties": {
                        "pais": {"type": "string"},
                        "valor_percentual": {"type": "string"},
                        "relacao_desempenho": {"type": "string"},
                    },
                    "required": ["pais", "valor_percentual"],
                },
            },
            "melhores_indicadores": {
                "type": "array",
                "description": "Países com melhores indicadores educacionais gerais.",
                "items": {
                    "type": "object",
                    "properties": {
                        "pais": {"type": "string"},
                        "justificativa": {"type": "string"},
                        "indicadores_destaque": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["pais", "justificativa"],
                },
            },
            "explicacoes": {
                "type": "array",
                "description": "Hipóteses explicativas para os padrões observados.",
                "items": {
                    "type": "object",
                    "properties": {
                        "hipotese": {"type": "string"},
                        "evidencia": {"type": "string"},
                        "nivel_confianca": {
                            "type": "string",
                            "enum": ["baixo", "médio", "alto"],
                        },
                    },
                    "required": ["hipotese", "evidencia", "nivel_confianca"],
                },
            },
            "recomendacoes": {
                "type": "array",
                "description": "Recomendações práticas para gestores educacionais.",
                "items": {
                    "type": "object",
                    "properties": {
                        "recomendacao": {"type": "string"},
                        "publico_alvo": {"type": "string"},
                        "prioridade": {
                            "type": "string",
                            "enum": ["alta", "média", "baixa"],
                        },
                    },
                    "required": ["recomendacao", "publico_alvo", "prioridade"],
                },
            },
            "sumario_executivo": {
                "type": "string",
                "description": "Parágrafo curto com o principal insight da análise.",
            },
        },
        "required": [
            "paises_em_evolucao",
            "paises_estagnados",
            "maior_investimento",
            "melhores_indicadores",
            "explicacoes",
            "recomendacoes",
            "sumario_executivo",
        ],
    },
}

SYSTEM_PROMPT = """Você é um agente especializado em inteligência analítica sobre indicadores educacionais globais.
Seu objetivo é transformar dados quantitativos em análise executiva e recomendações — nunca apenas resumir números.

Você receberá como entrada:
- Tabela de rankings de crescimento por país/indicador.
- Tabela comparativa entre países selecionados.
- Metadados (nome do indicador, unidade, período coberto).

Você deve executar:
1. Identificar quais países evoluíram mais e quais estão estagnados.
2. Relacionar nível de investimento público a desempenho educacional.
3. Apontar quais países possuem melhores indicadores em geral.
4. Propor explicações plausíveis para os padrões observados (marcando-as claramente como hipóteses, não fatos).
5. Gerar recomendações práticas para gestores educacionais.

Critérios de qualidade:
- Não repetir os números brutos — interpretá-los.
- Toda explicação causal deve ser identificada como hipótese, não fato.
- Usar sempre a tool de saída estruturada — nunca responder apenas em texto corrido.

Restrições:
- Não execute ações fora do escopo (não invente dados que não estejam no input).
- Não tome decisões críticas sem validação humana quando houver risco alto.
- Sempre indique incertezas, lacunas de dados ou dependências."""


def build_prompt(df_growth: pd.DataFrame) -> str:
    """Constrói prompt estruturado a partir do analise_final.csv."""
    n_paises = df_growth["Country Code"].nunique()
    n_indicadores = df_growth["Indicator Code"].nunique()
    ano_min = int(df_growth["Ano Inicio"].min())
    ano_max = int(df_growth["Ano Fim"].max())

    # Top crescimento por indicador
    top_crescimento = []
    for ind, grp in df_growth.groupby("Indicator Code"):
        label = grp.iloc[0].get("Indicador Label", ind)
        top5 = grp.nlargest(5, "Crescimento %")[
            ["Country Code", "Country Name", "Valor Inicio", "Valor Fim", "Crescimento %", "CAGR %"]
        ].to_dict("records")
        top_crescimento.append({"indicador": f"{label} ({ind})", "top5": top5})

    # Piores (estagnação)
    piores = df_growth.nsmallest(10, "Crescimento %")[
        ["Country Code", "Country Name", "Indicator Code", "Indicador Label", "Crescimento %", "Ano Inicio", "Ano Fim"]
    ].to_dict("records")

    # Maior investimento
    inv_col = "SE.XPD.TOTL.GD.ZS"
    df_inv = df_growth[df_growth["Indicator Code"] == inv_col].copy()
    if not df_inv.empty:
        investimento = df_inv.nlargest(5, "Valor Fim")[
            ["Country Code", "Country Name", "Valor Fim", "Crescimento %"]
        ].to_dict("records")
    else:
        investimento = []

    prompt = f"""Analise os dados educacionais do World Bank EdStats para {n_paises} países entre {ano_min} e {ano_max},
cobrindo {n_indicadores} indicadores educacionais prioritários.

=== TOP CRESCIMENTO POR INDICADOR ===
{json.dumps(top_crescimento, ensure_ascii=False, indent=2)}

=== PAÍSES COM MENOR CRESCIMENTO / ESTAGNAÇÃO ===
{json.dumps(piores, ensure_ascii=False, indent=2)}

=== INVESTIMENTO PÚBLICO EM EDUCAÇÃO (% PIB) ===
{json.dumps(investimento, ensure_ascii=False, indent=2)}

Gere uma análise executiva completa usando a tool 'registrar_analise_educacional'.
Interprete os dados, identifique padrões, proponha hipóteses e faça recomendações para gestores educacionais."""

    return prompt


def call_claude(prompt: str, api_key: str) -> dict:
    """Chama a Anthropic API com tool use para saída estruturada."""
    client = anthropic.Anthropic(api_key=api_key)

    print(f"  Chamando Claude ({MODEL})...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "registrar_analise_educacional"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extrair resultado da tool call
    for block in response.content:
        if block.type == "tool_use" and block.name == "registrar_analise_educacional":
            return block.input

    raise ValueError("Claude não retornou tool use. Verificar prompt/tool schema.")


def build_markdown(analysis: dict) -> str:
    """Converte JSON estruturado em Markdown formatado."""
    md = ["# Relatório Executivo — Indicadores Educacionais Globais\n"]
    md.append(f"**Gerado por:** Claude Intelligence Agent | **Modelo:** {MODEL}\n")
    md.append("---\n")

    md.append("## Sumário Executivo\n")
    md.append(f"{analysis.get('sumario_executivo', 'Nenhum sumário disponível.')}\n\n")

    md.append("## Países em Evolução\n")
    for p in analysis.get("paises_em_evolucao", []):
        md.append(f"- **{p.get('pais', '')}** — {p.get('indicador', '')} | Crescimento: {p.get('taxa_crescimento', '')}")
        if p.get("destaque"):
            md.append(f" — {p['destaque']}")
        md.append("\n")
    md.append("\n")

    md.append("## Países Estagnados\n")
    for p in analysis.get("paises_estagnados", []):
        md.append(f"- **{p.get('pais', '')}** — {p.get('indicador', '')} | Período: {p.get('periodo_observado', '')}")
        if p.get("observacao"):
            md.append(f" — {p['observacao']}")
        md.append("\n")
    md.append("\n")

    md.append("## Maior Investimento Público em Educação\n")
    for p in analysis.get("maior_investimento", []):
        md.append(f"- **{p.get('pais', '')}** — {p.get('valor_percentual', '')}")
        if p.get("relacao_desempenho"):
            md.append(f" — {p['relacao_desempenho']}")
        md.append("\n")
    md.append("\n")

    md.append("## Melhores Indicadores Gerais\n")
    for p in analysis.get("melhores_indicadores", []):
        md.append(f"- **{p.get('pais', '')}** — {p.get('justificativa', '')}\n")
        for ind in p.get("indicadores_destaque", []):
            md.append(f"  - {ind}\n")
    md.append("\n")

    md.append("## Hipóteses Explicativas\n")
    for h in analysis.get("explicacoes", []):
        confianca = h.get("nivel_confianca", "?")
        md.append(f"- **[Hipótese — confiança {confianca}]** {h.get('hipotese', '')}\n")
        md.append(f"  - Evidência: {h.get('evidencia', '')}\n")
    md.append("\n")

    md.append("## Recomendações para Gestores Educacionais\n")
    for r in analysis.get("recomendacoes", []):
        prioridade = r.get("prioridade", "?")
        md.append(f"- **[{prioridade.upper()}]** {r.get('recomendacao', '')} *(público-alvo: {r.get('publico_alvo', '')})*\n")
    md.append("\n")

    md.append("---\n*Este relatório foi gerado automaticamente. Recomenda-se revisão humana antes de uso em políticas públicas.*\n")
    return "".join(md)


def generate_pdf(md_path: Path, pdf_path: Path) -> bool:
    """Converte Markdown em PDF via weasyprint ou reportlab."""
    try:
        import weasyprint
        import markdown as md_lib
        html_content = md_lib.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables"])
        html_full = f"""<!DOCTYPE html><html><head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
  h1 {{ color: #1a4a7a; }} h2 {{ color: #2c6aa0; border-bottom: 1px solid #ccc; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
</style></head><body>{html_content}</body></html>"""
        weasyprint.HTML(string=html_full).write_pdf(str(pdf_path))
        print(f"  PDF gerado (weasyprint): {pdf_path}")
        return True
    except ImportError:
        pass

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for line in md_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
            elif line.startswith("# "):
                story.append(Paragraph(line[2:], styles["Title"]))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], styles["Heading2"]))
            else:
                clean = line.replace("**", "").replace("*", "")
                story.append(Paragraph(clean, styles["Normal"]))
        doc.build(story)
        print(f"  PDF gerado (reportlab): {pdf_path}")
        return True
    except ImportError:
        pass

    print("  AVISO: weasyprint e reportlab não disponíveis. PDF não gerado.")
    return False


def run_claude_agent(api_key: str = None) -> dict:
    """Executa o agente Claude completo."""
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada. Configure no .env ou passe como argumento.")

    # Carregar dados
    csv_path = OUTPUT_DIR / "analise_final.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"analise_final.csv não encontrado em {csv_path}. Execute pipeline.py primeiro.")

    print("[Claude Agent] Carregando analise_final.csv...")
    df_growth = pd.read_csv(csv_path, encoding="utf-8-sig")
    print(f"  {len(df_growth)} registros | {df_growth['Country Code'].nunique()} países")

    print("[Claude Agent] Construindo prompt...")
    prompt = build_prompt(df_growth)

    print("[Claude Agent] Chamando Anthropic API...")
    analysis = call_claude(prompt, api_key)

    # Salvar JSON
    json_path = OUTPUT_DIR / "relatorio.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"  Relatório JSON salvo: {json_path}")

    # Salvar Markdown
    md_path = OUTPUT_DIR / "relatorio.md"
    md_content = build_markdown(analysis)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"  Relatório MD salvo: {md_path}")

    # Gerar PDF
    pdf_path = OUTPUT_DIR / "relatorio.pdf"
    generate_pdf(md_path, pdf_path)

    print("[Claude Agent] Concluído!")
    return analysis


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = run_claude_agent()
    print(json.dumps(result, ensure_ascii=False, indent=2))
