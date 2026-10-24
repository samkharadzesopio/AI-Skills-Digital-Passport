
import json
from pathlib import Path


class MockCredentialRepository:
    def __init__(self, data_path=None):
        self.data_path = (
            Path(data_path)
            if data_path is not None
            else Path(__file__).resolve().parent
            / "mock_data"
            / "credentials.json"
        )

    def get_by_id(self, credential_id):
        with self.data_path.open(
            "r", encoding="utf-8"
        ) as file:
            records = json.load(file)

        for record in records:
            if record["credential_id"] == credential_id:
                return record

        return None
