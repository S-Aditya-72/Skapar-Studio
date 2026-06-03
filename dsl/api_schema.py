"""HTTP API contract for the AI Software Compiler DSL.

Defines REST endpoints, methods, auth requirements, and JSON payload shapes
that the compiler uses to generate route handlers and client bindings.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class HttpMethod(str, Enum):
    """HTTP verbs supported for generated API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class Endpoint(BaseModel):
    """A single REST API route with method, auth rules, and request/response shapes."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        description=(
            "URL path template starting with '/' (e.g. '/users', '/orders/{order_id}'). "
            "Path parameters use curly-brace notation and must be reflected in request_schema "
            "when applicable."
        ),
    )
    method: HttpMethod = Field(
        description=(
            "HTTP method for this endpoint. GET for reads, POST for creates, "
            "PUT for full updates, DELETE for removals."
        ),
    )
    description: str = Field(
        description=(
            "Clear summary of what this endpoint does, its side effects, and when "
            "the UI or other clients should call it. Used in OpenAPI-style generated docs."
        ),
    )
    requires_auth: bool = Field(
        description=(
            "True if the caller must present a valid authenticated session or token "
            "before the handler runs. False for public endpoints (e.g. health, login)."
        ),
    )
    required_roles: list[str] = Field(
        description=(
            "Role names from auth_schema that may access this endpoint when requires_auth "
            "is True. Empty list with requires_auth=True typically means any authenticated user. "
            "Ignored or treated as open when requires_auth is False."
        ),
    )
    request_schema: dict[str, object] = Field(
        description=(
            "JSON Schema-like dictionary describing the request body or query parameters. "
            "Keys are field names; values describe type, required flags, and constraints "
            "(e.g. {'email': {'type': 'string', 'format': 'email'}, 'age': {'type': 'integer'}}). "
            "Use an empty object {} when the endpoint accepts no structured input."
        ),
    )
    response_schema: dict[str, object] = Field(
        description=(
            "JSON Schema-like dictionary describing the successful response payload shape. "
            "Mirrors request_schema conventions. Use an empty object {} for endpoints "
            "that return no body (e.g. 204 DELETE) or only status metadata."
        ),
    )


class APISchema(BaseModel):
    """Root API contract: all HTTP endpoints exposed by the generated backend."""

    model_config = ConfigDict(extra="forbid")

    endpoints: list[Endpoint] = Field(
        description=(
            "Complete list of REST endpoints. Each path+method pair should be unique. "
            "Paths referenced by ui_schema Component.api_endpoint_binding must exist here."
        ),
    )
