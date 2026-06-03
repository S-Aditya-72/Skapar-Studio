"""Shared Gemini structured-output utilities for the compiler pipeline."""

from __future__ import annotations

import json
from typing import TypeVar

import google.generativeai as genai
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredGenerationError(RuntimeError):
    """Raised when Gemini output cannot be parsed or validated against a schema."""


def generate_structured(
    model: genai.GenerativeModel,
    *,
    prompt: str,
    response_schema: type[T],
    temperature: float = 0.2,
) -> T:
    """Call Gemini with JSON mode and validate the response against a Pydantic model."""
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )

    raw_text = response.text
    if not raw_text:
        raise StructuredGenerationError("Gemini returned an empty response body.")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        # Phase 3: JSON repair engine will plug in here.
        raise StructuredGenerationError(
            f"Failed to parse Gemini JSON output: {exc}"
        ) from exc

    try:
        return response_schema.model_validate(payload)
    except ValidationError as exc:
        # Phase 3: schema repair / re-prompt will plug in here.
        raise StructuredGenerationError(
            f"Gemini output failed schema validation: {exc}"
        ) from exc
