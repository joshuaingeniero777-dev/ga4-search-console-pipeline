"""Run the API on this computer with a pretend sheet and pretend sign-in, for working on the control panel.

    python -m scripts.dev_api

Nothing here touches Google: settings and run history live in memory and vanish
when it stops, everyone counts as signed in as DEV_USER, and "Run now" runs the
pipeline stub against the pretend sheet. It only listens on this computer
(127.0.0.1). Never deploy this; the real API is `uvicorn api.main:app`.
"""

import threading
import time

import uvicorn

from api.auth import current_user
from api.main import app
from api.routes import get_dispatcher, get_store
from pipeline import runner
from pipeline.store import Run, Store
from scripts.dev_sheet import FakeSpreadsheet

DEV_USER = "dev@joinswc.org"
HOST = "127.0.0.1"
PORT = 8000
RUN_SECONDS = 8  # long enough to see "running" in the panel


class DevDispatcher:
    """Runs the stub in a background thread after a pause, like a real run would take time."""

    def __init__(self, store: Store, seconds: float = RUN_SECONDS):
        self.store = store
        self.seconds = seconds

    def dispatch(self, run: Run) -> None:
        def work():
            time.sleep(self.seconds)
            runner.run(run.start_date, run.end_date, store=self.store, run_id=run.id)

        threading.Thread(target=work, daemon=True).start()


def configure(seconds: float = RUN_SECONDS) -> Store:
    """Point the API at a fresh pretend sheet with one finished run in its history."""
    store = Store(FakeSpreadsheet(), editor_email="dev-pipeline@example.iam.gserviceaccount.com")
    runner.run(store=store)
    dispatcher = DevDispatcher(store, seconds)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[current_user] = lambda: DEV_USER
    return store


def main() -> None:
    configure()
    print(f"Dev API with a pretend sheet, signed in as {DEV_USER}: http://{HOST}:{PORT}")
    print("Nothing here touches Google. Stop it with Ctrl+C.")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
