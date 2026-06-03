"""Per-compilation runtime binding for stage functions."""

from __future__ import annotations

from dataclasses import dataclass

import google.generativeai as genai


@dataclass(frozen=True, slots=True)
class CompilerRuntime:
    """Holds the active GenerativeModel for the current compilation run."""

    model: genai.GenerativeModel


_runtime: CompilerRuntime | None = None


def bind_runtime(runtime: CompilerRuntime) -> None:
    """Attach a GenerativeModel for the duration of a compilation."""
    global _runtime
    _runtime = runtime


def clear_runtime() -> None:
    """Detach the active runtime after compilation completes."""
    global _runtime
    _runtime = None


def get_runtime() -> CompilerRuntime:
    if _runtime is None:
        raise RuntimeError(
            "Compiler runtime is not bound. Instantiate CompilerEngine and call "
            "run_compilation() instead of invoking stage functions directly."
        )
    return _runtime
