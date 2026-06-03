from pydantic import BaseModel, Field


class Role(BaseModel):
    name: str = Field(description="Role name (e.g., admin, user)")
    description: str = Field(description="Role description")
    permissions: list[str] = Field(
        description="List of permissions", default_factory=list)


class AuthSchema(BaseModel):
    roles: list[Role] = Field(
        description="List of roles", default_factory=list)
    default_role: str = Field(
        description="The default role for new users", default="user")
