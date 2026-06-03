"""Multi-stage Gemini generation pipeline for the AI Software Compiler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from compiler._gemini import StructuredGenerationError, generate_structured
from compiler._runtime import get_runtime
from dsl import APISchema, AuthSchema, DatabaseSchema, RequirementsSchema, UISchema
from compiler.schema_helpers import get_gemini_schema


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
RequirementsSchema. Do not invent features unrelated to the prompt, but do infer \
reasonable defaults when the user omits implementation details (e.g. standard CRUD, login).

Populate:
- features: testable functional capabilities
- entities: domain nouns that become tables/resources (singular snake_case)
- assumptions: stack and architecture choices (Python REST API, SQLite, Streamlit UI, RBAC)

Always assume unless overridden:
- Python backend with REST API
- Relational database (tables with snake_case names)
- Role-based authentication
- Streamlit frontend (Forms, Tables, Text, Buttons)
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
- request_schema and response_schema are lists of SchemaField objects with field_name and field_type.
- field_type must be one of: string, integer, number, boolean, array, object.
- Use null for request_schema or response_schema when no fields apply.
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
- payload_mapping is a list of PayloadMapping objects (ui_input_name, api_field_name) for Forms and Buttons.
- Use null for payload_mapping when no request body is sent (e.g. Table components).
- Tables typically bind to GET list endpoints with null payload_mapping.
- Provide sensible pages (home/dashboard, auth, resource management) and a nav_menu listing routes.
- Routes must start with '/' and be unique.
- Do not reference API paths that are not in the provided APISchema.
"""


def extract_requirements(prompt: str) -> RequirementsSchema:
    """Extract structured requirements from the raw user prompt."""
    runtime = get_runtime()

    user_message = f"""{_REQUIREMENTS_SYSTEM}

--- USER PROMPT ---
{prompt.strip()}
"""

    try:
        return generate_structured(
            runtime.client,
            model=runtime.model_name,
            prompt=user_message,
            response_schema=get_gemini_schema(RequirementsSchema),
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"Requirements extraction failed: {exc}"
        ) from exc


def generate_backend(requirements: RequirementsSchema) -> tuple[DatabaseSchema, AuthSchema]:
    """Generate database and auth schemas from structured requirements."""
    runtime = get_runtime()

    requirements_json = requirements.model_dump_json(indent=2)
    user_message = f"""{_BACKEND_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}
"""

    try:
        result = generate_structured(
            runtime.client,
            model=runtime.model_name,
            prompt=user_message,
            response_schema=get_gemini_schema(BackendGenerationResult),
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"Backend schema generation failed: {exc}"
        ) from exc

    return result.database, result.auth


def generate_api(requirements: RequirementsSchema, db_schema: DatabaseSchema) -> APISchema:
    """Generate API routes strictly mapped to the provided database schema."""
    runtime = get_runtime()

    requirements_json = requirements.model_dump_json(indent=2)
    database_json = db_schema.model_dump_json(indent=2)

    user_message = f"""{_API_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}

--- DATABASE SCHEMA (Stage 2 output) ---
{database_json}
"""

    try:
        return generate_structured(
            runtime.client,
            model=runtime.model_name,
            prompt=user_message,
            response_schema=get_gemini_schema(APISchema),
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"API schema generation failed: {exc}"
        ) from exc


def generate_ui(requirements: RequirementsSchema, api_schema: APISchema) -> UISchema:
    """Generate Streamlit UI components bound to endpoints in the API schema."""
    runtime = get_runtime()

    requirements_json = requirements.model_dump_json(indent=2)
    api_json = api_schema.model_dump_json(indent=2)

    user_message = f"""{_UI_SYSTEM}

--- REQUIREMENTS (Stage 1 output) ---
{requirements_json}

--- API SCHEMA (Stage 3 output) ---
{api_json}
"""

    try:
        return generate_structured(
            runtime.client,
            model=runtime.model_name,
            prompt=user_message,
            response_schema=get_gemini_schema(UISchema),
        )
    except StructuredGenerationError:
        raise
    except Exception as exc:
        raise StructuredGenerationError(
            f"UI schema generation failed: {exc}"
        ) from exc
