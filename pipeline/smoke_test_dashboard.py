"""Renders the whole Streamlit dashboard headlessly against a given SQLite database.

Fails (non-zero exit) if any element raises. Used by CI after the pipeline has
exported the mart, to prove the warehouse output still feeds the dashboard.

    python pipeline/smoke_test_dashboard.py sql/lichess_platform.db
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

import queries  # noqa: E402  (imported first so the patched path is the one app.py sees)
from streamlit.testing.v1 import AppTest  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    queries.DB_PATH = Path(sys.argv[1]).resolve()

    app = AppTest.from_file(str(REPO_ROOT / "dashboard" / "app.py"), default_timeout=180).run()
    if app.exception:
        for exception in app.exception:
            print("Dashboard error:", exception.value)
        return 1
    print(f"Dashboard rendered without errors ({len(app.metric)} metrics, {len(app.subheader)} subheaders).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
