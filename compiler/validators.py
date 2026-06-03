"""Deterministic cross-layer validators for the AI Software Compiler DSL."""

from __future__ import annotations

import re

from dsl import APISchema, DatabaseSchema, UISchema
from dsl.api_schema import Endpoint, HttpMethod, SchemaField
from dsl.schema_helpers import payload_api_field_names, schema_field_names
from dsl.ui_schema import Component, ComponentType

_PATH_PARAM_PATTERN = re.compile(r"^\{[a-zA-Z_][a-zA-Z0-9_]*\}$")

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

_EXEMPT_PATH_PREFIXES = (
    "/auth",
    "/health",
    "/login",
    "/register",
    "/token",
    "/me",
)

_COMPONENT_METHOD_PRIORITY: dict[ComponentType, tuple[HttpMethod, ...]] = {
    ComponentType.TABLE: (HttpMethod.GET,),
    ComponentType.FORM: (HttpMethod.POST, HttpMethod.PUT),
    ComponentType.BUTTON: (HttpMethod.POST, HttpMethod.DELETE, HttpMethod.PUT),
    ComponentType.TEXT: (HttpMethod.GET,),
}


class CrossLayerValidationError(Exception):
    """Raised when two DSL layers disagree in ways Pydantic alone cannot detect."""


def validate_ui_against_api(ui_schema: UISchema, api_schema: APISchema) -> None:
    """Ensure UI components only bind to endpoints that exist in the API schema."""
    endpoint_paths = {endpoint.path for endpoint in api_schema.endpoints}
    endpoints_by_path = _group_endpoints_by_path(api_schema.endpoints)

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


def _group_endpoints_by_path(endpoints: list[Endpoint]) -> dict[str, list[Endpoint]]:
    grouped: dict[str, list[Endpoint]] = {}
    for endpoint in endpoints:
        grouped.setdefault(endpoint.path, []).append(endpoint)
    return grouped


def _validate_component_endpoint_binding(
    component: Component,
    *,
    page_name: str,
    page_route: str,
    endpoint_paths: set[str],
    endpoints_by_path: dict[str, list[Endpoint]],
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

    endpoints_at_path = endpoints_by_path[binding]
    endpoint = _resolve_bound_endpoint(component, endpoints_at_path)
    request_keys = schema_field_names(endpoint.request_schema)

    for mapping in component.payload_mapping or []:
        if mapping.api_field_name not in request_keys:
            methods_at_path = [
                f"{ep.method.value} {ep.path}" for ep in endpoints_at_path]
            raise CrossLayerValidationError(
                f"Component '{component.id}' on page '{page_name}' maps UI input "
                f"'{mapping.ui_input_name}' to API field '{mapping.api_field_name}', but "
                f"resolved endpoint '{endpoint.method.value} {binding}' request_schema "
                f"fields are {sorted(request_keys) or '(none)'}. "
                f"Endpoints at this path: {methods_at_path}."
            )


def _resolve_bound_endpoint(
    component: Component,
    endpoints_at_path: list[Endpoint],
) -> Endpoint:
    if len(endpoints_at_path) == 1:
        return endpoints_at_path[0]

    candidates = _candidates_for_component_type(
        component.type, endpoints_at_path)
    if len(candidates) == 1:
        return candidates[0]

    mapped_fields = payload_api_field_names(component.payload_mapping)
    if mapped_fields:
        compatible = [
            endpoint
            for endpoint in candidates
            if mapped_fields.issubset(schema_field_names(endpoint.request_schema))
        ]
        if len(compatible) == 1:
            return compatible[0]
        if len(compatible) > 1:
            picked = _select_by_method_priority(component.type, compatible)
            if picked is not None:
                return picked
            raise CrossLayerValidationError(
                f"Component '{component.id}' (type={component.type.value}) binds to path "
                f"'{endpoints_at_path[0].path}' but payload_mapping is compatible with "
                f"multiple endpoints: "
                f"{', '.join(ep.method.value for ep in compatible)}."
            )

    picked = _select_by_method_priority(component.type, candidates)
    if picked is not None:
        return picked

    methods = ", ".join(
        endpoint.method.value for endpoint in endpoints_at_path)
    preferred = _COMPONENT_METHOD_PRIORITY.get(component.type, ())
    raise CrossLayerValidationError(
        f"Component '{component.id}' (type={component.type.value}) binds to path "
        f"'{endpoints_at_path[0].path}' but cannot resolve an endpoint among "
        f"methods [{methods}]. Disambiguate with payload_mapping. "
        f"Preferred methods for this component type: "
        f"{', '.join(method.value for method in preferred) or 'none'}."
    )


def _candidates_for_component_type(
    component_type: ComponentType,
    endpoints_at_path: list[Endpoint],
) -> list[Endpoint]:
    allowed_methods = set(_COMPONENT_METHOD_PRIORITY.get(component_type, ()))
    if not allowed_methods:
        return endpoints_at_path

    filtered = [
        endpoint for endpoint in endpoints_at_path if endpoint.method in allowed_methods]
    if not filtered:
        methods = ", ".join(
            endpoint.method.value for endpoint in endpoints_at_path)
        preferred = ", ".join(
            method.value for method in _COMPONENT_METHOD_PRIORITY[component_type])
        raise CrossLayerValidationError(
            f"No endpoint at path '{endpoints_at_path[0].path}' uses an HTTP method "
            f"appropriate for component type {component_type.value}. "
            f"Available methods: [{methods}]. Expected one of: [{preferred}]."
        )
    return filtered


def _select_by_method_priority(
    component_type: ComponentType,
    candidates: list[Endpoint],
) -> Endpoint | None:
    for method in _COMPONENT_METHOD_PRIORITY.get(component_type, ()):
        for endpoint in candidates:
            if endpoint.method == method:
                return endpoint
    return None


def validate_api_against_db(api_schema: APISchema, db_schema: DatabaseSchema) -> None:
    """Sanity-check API endpoints against the database schema."""
    tables = {table.name: {column.name for column in table.columns}
              for table in db_schema.tables}
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
    segments = [segment for segment in path.strip("/").split("/") if segment]
    for segment in segments:
        if not _PATH_PARAM_PATTERN.match(segment):
            return segment
    return None


def _resolve_table_name(resource: str, tables: dict[str, set[str]]) -> str | None:
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
    fields: list[SchemaField] | None,
    table_name: str,
    table_columns: set[str],
    all_columns: set[str],
) -> None:
    if fields is None:
        return

    for schema_field in fields:
        field_name = schema_field.field_name
        if field_name in table_columns or field_name in _AUTH_OR_METADATA_FIELDS:
            continue

        if field_name in all_columns:
            continue

        raise CrossLayerValidationError(
            f"Endpoint '{endpoint.method.value} {endpoint.path}' {field_source} defines "
            f"field '{field_name}' which does not match any column on table '{table_name}' "
            f"(columns: {sorted(table_columns)}) or known auth/metadata fields."
        )
