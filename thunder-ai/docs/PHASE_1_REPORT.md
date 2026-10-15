# Phase 1 — Skeleton + dashboard (demo mode)

**What works:** config (pydantic + `config.yaml`), SQLite (WAL, versioned migrations), launchers for
Windows/macOS/Linux, engine/dashboard split through a `commands` table, 12 dashboard pages, mode ribbon
(SAMPLE DATA / BACKTEST / PAPER / LIVE), light/dark theme, Indian-grouped ₹ formatting, IST times, setup wizard.

**Tested:** Streamlit AppTest renders every page without errors; formatter tests; the Linux launcher was run on a
clean folder (created the venv, installed pinned packages, started both processes, served the page); a headless
phone-sized browser (390 px) showed no horizontal scrolling.

**Not verified:** the Windows `.bat` and macOS `.command` launchers were written but not run on those systems.
