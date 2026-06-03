"""Deterministic cross-layer validators for the AI Software Compiler DSL."""

from __future__ import annotations

import re

from dsl import APISchema, DatabaseSchema, UISchema
from dsl.api_schema import Endpoint
from dsl.ui_schema import Component, ComponentType

_PATH_PARAM_PATTERN = re.compile(r"^\{[a-zA-Z_][a-zA-Z0-9_]*\}$")

# Request/response fields commonly used by auth flows but not stored as columns.
_AUTH_OR_METADATA_FIELDS = frozenset({
    "email",
    "password",
    "username",
    "token",
    "access_token",
    "refresh_token",
    "confirm_password",
    "remember_me",
    "message",
    "detail",
    "error",
})

# Path prefixes that are not required to map to a database table.
_EXEMPT_PATH_PREFIXES = (
    "/auth",
    "/health",
    "/login",
    "/register",
    "/token",
    "/me",
)


class CrossLayerValidationError(Exception):
    """Raised when two DSL layers disagree in ways Pydantic alone cannot detect."""


def validate_ui_against_api(ui_schema: UISchema, api_schema: APISchema) -> None:
    """Ensure UI components only bind to endpoints that exist in the API schema."""
    endpoint_paths = {endpoint.path for endpoint in api_schema.endpoints}
    endpoints_by_path = {endpoint.path: endpoint for endpoint in api_schema.endpoints}

    page_routes = {page.route for page in ui_schema.pages}

    for route in ui_schema.nav_menu:
        if route not in page_routes:
            raise CrossLayerValidationError(
                f"nav_menu references route '{route}' which is not defined on any Page. "
                f"Defined routes: {sorted(page_routes)}"
            )

    for page in ui_schema.pages:
        for component in page.components:
            _validate_component_endpoint_binding(
                component,
                page_name=page.name,
                page_route=page.route,
                endpoint_paths=endpoint_paths,
                endpoints_by_path=endpoints_by_path,
            )


def _validate_component_endpoint_binding(
    component: Component,
    *,
    page_name: str,
    page_route: str,
    endpoint_paths: set[str],
    endpoints_by_path: dict[str, Endpoint],
) -> None:
    binding = component.api_endpoint_binding

    if component.type in {ComponentType.FORM, ComponentType.TABLE, ComponentType.BUTTON}:
        if not binding:
            raise CrossLayerValidationError(
                f"Component '{component.id}' (type={component.type.value}) on page "
                f"'{page_name}' (route {page_route}) must set api_endpoint_binding."
            )

    if binding is None:
        return

    if binding not in endpoint_paths:
        raise CrossLayerValidationError(
            f"Component '{component.id}' on page '{page_name}' (route {page_route}) "
            f"references missing API endpoint '{binding}'. "
            f"Available endpoint paths: {sorted(endpoint_paths)}"
        )

    endpoint = endpoints_by_path[binding]
    request_keys = set(endpoint.request_schema.keys()) if endpoint.request_schema else set()

    for ui_field, api_field in component.payload_mapping.items():
        if api_field not in request_keys:
            raise CrossLayerValidationError(
                f"Component '{component.id}' on page '{page_name}' maps UI field "
                f"'{ui_field}' to API key '{api_field}', but endpoint '{binding}' "
                f"request_schema keys are {sorted(request_keys) or '(empty)'}."
            )


def validate_api_against_db(api_schema: APISchema, db_schema: DatabaseSchema) -> None:
    """Sanity-check API endpoints against the database schema."""
    tables = {table.name: {column.name for column in table.columns} for table in db_schema.tables}
    all_columns: set[str] = set()
    for columns in tables.values():
        all_columns |= columns

    if not tables:
        return

    for endpoint in api_schema.endpoints:
        if _is_exempt_path(endpoint.path):
            continue

        resource = _resource_segment_from_path(endpoint.path)
        if resource is None:
            continue

        table_name = _resolve_table_name(resource, tables)
        if table_name is None:
            raise CrossLayerValidationError(
                f"Endpoint '{endpoint.method.value} {endpoint.path}' implies resource "
                f"'{resource}', but no matching table exists in DatabaseSchema. "
                f"Available tables: {sorted(tables)}"
            )

        table_columns = tables[table_name]
        _validate_schema_fields_against_table(
            endpoint=endpoint,
            field_source="request_schema",
            fields=endpoint.request_schema,
            table_name=table_name,
            table_columns=table_columns,
            all_columns=all_columns,
        )
        _validate_schema_fields_against_table(
            endpoint=endpoint,
            field_source="response_schema",
            fields=endpoint.response_schema,
            table_name=table_name,
            table_columns=table_columns,
            all_columns=all_columns,
        )


def _is_exempt_path(path: str) -> bool:
    normalized = path.rstrip("/") or path
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in _EXEMPT_PATH_PREFIXES
    )


def _resource_segment_from_path(path: str) -> str | None:
    """Return the first non-parameter path segment (e.g. '/users/{id}' -> 'users')."""
    segments = [segment for segment in path.strip("/").split("/") if segment]
    for segment in segments:
        if not _PATH_PARAM_PATTERN.match(segment):
            return segment
    return None


def _resolve_table_name(resource: str, tables: dict[str, set[str]]) -> str | None:
    """Map a URL resource segment to a database table name when possible."""
    if resource in tables:
        return resource

    if resource.endswith("ies"):
        singular = f"{resource[:-3]}y"
        if singular in tables:
            return singular

    if resource.endswith("es"):
        singular = resource[:-2]
        if singular in tables:
            return singular

    if resource.endswith("s"):
        singular = resource[:-1]
        if singular in tables:
            return singular

    return None


def _validate_schema_fields_against_table(
    *,
    endpoint: Endpoint,
    field_source: str,
    fields: dict[str, object],
    table_name: str,
    table_columns: set[str],
    all_columns: set[str],
) -> None:
    if not fields:
        return

    for field_name in fields:
        if field_name in table_columns or field_name in _AUTH_OR_METADATA_FIELDS:
            continue

        if field_name in all_columns:
            # Field exists on another table — allowed for joins/aggregates but flagged only
            # when it is completely unknown across the schema.
            continue

        raise CrossLayerValidationError(
            f"Endpoint '{endpoint.method.value} {endpoint.path}' {field_source} defines "
            f"field '{field_name}' which does not match any column on table '{table_name}' "
            f"(columns: {sorted(table_columns)}) or known auth/metadata fields."
        )