"""Gemini-powered repair agent for invalid or cross-layer-inconsistent DSL JSON."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from compiler._gemini import generate_structured
from compiler._runtime import get_runtime
from compiler.schema_helpers import get_gemini_schema

T = TypeVar("T", bound=BaseModel)

_REPAIR_PROMPT_TEMPLATE = """\
You are a compiler repair agent. The previous stage generated this JSON: {bad_json}. \
It failed validation with this exact Python error: {error_trace}. \
Context from other layers: {context_str}. \
Fix the JSON to resolve the error. Do not change anything that isn't broken. \
Output valid JSON matching the schema.
"""


def repair_json(
    bad_json: str,
    error_trace: str,
    target_model: type[T],
    context_str: str = "",
) -> T:
    """Ask Gemini to minimally repair JSON so it validates against target_model."""
    runtime = get_runtime()

    prompt = _REPAIR_PROMPT_TEMPLATE.format(
        bad_json=bad_json,
        error_trace=error_trace,
        context_str=context_str or "(none)",
    )

    return generate_structured(
        runtime.client,
        model=runtime.model_name,
        prompt=prompt,
        response_schema=get_gemini_schema(target_model),
        temperature=0.1,
    )
