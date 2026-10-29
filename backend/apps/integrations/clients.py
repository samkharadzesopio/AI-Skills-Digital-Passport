
from .repositories import MockClassroomRepository


class MockBTUClassroomClient:
    """
    SIMULATED BTU Classroom integration.
    Does not connect to the real BTU Classroom API.
    """

    def __init__(self, repository=None):
        self.repository = repository or MockClassroomRepository()

    def fetch_completions(self):
        return self.repository.get_completions()
