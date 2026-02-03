from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NucleusError(Exception):
    code: str
    message: str
    data: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ValidationError(NucleusError):
    pass


class PolicyDenied(NucleusError):
    pass


class ToolNotFound(NucleusError):
    pass


class ToolExecutionError(NucleusError):
    pass

