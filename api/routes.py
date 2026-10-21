"""The five endpoints. Each is a thin layer over the pipeline's store, runner and schedule.

Every endpoint needs a signed-in, allowed user (api.auth.current_user).

Google Sheets allows about 60 reads a minute for the service account; /status
uses about 4, so the panel should poll it no faster than every 15 seconds.
"""

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth import current_user
from api.dispatch import Dispatcher, LocalDispatcher
from api.schemas import (
    RunRequest,
    RunResponse,
    RunsResponse,
    SettingsResponse,
    SettingsUpdate,
    StatusResponse,
)
from pipeline import schedule
from pipeline.runner import InvalidDateRange, resolve_range
from pipeline.settings import SettingsInvalid, placeholder_warnings
from pipeline.store import SettingsConflict, Store

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(current_user)])

ALL_RUNS = 10_000  # list_runs reads the whole tab anyway; this just means "don't cut any off"
DISPATCH_FAILED = "The run couldn't be started. Please try again in a minute."


@lru_cache
def get_store() -> Store:
    # One Store per server process, so each tab's lock is checked once, not on every request.
    return Store.open()


def get_dispatcher() -> Dispatcher:
    return LocalDispatcher()


StoreDep = Annotated[Store, Depends(get_store)]
UserDep = Annotated[str, Depends(current_user)]
DispatcherDep = Annotated[Dispatcher, Depends(get_dispatcher)]


def _when(moment: datetime) -> str:
    """e.g. 'Tue 20 Oct, 6:00 AM', in New York time."""
    local = moment.astimezone(schedule.TIMEZONE)
    hour = local.strftime("%I").lstrip("0")
    return f"{local:%a} {local.day} {local:%b}, {hour}:{local:%M} {local:%p}"


@router.get("/status", response_model=StatusResponse)
def get_status(store: StoreDep) -> StatusResponse:
    warnings: list[str] = []
    settings_problem = None
    try:
        warnings += placeholder_warnings(store.read_settings().settings)
    except SettingsInvalid as error:
        settings_problem = str(error)

    runs = store.list_runs(limit=ALL_RUNS)
    current = next((run for run in runs if run.status == "running"), None)
    finished = next((run for run in runs if run.status != "running"), None)

    warnings += [
        f"The {title} tab in the sheet had been unlocked. It was locked again on {_when(at)}. "
        "Please check the settings still look right."
        for title, at in store.relocked.items()
    ]

    if settings_problem:
        state, message = "settings_invalid", f"The settings have a problem, so runs will fail until it's fixed. {settings_problem}"
    elif current:
        state, message = "running", f"A run is in progress (started {_when(current.started_at)})."
    elif finished is None:
        state, message = "never_run", "The pipeline hasn't run yet."
    elif finished.status == "success":
        state, message = "ok", f"The last run ({_when(finished.started_at)}) worked. {finished.message}".strip()
    else:
        state, message = "failed", f"The last run ({_when(finished.started_at)}) failed. {finished.message}".strip()

    return StatusResponse(
        state=state,
        message=message,
        warnings=warnings,
        last_run=runs[0] if runs else None,
        next_run_at=schedule.next_run_at(datetime.now(UTC)),
    )


@router.get("/runs", response_model=RunsResponse)
def get_runs(store: StoreDep, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> RunsResponse:
    return RunsResponse(runs=store.list_runs(limit=limit))


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
def start_run(
    user: UserDep, store: StoreDep, dispatcher: DispatcherDep, body: RunRequest | None = None
) -> RunResponse:
    body = body or RunRequest()
    try:
        start, end = resolve_range(body.start_date, body.end_date, schedule.today())
    except InvalidDateRange as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    if store.current_run() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A run is already in progress. Wait for it to finish, then try again.")

    # Recorded before it's started, so a second click straight away gets the 409 above.
    run = store.start_run(start, end, "manual", user)
    try:
        dispatcher.dispatch(run)
    except Exception:
        log.exception("Couldn't dispatch run %s", run.id)
        store.finish_run(run.id, "failed", None, DISPATCH_FAILED)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, DISPATCH_FAILED) from None
    return RunResponse(run=run)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(store: StoreDep) -> SettingsResponse:
    try:
        record = store.read_settings()
    except SettingsInvalid as error:
        # Still return the version, so the panel can save corrected settings over the broken ones.
        version, updated_by = store.settings_meta()
        return SettingsResponse(settings=None, problem=str(error), version=version, updated_by=updated_by)
    return SettingsResponse(
        settings=record.settings,
        version=record.version,
        updated_by=record.updated_by,
        warnings=placeholder_warnings(record.settings),
    )


@router.put("/settings", response_model=SettingsResponse)
def put_settings(body: SettingsUpdate, user: UserDep, store: StoreDep) -> SettingsResponse:
    try:
        record = store.write_settings(body.settings, user, expected_version=body.version)
    except SettingsConflict as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    return SettingsResponse(
        settings=record.settings,
        version=record.version,
        updated_by=record.updated_by,
        warnings=placeholder_warnings(record.settings),
    )
