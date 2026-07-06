"""Script auxiliar: valida o ambiente antes de rodar o pipeline ou o dashboard.

Verifica dependências instaladas, variáveis de ambiente e dados de entrada,
e imprime um resumo com o que está pronto e o que falta configurar.
"""
import importlib
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
REQUIRED_PACKAGES = [
    "pandas", "numpy", "streamlit", "plotly", "requests", "dotenv", "anthropic",
]
DATA_FILES = ["EdStatsData.csv", "EdStatsCountry.csv", "EdStatsSeries.csv"]


def check_packages() -> list[str]:
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def check_env() -> dict:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    return {
        "env_file_exists": (BASE_DIR / ".env").exists(),
        "api_key_configured": bool(api_key) and "xxxx" not in api_key,
        "webhook_url_configured": bool(webhook_url),
    }


def check_data_files() -> list[str]:
    data_dir = BASE_DIR / "data"
    return [f for f in DATA_FILES if not (data_dir / f).exists()]


def main() -> None:
    print("=" * 60)
    print("VERIFICAÇÃO DE AMBIENTE — Agente de Inteligência Global em Educação")
    print("=" * 60)

    missing_pkgs = check_packages()
    if missing_pkgs:
        print(f"[ERRO] Pacotes Python faltando: {', '.join(missing_pkgs)}")
        print("       Rode: pip install -r requirements.txt")
    else:
        print("[OK] Todas as dependências Python estão instaladas.")

    env = check_env()
    print(f"[{'OK' if env['env_file_exists'] else 'AVISO'}] Arquivo .env "
          f"{'encontrado' if env['env_file_exists'] else 'não encontrado (copie de .env.example)'}.")
    print(f"[{'OK' if env['webhook_url_configured'] else 'INFO'}] WEBHOOK_URL "
          f"{'configurada — modo n8n ativo' if env['webhook_url_configured'] else 'não configurada — modo local será usado'}.")
    if not env["webhook_url_configured"] and not env["api_key_configured"]:
        print("[AVISO] Nem WEBHOOK_URL nem ANTHROPIC_API_KEY estão configuradas — "
              "a análise via Claude não vai rodar em nenhum dos dois modos.")

    missing_data = check_data_files()
    if missing_data:
        print(f"[INFO] CSVs do Kaggle ausentes em data/: {', '.join(missing_data)}. "
              "O pipeline usa fallback automático (World Bank API ou dados sintéticos).")
    else:
        print("[OK] CSVs do Kaggle (EdStats) encontrados em data/.")

    print("=" * 60)


if __name__ == "__main__":
    main()
