
import json
from pathlib import Path


class MockClassroomRepository:
    def __init__(self):
        self.data_path = (
            Path(__file__).resolve().parent
            / "mock_data"
            / "completions.json"
        )

    def get_completions(self):
        with self.data_path.open("r", encoding="utf-8") as file:
            return json.load(file)


import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "mock_data"


class MockClassroomRepository:
    def __init__(self):
        self.data_path = DATA_DIR / "completions.json"

    def get_completions(self):
        with self.data_path.open("r", encoding="utf-8") as file:
            return json.load(file)


class ApprovedAICourseRepository:
    def __init__(self):
        self.data_path = DATA_DIR / "approved_ai_courses.json"

    def get_approved_courses(self):
        with self.data_path.open("r", encoding="utf-8") as file:
            return json.load(file)
