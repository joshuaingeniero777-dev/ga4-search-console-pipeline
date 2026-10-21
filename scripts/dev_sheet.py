"""An in-memory stand-in for the master Google Sheet.

Used by the tests and by the local dev server (scripts/dev_api.py), so neither
ever touches the real sheet. It mimics just the parts of gspread the store uses.
"""

import gspread


class FakeWorksheet:
    """Just enough of gspread's Worksheet for the pipeline.

    Like Sheets: values read back as text unless asked for "unformatted", and
    writing past the tab's edge is refused until it's resized.
    """

    def __init__(self, title: str, sheet_id: int, rows: int = 1000, cols: int = 26):
        self.title = title
        self.id = sheet_id
        self.row_count = rows
        self.col_count = cols
        self.rows: list[list] = []
        self.formats: list[tuple[str, dict]] = []

    def get_all_values(self, value_render_option: str | None = None, **_) -> list[list]:
        if value_render_option == "UNFORMATTED_VALUE":
            return [list(row) for row in self.rows]
        return [[str(value) for value in row] for row in self.rows]

    def append_row(self, row: list) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows = []

    def update(self, values: list[list], range_name: str, value_input_option: str | None = None) -> None:
        first = int(range_name.removeprefix("A")) - 1
        widest = max((len(row) for row in values), default=0)
        if first + len(values) > self.row_count or widest > self.col_count:
            raise gspread.exceptions.APIError(
                {"code": 400, "message": f"Range exceeds grid limits of {self.title}", "status": "INVALID_ARGUMENT"}
            )
        for offset, row in enumerate(values):
            while len(self.rows) <= first + offset:
                self.rows.append([])
            self.rows[first + offset] = list(row)

    def resize(self, rows: int | None = None, cols: int | None = None) -> None:
        self.row_count = rows or self.row_count
        self.col_count = cols or self.col_count

    def format(self, range_name: str, cell_format: dict) -> None:
        self.formats.append((range_name, cell_format))


class FakeSpreadsheet:
    def __init__(self):
        self.worksheets: dict[str, FakeWorksheet] = {}
        self.batch_requests: list[dict] = []
        self.protections: list[dict] = []  # what the real sheet reports as protectedRanges
        self.metadata_fetches = 0

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self.worksheets:
            raise gspread.WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        self.worksheets[title] = FakeWorksheet(title, sheet_id=len(self.worksheets) + 1, rows=rows, cols=cols)
        return self.worksheets[title]

    def batch_update(self, body: dict) -> None:
        self.batch_requests.append(body)
        for request in body["requests"]:
            if "addProtectedRange" in request:
                self.protections.append(request["addProtectedRange"]["protectedRange"])

    def fetch_sheet_metadata(self, params: dict | None = None) -> dict:
        self.metadata_fetches += 1
        return {
            "sheets": [
                {
                    "properties": {"sheetId": worksheet.id},
                    "protectedRanges": [
                        p for p in self.protections if p["range"].get("sheetId", 0) == worksheet.id
                    ],
                }
                for worksheet in self.worksheets.values()
            ]
        }
