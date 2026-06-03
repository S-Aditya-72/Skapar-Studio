"""Top-level compilation orchestrator for the AI Software Compiler."""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from typing import TypeVar

import google.generativeai as genai
from pydantic import BaseModel, ValidationError

from compiler._gemini import StructuredGenerationError
from compiler._runtime import CompilerRuntime, bind_runtime, clear_runtime
from compiler.repair import repair_json
from compiler.stages import (
    BackendGenerationResult,
    RequirementsExtraction,
    extract_requirements,
    generate_api,
    generate_backend,
    generate_ui,
)
from compiler.validators import CrossLayerValidationError, validate_api_against_db, validate_ui_against_api
from dsl import APISchema, MasterAppSchema, UISchema

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"

T = TypeVar("T", bound=BaseModel)


class CompilationError(RuntimeError):
    """Raised when any pipeline stage fails after exhausting repair retries."""


class CompilerEngine:
    """Executes the multi-stage Gemini pipeline and returns a validated MasterAppSchema."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MODEL,
        max_retries: int = 3,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("A non-empty Gemini API key is required.")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        genai.configure(api_key=api_key.strip())
        self._model_name = model_name
        self._model = genai.GenerativeModel(model_name)
        self._max_retries = max_retries

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def max_retries(self) -> int:
        return self._max_retries

    def run_compilation(self, user_prompt: str) -> MasterAppSchema:
        """Run all compilation stages sequentially with validation and repair."""
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt must be a non-empty string.")

        bind_runtime(CompilerRuntime(model=self._model))
        try:
            return self._execute_pipeline(user_prompt.strip())
        finally:
            clear_runtime()

    def _execute_pipeline(self, user_prompt: str) -> MasterAppSchema:
        logger.info("Stage 1/4: extracting requirements")
        requirements_model = self._run_stage_with_repair(
            stage_label="Requirements Schema",
            target_model=RequirementsExtraction,
            generate_fn=lambda: RequirementsExtraction.model_validate(
                extract_requirements(user_prompt)
            ),
            validate_fn=None,
            context_fn=lambda: f"Original user prompt:\n{user_prompt}",
            initial_json_fn=lambda: "{}",
        )
        requirements = requirements_model.model_dump(mode="json")

        logger.info("Stage 2/4: generating database and auth schemas")
        backend_result = self._generate_backend_with_repair(requirements)
        db_schema = backend_result.database
        auth_schema = backend_result.auth

        logger.info("Stage 3/4: generating API schema")
        api_schema = self._run_stage_with_repair(
            stage_label="API Schema",
            target_model=APISchema,
            generate_fn=lambda: generate_api(requirements, db_schema),
            validate_fn=lambda schema: validate_api_against_db(schema, db_schema),
            context_fn=lambda: db_schema.model_dump_json(indent=2),
            initial_json_fn=lambda: "{}",
        )

        logger.info("Stage 4/4: generating UI schema")
        ui_schema = self._run_stage_with_repair(
            stage_label="UI Schema",
            target_model=UISchema,
            generate_fn=lambda: generate_ui(requirements, api_schema),
            validate_fn=lambda schema: validate_ui_against_api(schema, api_schema),
            context_fn=lambda: api_schema.model_dump_json(indent=2),
            initial_json_fn=lambda: "{}",
        )

        master = MasterAppSchema(
            database=db_schema,
            auth=auth_schema,
            api=api_schema,
            ui=ui_schema,
        )

        logger.info("Compilation complete; MasterAppSchema assembled")
        return master

    def _generate_backend_with_repair(self, requirements: dict) -> BackendGenerationResult:
        """Generate database and auth schemas with repair on validation failure."""

        def _generate() -> BackendGenerationResult:
            database, auth = generate_backend(requirements)
            return BackendGenerationResult(database=database, auth=auth)

        return self._run_stage_with_repair(
            stage_label="Backend Schema",
            target_model=BackendGenerationResult,
            generate_fn=_generate,
            validate_fn=None,
            context_fn=lambda: json.dumps(requirements, indent=2),
            initial_json_fn=lambda: "{}",
        )

    def _run_stage_with_repair(
        self,
        *,
        stage_label: str,
        target_model: type[T],
        generate_fn: Callable[[], T],
        validate_fn: Callable[[T], None] | None,
        context_fn: Callable[[], str],
        initial_json_fn: Callable[[], str],
    ) -> T:
        """Run a stage, validate, and repair up to max_retries times on failure."""
        bad_json = initial_json_fn()
        result: T | None = None
        last_error_trace = ""

        for attempt in range(self._max_retries + 1):
            try:
                if attempt == 0:
                    result = generate_fn()
                else:
                    result = repair_json(
                        bad_json=bad_json,
                        error_trace=last_error_trace,
                        target_model=target_model,
                        context_str=context_fn(),
                    )

                if validate_fn is not None and result is not None:
                    validate_fn(result)

                return result

            except (ValidationError, CrossLayerValidationError) as exc:
                last_error_trace = traceback.format_exc()
                bad_json = self._serialize_for_repair(result, bad_json)

                if attempt >= self._max_retries:
                    logger.exception(
                        "Stage '%s' failed after %s retries",
                        stage_label,
                        self._max_retries,
                    )
                    raise CompilationError(
                        f"Stage '{stage_label}' failed after {self._max_retries} repair "
                        f"attempts. Last error:\n{last_error_trace}"
                    ) from exc

                print(
                    f"Repairing {stage_label}... Retry {attempt + 1}/{self._max_retries}. "
                    f"Error: {exc}"
                )

            except StructuredGenerationError as exc:
                last_error_trace = traceback.format_exc()
                if exc.raw_text:
                    bad_json = exc.raw_text
                else:
                    bad_json = self._serialize_for_repair(result, bad_json)

                if attempt >= self._max_retries:
                    raise CompilationError(
                        f"Stage '{stage_label}' failed structured generation after "
                        f"{self._max_retries} repair attempts: {exc}"
                    ) from exc

                print(
                    f"Repairing {stage_label}... Retry {attempt + 1}/{self._max_retries}. "
                    f"Error: {exc}"
                )

            except json.JSONDecodeError as exc:
                last_error_trace = traceback.format_exc()

                if attempt >= self._max_retries:
                    raise CompilationError(
                        f"Stage '{stage_label}' produced invalid JSON after "
                        f"{self._max_retries} repair attempts: {exc}"
                    ) from exc

                print(
                    f"Repairing {stage_label}... Retry {attempt + 1}/{self._max_retries}. "
                    f"Error: {exc}"
                )

        raise CompilationError(f"Stage '{stage_label}' failed unexpectedly.")

    @staticmethod
    def _serialize_for_repair(result: BaseModel | None, fallback_json: str) -> str:
        if result is not None:
            return result.model_dump_json(indent=2)
        return fallback_json
