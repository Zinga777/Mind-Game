"""Back up the THUNDER database to data/backups (keeps the last 14)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.db import backup  # noqa: E402

if __name__ == "__main__":
    print(f"Backup written to {backup()}")
