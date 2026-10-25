
from datetime import datetime, timezone
from uuid import uuid4

from .service import ALLOWED_SOURCES


class InMemoryImportAudit:
    """
    Development-only import audit store.

    Records disappear after process restart.
    Not suitable as a production audit log.
    """

    def __init__(self):
        self._records = []

    def record(self, source, result):
        if source not in ALLOWED_SOURCES:
            raise ValueError("Unsupported import source")

        required = (
            "processed",
            "awarded",
            "skipped",
            "failed",
            "errors",
        )

        if not isinstance(result, dict):
            raise ValueError("Invalid import result")

        if any(key not in result for key in required):
            raise ValueError("Missing import statistics")

        for field in required[:-1]:
            value = result[field]
            if type(value) is not int or value < 0:
                raise ValueError(
                    f"Invalid statistic: {field}"
                )

        if not isinstance(result["errors"], list):
            raise ValueError("Invalid error list")

        # Do not store raw spreadsheet rows or
        # student personal data in the audit log.
        if result["failed"] == 0:
            status = "COMPLETED"
        elif (
            result["awarded"] > 0
            or result["skipped"] > 0
        ):
            status = "PARTIAL"
        else:
            status = "FAILED"

        entry = {
            "id": str(uuid4()),
            "source": source,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "status": status,
            "processed": result["processed"],
            "awarded": result["awarded"],
            "skipped": result["skipped"],
            "failed": result["failed"],
            "error_count": len(result["errors"]),
        }

        self._records.append(entry)
        return entry.copy()

    def list_history(self):
        return [
            entry.copy()
            for entry in reversed(self._records)
        ]
