"""
Orquestrador ponta a ponta — execução completa do pipeline sem intervenção manual.
Fluxo: Coleta -> Tratamento -> Análise -> Relatório (IA) -> PDF
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

STATUS_FILE = OUTPUT_DIR / "pipeline_status.json"


# ─── Status tracking ─────────────────────────────────────────────────────────

def write_status(stage: str, label: str, pct: int, error: str = None, outputs: dict = None):
    status = {
        "stage": stage,
        "stage_label": label,
        "progress_pct": pct,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error,
        "outputs": outputs or {},
    }
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def read_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"stage": "idle", "stage_label": "Aguardando", "progress_pct": 0}


# ─── Stages ──────────────────────────────────────────────────────────────────

def stage_coleta(progress_cb=None):
    """Etapa 1: Coleta de dados (Kaggle CSV ou World Bank API)."""
    from fetch_worldbank import data_available, fetch_all

    if data_available():
        print("[Etapa 1] Dados já disponíveis — usando CSVs existentes.")
        if progress_cb:
            progress_cb(10, "Dados locais encontrados.")
    else:
        print("[Etapa 1] CSVs não encontrados — coletando via World Bank API...")
        write_status("fetching", "Coletando dados do World Bank API...", 5)

        def api_progress(pct, msg):
            write_status("fetching", msg, 5 + int(pct * 0.2))
            if progress_cb:
                progress_cb(5 + int(pct * 0.2), msg)

        fetch_all(progress_cb=api_progress)
        print("[Etapa 1] Coleta concluída.")


def stage_pipeline(progress_cb=None):
    """Etapa 2: Tratamento e enriquecimento analítico."""
    print("[Etapa 2] Executando pipeline de dados...")
    write_status("processing", "Limpando e processando dados...", 30)

    from pipeline import run_pipeline
    csv_path = run_pipeline()

    write_status("processing", "Pipeline de dados concluído.", 55)
    if progress_cb:
        progress_cb(55, "Pipeline concluído.")
    return csv_path


def stage_claude(api_key: str, progress_cb=None):
    """Etapa 3: Análise via Claude (Anthropic API)."""
    print("[Etapa 3] Gerando análise executiva via Claude...")
    write_status("analyzing", "Chamando Claude para análise executiva...", 60)

    from claude_agent import run_claude_agent
    analysis = run_claude_agent(api_key=api_key)

    write_status("analyzing", "Análise Claude concluída.", 85)
    if progress_cb:
        progress_cb(85, "Análise Claude concluída.")
    return analysis


def stage_finalize():
    """Etapa 4: Verificação e consolidação dos outputs."""
    print("[Etapa 4] Verificando outputs gerados...")
    outputs = {}
    for name in ["analise_final.csv", "relatorio.json", "relatorio.md", "relatorio.pdf",
                 "comparativo_paises.csv", "historico.csv"]:
        path = OUTPUT_DIR / name
        outputs[name] = str(path) if path.exists() else None

    present = [k for k, v in outputs.items() if v]
    missing = [k for k, v in outputs.items() if not v]
    print(f"  Gerados: {present}")
    if missing:
        print(f"  Não gerados: {missing}")
    return outputs


# ─── Orquestrador principal ───────────────────────────────────────────────────

def run_full_pipeline(api_key: str = None, progress_cb=None):
    """
    Executa o pipeline completo ponta a ponta.
    progress_cb(pct: int, msg: str) — callback de progresso opcional.
    """
    start = time.time()
    write_status("starting", "Iniciando pipeline...", 0)

    if api_key is None:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    try:
        # 1. Coleta
        write_status("fetching", "Etapa 1/4 — Coleta de dados...", 5)
        stage_coleta(progress_cb=progress_cb)

        # 2. Pipeline de dados
        write_status("processing", "Etapa 2/4 — Tratamento e análise de dados...", 25)
        stage_pipeline(progress_cb=progress_cb)

        # 3. Claude IA
        if api_key:
            write_status("analyzing", "Etapa 3/4 — Geração de inteligência via Claude...", 58)
            stage_claude(api_key=api_key, progress_cb=progress_cb)
        else:
            print("[Etapa 3] ANTHROPIC_API_KEY não configurada — pulando análise Claude.")
            write_status("analyzing", "API Key não configurada — análise Claude ignorada.", 85)

        # 4. Finalização
        write_status("reporting", "Etapa 4/4 — Consolidando outputs...", 90)
        outputs = stage_finalize()

        elapsed = round(time.time() - start, 1)
        write_status("done", f"Pipeline concluído em {elapsed}s.", 100, outputs=outputs)

        if progress_cb:
            progress_cb(100, f"Concluído em {elapsed}s.")

        print(f"\n{'='*60}")
        print(f"Pipeline completo em {elapsed}s.")
        print(f"{'='*60}")
        for k, v in outputs.items():
            status_icon = "OK" if v else "--"
            print(f"  {status_icon} {k}")
        return outputs

    except Exception as exc:
        import traceback
        err = traceback.format_exc()
        write_status("error", f"Erro: {exc}", 0, error=err)
        print(f"[ERRO] {exc}")
        print(err)
        raise


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    def cli_progress(pct, msg):
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r[{bar}] {pct:3d}% — {msg}", end="", flush=True)

    print("=" * 60)
    print("AGENTE DE INTELIGÊNCIA GLOBAL EM EDUCAÇÃO")
    print("Pipeline Automatizado Ponta a Ponta")
    print("=" * 60)

    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("\nAVISO: ANTHROPIC_API_KEY não encontrada no .env")
        print("O pipeline de dados rodará, mas a análise Claude será ignorada.")
        print("Configure a key no .env para gerar o relatório executivo.\n")

    run_full_pipeline(api_key=key, progress_cb=cli_progress)
    print()
