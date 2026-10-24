
import json
from pathlib import Path


class MockDocumentRepository:
    """
    Simulated trusted issued-document registry.
    This is NOT an official BTU credential database.
    """

    def __init__(self, data_path=None):
        self.data_path = (
            Path(data_path)
            if data_path is not None
            else Path(__file__).resolve().parent
            / "mock_data"
            / "issued_documents.json"
        )

    def _load(self):
        with self.data_path.open(
            "r", encoding="utf-8"
        ) as file:
            return json.load(file)

    def find_by_hash(self, pdf_hash):
        data = self._load()

        for document in data["documents"]:
            if document["pdf_sha256"] == pdf_hash:
                return document

        return None

    def get_passport(self, passport_id):
        data = self._load()

        for passport in data["passports"]:
            if passport["passport_id"] == passport_id:
                return passport

        return None
