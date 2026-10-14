"""Run the full strategy arena from the command line (the dashboard button does the same)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunder.backtest.arena import run_arena  # noqa: E402
from thunder.config import load_config  # noqa: E402
from thunder.db import connect  # noqa: E402
from thunder.insights import report  # noqa: E402

if __name__ == "__main__":
    con = connect()
    res = run_arena(con, load_config(), progress=print)
    report.generate(con, "backtest")
    for sid, s in res["summary"].items():
        print(f"{sid:3} {s['status']:20} OOS trades {s['oos_trades']:4}  expectancy {s['expectancy_r']:+.3f}R  "
              f"CI [{s['ci'][0]:+.3f}, {s['ci'][1]:+.3f}]")
