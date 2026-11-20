"""OMR engines TransNote can drive."""

from .base import Engine, EngineError, EngineNotFound, EngineResult
from .homr import HomrEngine
from .audiveris import AudiverisEngine

ENGINES: dict[str, type[Engine]] = {
    "homr": HomrEngine,
    "audiveris": AudiverisEngine,
}


def get_engine(name: str) -> Engine:
    try:
        return ENGINES[name]()
    except KeyError:
        raise ValueError(f"Unknown engine {name!r}. Choose from: {', '.join(ENGINES)}") from None


__all__ = ["ENGINES", "Engine", "EngineError", "EngineNotFound", "EngineResult", "get_engine"]
