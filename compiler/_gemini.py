"""Shared Gemini structured-output utilities for the compiler pipeline."""

from __future__ import annotations

import json
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredGenerationError(RuntimeError):
    """Raised when Gemini output cannot be parsed as JSON."""

    def __init__(self, message: str, *, raw_text: str | None = None) -> None:
        super().__init__(message)
        self.raw_text = raw_text


def generate_structured(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    response_schema: type[T],
    temperature: float = 0.2,
) -> T:
    """Call Gemini with JSON mode and validate the response against a Pydantic model."""
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )

    raw_text = response.text
    if not raw_text:
        raise StructuredGenerationError(
            "Gemini returned an empty response body.")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise StructuredGenerationError(
            f"Failed to parse Gemini JSON output: {exc}",
            raw_text=raw_text,
        ) from exc

    return response_schema.model_validate(payload)
