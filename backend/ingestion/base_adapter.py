from abc import ABC, abstractmethod


class BaseAdapter(ABC):

    @abstractmethod
    def fetch(self, page: int = 0) -> list[dict]:
        """Fetch a page of raw records from the source API."""

    @abstractmethod
    def normalize(self, raw: dict) -> dict | None:
        """Convert a raw source record into the Master Universal Schema.
        Return None to skip the record (missing required fields, bad license, etc.)
        """

    def paginate(self, max_pages: int = 100) -> list[dict]:
        """Iterate pages until empty or max_pages reached. Returns all normalized records."""
        results = []
        for page in range(max_pages):
            raw_records = self.fetch(page)
            if not raw_records:
                break
            for raw in raw_records:
                normalized = self.normalize(raw)
                if normalized:
                    results.append(normalized)
        return results
