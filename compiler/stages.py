"""Multi-stage Gemini generation pipeline for the AI Software Compiler."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from compiler._gemini import StructuredGenerationError, generate_structured
from compiler._runtime import get_runtime
from dsl import APISchema, AuthSchema, DatabaseSchema, UISchema


class RequirementsExtraction(BaseModel):
    """Structured requirements document produced from a natural-language prompt."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(
        description=(
            "One-paragraph summary of the application's primary purpose and target users."
        ),
    )
    functional_requirements: list[str] = Field(
        description=(
            "Discrete, testable functional requirements inferred from the prompt "
            "(e.g. 'Users can register with email and password')."
        ),
    )
    architectural_assumptions: list[str] = Field(
        description=(
            "Explicit technical assumptions the compiler should treat as fixed "
            "(e.g. 'PostgreSQL persistence', 'Role-based access control', 'Streamlit UI')."
        ),
    )
    entities: list[str] = Field(
        description=(
            "Core domain nouns/entities that likely become database tables "
            "(e.g. 'user', 'order', 'product')."
        ),
    )
    constraints: list[str] = Field(
        description=(
            "Non-functional constraints: security, scale, compliance, or UX limits "
            "stated or strongly implied by the prompt."
        ),
    )


class BackendGenerationResult(BaseModel):
    """Combined database and auth output for the backend generation stage."""

    model_config = ConfigDict(extra="forbid")

    database: DatabaseSchema = Field(
        description="Relational schema derived from requirements and domain entities.",
    )
    auth: AuthSchema = Field(
        description=(
            "Roles and permissions aligned with the database model and stated security needs."
        ),
    )


_REQUIREMENTS_SYSTEM = """\
You are Stage 1 (Requirements Extraction) of an AI Software Compiler.

Your job is to read a natural-language application request and produce a precise \
requirements document. Do not invent features unrelated to the prompt, but do infer \
reasonable defaults when the user omits implementation details (e.g. standard CRUD, login).

Always assume the target stack unless the user overrides it:
- Python backend with REST API
- Relational database (tables with snake_case names)
- Role-based authentication
- Streamlit frontend (Forms, Tables, Text, Buttons)

Be explicit in architectural_assumptions about anything you are inferring.
"""

_BACKEND_SYSTEM = """\
You are Stage 2 (Backend Schema Generation) of an AI Software Compiler.

Given structured requirements, produce:
1. database — Complete DatabaseSchema with tables, columns, types, primary keys, \
foreign keys, and nullability. Every entity listed in requirements should map to a table \
unless the app is truly stateless.
2. auth — Complete AuthSchema with at least one role. Include admin/user (or equivalent) \
when multi-user access is implied. default_role must match an existing role name. \
Permissions should use resource:action strings aligned with tables and operations.

Rules:
- Use snake_case for table and column names.
- Prefer UUID primary keys for user-facing entities; integers are acceptable for junction tables.
- Add created_at/updated_at datetime columns on major entities when temporal auditing is implied.
- Foreign keys must use format 'table_name.column_name'.
- Do not define API routes or UI components in this stage.
"""

_API_SYSTEM = """\
You are Stage 3 (API Schema Generation) of an AI Software Compiler.

Given requirements and a finalized DatabaseSchema, produce a complete APISchema.

Rules:
- Every table should have appropriate REST endpoints (list, get by id, create, update, delete) \
unless requirements explicitly exclude them.
- Paths must start with '/' and use plural resource names (e.g. '/users', '/users/{user_id}').
- request_schema and response_schema are JSON-Schema-like dicts keyed by field name; \
values describe type and constraints (e.g. {"type": "string"}).
- Map request/response fields to actual database columns where applicable.
- Include auth endpoints (register, login, me) when authentication is required.
- requires_auth and required_roles must be consistent with the auth roles from requirements context.
- Use only HttpMethod enum values: GET, POST, PUT, DELETE.
- Do not invent tables not present in the provided database schema.
"""

_UI_SYSTEM = """\
You are Stage 4 (UI Schema Generation) of an AI Software Compiler.

Given requirements and a finalized APISchema, produce a Streamlit-oriented UISchema.

Rules:
- Component types are strictly: Text, Form, Table, Button.
- Form, Table, and Button components MUST set api_endpoint_binding to an exact path from APISchema.
- Text components may omit api_endpoint_binding when displaying static content.
- payload_mapping links UI field ids to API request_schema keys for Forms and Buttons.
- Tables typically bind to GET list endpoints with empty payload_mapping.
- Provide sensible pages (home/dashboard, auth, resource management) and a nav_menu listing routes.
- Routes must start with '/' and be unique.
- Do not reference API paths that are not in the provided APISchema.
"""


def extract_requirements(prompt: str) -> dict:
    """Extract intent and explicit architectural assumptions from the raw user prompt."""
    model = get_runtime().model

    user_message = f"""{_REQUIREMENTS_SYSTEM}

--- USER PROMPT ---
{prompt.strip()}
"""

    try:
        result = generate_structured(
            model,
            prompt=user_message,
            response_schema=RequirementsExtraction,
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"Requirements extraction failed: {exc}"
        ) from exc

    return result.model_dump(mode="json")


def generate_backend(requirements: dict) -> tuple[DatabaseSchema, AuthSchema]:
    """Generate database and auth schemas from structured requirements."""
    model = get_runtime().model

    requirements_json = json.dumps(requirements, indent=2)
    user_message = f"""{_BACKEND_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}
"""

    try:
        result = generate_structured(
            model,
            prompt=user_message,
            response_schema=BackendGenerationResult,
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"Backend schema generation failed: {exc}"
        ) from exc

    return result.database, result.auth


def generate_api(requirements: dict, db_schema: DatabaseSchema) -> APISchema:
    """Generate API routes strictly mapped to the provided database schema."""
    model = get_runtime().model

    requirements_json = json.dumps(requirements, indent=2)
    database_json = db_schema.model_dump_json(indent=2)

    user_message = f"""{_API_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}

--- DATABASE SCHEMA (Stage 2 output) ---
{database_json}
"""

    try:
        return generate_structured(
            model,
            prompt=user_message,
            response_schema=APISchema,
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"API schema generation failed: {exc}"
        ) from exc


def generate_ui(requirements: dict, api_schema: APISchema) -> UISchema:
    """Generate Streamlit UI components bound to endpoints in the API schema."""
    model = get_runtime().model

    requirements_json = json.dumps(requirements, indent=2)
    api_json = api_schema.model_dump_json(indent=2)

    user_message = f"""{_UI_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}

--- API SCHEMA (Stage 3 output) ---
{api_json}
"""

    try:
        return generate_structured(
            model,
            prompt=user_message,
            response_schema=UISchema,
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"UI schema generation failed: {exc}"
        ) from exc
