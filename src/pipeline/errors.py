"""Plain-English explanations for things that go wrong.

Anything the owner sees (control panel, run history, alerts) gets its
message from here, never a raw exception or stack trace.
"""

from google.api_core import exceptions
from googleapiclient.errors import HttpError


class PipelineError(Exception):
    """An expected failure whose message is already plain English and safe to show."""


def status_code(error: Exception) -> int | None:
    """Pull the HTTP status out of either Google client library's errors."""
    if isinstance(error, HttpError):
        return error.resp.status
    if isinstance(error, exceptions.GoogleAPICallError):
        return error.code
    return None


def explain_error(error: Exception, source: str) -> str:
    """Turn a failed call into a plain-English likely cause."""
    if isinstance(error, PipelineError):
        return str(error)
    text = str(error)
    code = status_code(error)
    if isinstance(error, FileNotFoundError):
        return "service-account.json wasn't found. Run this from the project's main folder."
    if code == 403 and ("SERVICE_DISABLED" in text or "has not been used" in text):
        return (
            f"The {source} API is turned off in the Google Cloud project. "
            "Someone needs to enable it in the Cloud Console (APIs & Services > Library)."
        )
    if code == 403:
        return f"Google said no (403). The service account probably hasn't been added to the {source} property yet."
    if code == 401:
        return "Google rejected the key (401). service-account.json may be wrong, expired, or deleted."
    if code == 404:
        return f"Google couldn't find that {source} property (404). Check the ID or site address in .env."
    if code == 400:
        return f"Google didn't accept the request (400). The {source} ID in .env is probably in the wrong format."
    return f"Something unexpected went wrong talking to {source} ({type(error).__name__})."
