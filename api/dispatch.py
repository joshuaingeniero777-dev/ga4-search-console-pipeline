"""How "Run now" actually starts a run.

The API never runs the pipeline inside itself; a run can take minutes and would
be cut off when the request ends. It records the run, then hands it to a
dispatcher, which starts `python -m pipeline.runner --run-id ...` somewhere else.

- LocalDispatcher: a separate process on this machine. For development.
- The Cloud Run Job dispatcher (decision 15) is added with deployment
  (docs/ROADMAP.md, item 7).
"""

import subprocess
import sys
from typing import Protocol

from pipeline.store import Run


class Dispatcher(Protocol):
    def dispatch(self, run: Run) -> None:
        """Start the run. Raise if it couldn't be started."""


def runner_command(run: Run) -> list[str]:
    # A list, never a shell string: the email and dates are passed as plain arguments.
    return [
        sys.executable,
        "-m",
        "pipeline.runner",
        "--run-id",
        run.id,
        "--start",
        run.start_date.isoformat(),
        "--end",
        run.end_date.isoformat(),
        "--trigger",
        run.trigger,
        "--triggered-by",
        run.triggered_by,
    ]


class LocalDispatcher:
    def dispatch(self, run: Run) -> None:
        subprocess.Popen(runner_command(run))
