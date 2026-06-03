"""AI Software Compiler DSL — Pydantic contracts for LLM-structured app generation.

Import root schemas from this package:

    from dsl import MasterAppSchema, DatabaseSchema, AuthSchema, APISchema, UISchema
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dsl.api_schema import APISchema
from dsl.auth_schema import AuthSchema
from dsl.db_schema import DatabaseSchema
from dsl.ui_schema import UISchema

__all__ = [
    "APISchema",
    "AuthSchema",
    "DatabaseSchema",
    "MasterAppSchema",
    "UISchema",
]


class MasterAppSchema(BaseModel):
    """Single root contract combining database, auth, API, and UI definitions.

    This is the top-level JSON document Gemini should emit. The compiler
    validates and consumes each subsection independently while ensuring
    cross-references (roles, paths, foreign keys) stay consistent.
    """

    model_config = ConfigDict(extra="forbid")

    database: DatabaseSchema = Field(
        description=(
            "Relational data model: tables, columns, types, and foreign keys. "
            "Drives migrations, ORM entities, and repository layers."
        ),
    )
    auth: AuthSchema = Field(
        description=(
            "Roles, permissions, and default role for new users. "
            "Must align with APISchema Endpoint.required_roles."
        ),
    )
    api: APISchema = Field(
        description=(
            "REST API surface: paths, methods, auth, and request/response JSON shapes. "
            "Referenced by UISchema Component.api_endpoint_binding."
        ),
    )
    ui: UISchema = Field(
        description=(
            "Streamlit UI: pages, navigation, and components bound to API endpoints. "
            "Completes the end-to-end application contract."
        ),
    )
