"""Load bundled SAMPLE DATA (synthetic candles) so the dashboard works offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.config import load_config  # noqa: E402
from thunder.data.downloader import load_demo  # noqa: E402
from thunder.db import connect  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    load_demo(connect(), cfg.exchange.instruments, days=180, seed=cfg.seed, future_days=60)
    print("SAMPLE DATA loaded.")
