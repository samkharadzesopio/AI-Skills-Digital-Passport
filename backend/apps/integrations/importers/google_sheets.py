
import re

from .validators import (
    ImportValidationError,
    REQUIRED_FIELDS,
    validate_completion_record,
)

MAX_ROWS = 5000


def read_google_sheet(
    spreadsheet_id,
    worksheet_name="Completions",
    client=None,
):
    """
    Read a trusted Google Sheet.

    Returns:
        (valid_records, errors)

    A client may be injected for testing.
    """

    if not isinstance(spreadsheet_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{10,200}", spreadsheet_id
    ):
        raise ImportValidationError(
            "Invalid spreadsheet ID"
        )

    if client is None:
        from django.conf import settings
        import gspread

        credentials_path = getattr(
            settings,
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            None,
        )

        if not credentials_path:
            raise ImportValidationError(
                "Google Sheets credentials not configured"
            )

        client = gspread.service_account(filename=credentials_path, scopes=[
            'https://www.googleapis.com/auth/spreadsheets.readonly',
        ])
        client.set_timeout(10)

    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)

    # Bounded range prevents unlimited imports.
    rows = worksheet.get("A1:Z5002")

    if not rows:
        raise ImportValidationError(
            "Google Sheet is empty"
        )

    if any(sum(len(str(cell)) for cell in row) > 16384 for row in rows):
        raise ImportValidationError('Sheet row exceeds processing limit')
    headers = [
        str(value).strip()
        for value in rows[0]
    ]

    if len(headers) != len(set(headers)):
        raise ImportValidationError(
            "Duplicate column names"
        )

    missing = set(REQUIRED_FIELDS) - set(headers)

    if missing:
        raise ImportValidationError(
            "Missing columns: " + ", ".join(sorted(missing))
        )

    if len(rows) - 1 > MAX_ROWS:
        raise ImportValidationError(
            "Google Sheet exceeds 5000 rows"
        )

    valid_records = []
    errors = []

    for row_number, values in enumerate(
        rows[1:], start=2
    ):
        if not any(str(v).strip() for v in values):
            continue

        record = dict(
            zip(
                headers,
                list(values) + [""] * (
                    len(headers) - len(values)
                ),
            )
        )

        # Google Sheets returns cell values as strings.
        if "grade" in record:
            try:
                record["grade"] = float(
                    record["grade"]
                )
            except (TypeError, ValueError):
                pass

        if "passed" in record:
            value = str(record["passed"]).strip().lower()
            if value == "true":
                record["passed"] = True
            elif value == "false":
                record["passed"] = False

        try:
            validated = validate_completion_record(
                record
            )
            valid_records.append(validated)

        except (ImportValidationError, ValueError) as exc:
            errors.append({
                "row": row_number,
                "error": str(exc),
            })

    return valid_records, errors
