"""An in-memory stand-in for the master Google Sheet.

Used by the tests and by the local dev server (scripts/dev_api.py), so neither
ever touches the real sheet. It mimics just the parts of gspread the store uses.
"""

import gspread


class FakeWorksheet:
    """Just enough of gspread's Worksheet for the store. Cells come back as strings, like Sheets."""

    def __init__(self, title: str, sheet_id: int):
        self.title = title
        self.id = sheet_id
        self.rows: list[list[str]] = []

    def get_all_values(self) -> list[list[str]]:
        return [list(row) for row in self.rows]

    def append_row(self, row: list) -> None:
        self.rows.append([str(value) for value in row])

    def clear(self) -> None:
        self.rows = []

    def update(self, values: list[list], range_name: str) -> None:
        first = int(range_name.removeprefix("A")) - 1
        for offset, row in enumerate(values):
            while len(self.rows) <= first + offset:
                self.rows.append([])
            self.rows[first + offset] = [str(value) for value in row]


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
        self.worksheets[title] = FakeWorksheet(title, sheet_id=len(self.worksheets) + 1)
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
