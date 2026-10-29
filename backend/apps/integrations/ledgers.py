
class InMemorySyncLedger:
    """
    TEST-ONLY synchronization ledger.

    Never use this for persistent or concurrent
    production synchronization.
    """

    def __init__(self):
        self.processed_events = set()

    def is_processed(self, event_id):
        return event_id in self.processed_events

    def mark_processed(self, event_id):
        self.processed_events.add(event_id)
