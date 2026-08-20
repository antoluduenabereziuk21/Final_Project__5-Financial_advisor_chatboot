import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_financial_advisor.db")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
