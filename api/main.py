"""The control panel's backend. Run locally from the repo root with:

    uvicorn api.main:app --reload

Every error comes back as {"detail": "<plain English>"}. The real error, if any,
goes to the server log, never to the browser.

Settings, read from the environment (or .env locally):
    GOOGLE_OAUTH_CLIENT_ID  the panel's Google sign-in client ID (required; without it nobody can sign in)
    ALLOWED_DOMAINS         comma-separated Workspace domains (default: both business domains)
    PANEL_ORIGIN            where the control panel is served (default: http://localhost:3000)
    API_DOCS=1              turn on the interactive docs at /docs (off by default)
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router
from pipeline.errors import PipelineError
from pipeline.settings import describe_errors

load_dotenv()
log = logging.getLogger(__name__)

# How request fields are named in error messages. None = leave out of the location.
REQUEST_LABELS = {
    "body": None,
    "query": None,
    "settings": None,
    "start_date": "Start date",
    "end_date": "End date",
    "version": "Version",
    "limit": "Limit",
}
SERVER_ERROR = "Something went wrong on the server, so that didn't work. Please try again; if it keeps happening, the server log has the details."

docs_on = os.environ.get("API_DOCS") == "1"
app = FastAPI(
    title="SWC pipeline control panel API",
    docs_url="/docs" if docs_on else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_on else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("PANEL_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": describe_errors(list(error.errors()), REQUEST_LABELS)},
    )


@app.exception_handler(PipelineError)
async def pipeline_problem(request: Request, error: PipelineError) -> JSONResponse:
    # Expected problems (e.g. SPREADSHEET_ID missing) whose message is already plain English.
    log.warning("%s: %s", type(error).__name__, error)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(error)})


@app.exception_handler(Exception)
async def unexpected(request: Request, error: Exception) -> JSONResponse:
    log.exception("Unexpected error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": SERVER_ERROR})
