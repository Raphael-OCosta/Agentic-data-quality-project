# src/config.py
from dotenv import load_dotenv
load_dotenv()  # carrega OPENAI_API_KEY do .env (se existir)

from pathlib import Path

# Raiz do projeto = .../agentic-data-quality
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Caminho de arquivo do DuckDB (para duckdb.connect)
DB_PATH = str(PROJECT_ROOT / "agentic.duckdb")

# URI SQLAlchemy do DuckDB (para LangChain SQLDatabase via duckdb-engine)
DB_URI = f"duckdb:///{DB_PATH}"

# Tabelas
RAW_TABLE = "raw.sales"
STG_TABLE = "stg.sales"
GOLD_TABLE = "gold.sales_clean"

# CSV como caminho ABSOLUTO (evita erro se rodar fora da raiz)
DATA_CSV = str(PROJECT_ROOT / "data" / "sales_raw.csv")

# Gate humano por padrão
REQUIRE_HUMAN_APPROVAL = True
