from ulid import ULID


class UlidIdGenerator:
    def _ulid(self) -> str:
        return str(ULID())

    def session_id(self) -> str:
        return f"ses_{self._ulid()}"

    def shot_id(self) -> str:
        return f"shot_{self._ulid()}"

    def export_id(self) -> str:
        return f"exp_{self._ulid()}"
