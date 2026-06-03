"""Streamlit-oriented UI contract for the AI Software Compiler DSL.

Defines pages, navigation, and UI components (text, forms, tables, buttons)
that the compiler maps to a Streamlit runtime with API bindings.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComponentType(str, Enum):
    """Streamlit component kinds supported by the compiler's UI generator."""

    TEXT = "Text"
    FORM = "Form"
    TABLE = "Table"
    BUTTON = "Button"


class Component(BaseModel):
    """A single UI widget on a page, optionally bound to an API endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        description=(
            "Unique snake_case identifier for this component within the application "
            "(e.g. 'login_form', 'users_table'). Used for Streamlit keys and event wiring."
        ),
    )
    type: ComponentType = Field(
        description=(
            "Component kind: Text (static/markdown), Form (input fields + submit), "
            "Table (DataFrame display of API list data), Button (action trigger)."
        ),
    )
    label: str = Field(
        description=(
            "User-visible label or heading shown in the Streamlit UI "
            "(e.g. 'Sign in', 'All Users', 'Export CSV')."
        ),
    )
    api_endpoint_binding: str | None = Field(
        default=None,
        description=(
            "API path from api_schema this component calls or displays "
            "(e.g. '/users', '/auth/login'). Must match Endpoint.path exactly. "
            "Null for Text components with no backend interaction; required for "
            "Form, Table, and Button components that load or mutate data."
        ),
    )
    payload_mapping: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps UI field or action keys to API request body or query keys. "
            "For Form: {'email_input': 'email', 'password_input': 'password'}. "
            "For Button: {'submit': 'action'} or {} if the endpoint needs no body. "
            "For Table: often {} when GET returns the full dataset. "
            "Keys are component-internal identifiers; values are keys in Endpoint.request_schema."
        ),
    )


class Page(BaseModel):
    """One routable screen in the Streamlit app with an ordered list of components."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Human-readable page title shown in the UI and navigation "
            "(e.g. 'Dashboard', 'User Management')."
        ),
    )
    route: str = Field(
        description=(
            "URL-style route segment for multipage Streamlit apps, starting with '/' "
            "(e.g. '/', '/users', '/settings'). Must be unique across pages."
        ),
    )
    components: list[Component] = Field(
        description=(
            "Top-to-bottom render order of components on this page. "
            "At least one component is recommended per non-empty page."
        ),
    )


class UISchema(BaseModel):
    """Root UI contract: pages and navigation for the generated Streamlit frontend."""

    model_config = ConfigDict(extra="forbid")

    pages: list[Page] = Field(
        description=(
            "All application pages. Each Page.route should appear in nav_menu if the "
            "page is reachable from the main navigation."
        ),
    )
    nav_menu: list[str] = Field(
        description=(
            "Ordered list of Page.route values defining the sidebar or top navigation menu. "
            "Routes must correspond to entries in pages. First item is typically the home page."
        ),
    )
