"""Top-level compilation orchestrator for the AI Software Compiler."""

from __future__ import annotations

import json
import logging

import google.generativeai as genai

from compiler._gemini import StructuredGenerationError
from compiler._runtime import CompilerRuntime, bind_runtime, clear_runtime
from compiler.stages import (
    extract_requirements,
    generate_api,
    generate_backend,
    generate_ui,
)
from dsl import MasterAppSchema

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


class CompilationError(RuntimeError):
    """Raised when any pipeline stage fails."""


class CompilerEngine:
    """Executes the multi-stage Gemini pipeline and returns a validated MasterAppSchema."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("A non-empty Gemini API key is required.")

        genai.configure(api_key=api_key.strip())
        self._model_name = model_name
        self._model = genai.GenerativeModel(model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def run_compilation(self, user_prompt: str) -> MasterAppSchema:
        """Run all compilation stages sequentially with context carry-over."""
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt must be a non-empty string.")

        bind_runtime(CompilerRuntime(model=self._model))
        try:
            return self._execute_pipeline(user_prompt.strip())
        finally:
            clear_runtime()

    def _execute_pipeline(self, user_prompt: str) -> MasterAppSchema:
        logger.info("Stage 1/4: extracting requirements")
        requirements = self._run_stage(
            "requirements",
            lambda: extract_requirements(user_prompt),
        )

        logger.info("Stage 2/4: generating database and auth schemas")
        db_schema, auth_schema = self._run_stage(
            "backend",
            lambda: generate_backend(requirements),
        )

        logger.info("Stage 3/4: generating API schema")
        api_schema = self._run_stage(
            "api",
            lambda: generate_api(requirements, db_schema),
        )

        logger.info("Stage 4/4: generating UI schema")
        ui_schema = self._run_stage(
            "ui",
            lambda: generate_ui(requirements, api_schema),
        )

        master = MasterAppSchema(
            database=db_schema,
            auth=auth_schema,
            api=api_schema,
            ui=ui_schema,
        )

        logger.info("Compilation complete; validating MasterAppSchema")
        return master

    @staticmethod
    def _run_stage(stage_name: str, stage_fn):
        """Execute a stage with placeholder JSON/schema error handling (Phase 3)."""
        try:
            return stage_fn()
        except json.JSONDecodeError as exc:
            # Phase 3: JSON repair engine
            logger.exception("JSON decode error in stage %s", stage_name)
            raise CompilationError(
                f"Stage '{stage_name}' produced invalid JSON: {exc}"
            ) from exc
        except StructuredGenerationError as exc:
            # Phase 3: structured output repair / retry
            logger.exception("Structured generation error in stage %s", stage_name)
            raise CompilationError(
                f"Stage '{stage_name}' failed structured generation: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error in stage %s", stage_name)
            raise CompilationError(
                f"Stage '{stage_name}' failed unexpectedly: {exc}"
            ) from exc
