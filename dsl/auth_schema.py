"""Authentication and authorization contract for the AI Software Compiler DSL.

Defines roles, permissions, and defaults used to generate auth middleware,
guards, and role-based access checks aligned with the API schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Role(BaseModel):
    """A named security role with an explicit permission grant list."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Unique snake_case role identifier (e.g. 'admin', 'viewer', 'editor'). "
            "Referenced by API endpoints via required_roles and assigned to users at runtime."
        ),
    )
    description: str = Field(
        description=(
            "Human-readable explanation of what this role represents and which users "
            "or workflows should receive it. Used in generated docs and admin UIs."
        ),
    )
    permissions: list[str] = Field(
        description=(
            "List of permission strings granted to holders of this role "
            "(e.g. 'users:read', 'orders:write'). Use consistent resource:action naming. "
            "An empty list denotes a role with no explicit grants beyond authentication."
        ),
    )


class AuthSchema(BaseModel):
    """Root authentication contract: roles and the default role for new users."""

    model_config = ConfigDict(extra="forbid")

    roles: list[Role] = Field(
        description=(
            "All roles defined for the application. Role names must be unique. "
            "Endpoints in api_schema may reference these names in required_roles."
        ),
    )
    default_role: str = Field(
        description=(
            "Name of the role automatically assigned to newly registered or anonymous "
            "authenticated users. Must match the name field of one entry in roles."
        ),
    )
