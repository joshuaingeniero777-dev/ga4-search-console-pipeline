"""Write daily numbers into the sheet: a GA4 tab and a Search Console tab (decision 20).

One row per day. A day that's pulled again replaces its row, so re-pulls never
create duplicates (decision 3). Nothing is ever deleted: rows for days not in
this pull stay as they are, and if a metric is dropped from the settings its
column and history stay too; new days just leave it blank.

The tabs are locked like _settings and _runs, so only the pipeline can edit
them. Looker Studio reads them.
"""

from datetime import date, datetime

from pipeline.errors import PipelineError
from pipeline.store import Store

GA4_TAB = "GA4"
SEARCH_CONSOLE_TAB = "Search Console"
DATE_COLUMN = "date"
UPDATED_COLUMN = "updated_at"
DATE_FORMAT = {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}


def merge(existing: list[list], fresh: dict[str, dict], metrics: list[str], tab: str, updated_at: str) -> list[list]:
    """The whole tab after adding `fresh`: header first, then one row per day, oldest first."""
    old_header = [str(cell) for cell in existing[0]] if existing else []
    columns = [c for c in old_header if c not in (DATE_COLUMN, UPDATED_COLUMN)]
    columns += [m for m in metrics if m not in columns]
    header = [DATE_COLUMN, *columns, UPDATED_COLUMN]

    rows: dict[str, dict] = {}
    for line, row in enumerate(existing[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue
        cells = dict(zip(old_header, row, strict=False))
        day = str(cells.get(DATE_COLUMN, "")).strip()
        try:
            date.fromisoformat(day)
        except ValueError:
            # Rewriting the tab without this row would lose it, so stop instead.
            raise PipelineError(
                f"Row {line} of the {tab} tab has a date the pipeline can't read ('{day}'). "
                "Fix or delete that row, then run again."
            ) from None
        rows[day] = cells

    for day, values in fresh.items():
        rows[day] = {**rows.get(day, {}), **values, DATE_COLUMN: day, UPDATED_COLUMN: updated_at}

    return [header] + [[rows[day].get(column, "") for column in header] for day in sorted(rows)]


def read_daily(store: Store, tab: str) -> list[list]:
    """The tab's rows (header first), numbers as numbers. Empty if the tab doesn't exist yet."""
    worksheet = store.find_tab(tab)
    if worksheet is None:
        return []
    return worksheet.get_all_values(
        value_render_option="UNFORMATTED_VALUE", date_time_render_option="FORMATTED_STRING"
    )


def write_daily(store: Store, tab: str, fresh: dict[str, dict], metrics: list[str], now: datetime) -> int:
    """Merge `fresh` into the tab. Returns how many days were written."""
    if not fresh:
        return 0
    worksheet = store.tab(tab, [DATE_COLUMN, *metrics, UPDATED_COLUMN])
    existing = read_daily(store, tab)
    table = merge(existing, fresh, metrics, tab, now.strftime("%Y-%m-%d %H:%M UTC"))

    # Grow the tab first if needed; Sheets refuses to write past its edge.
    if worksheet.row_count < len(table) or worksheet.col_count < len(table[0]):
        worksheet.resize(rows=max(worksheet.row_count, len(table)), cols=max(worksheet.col_count, len(table[0])))
    # Never cleared first: the new table only ever has more rows and columns than
    # the old one, so a failed write can't leave the tab emptier than it was.
    worksheet.update(table, "A1", value_input_option="USER_ENTERED")
    worksheet.format(f"A2:A{len(table)}", DATE_FORMAT)
    return len(fresh)
