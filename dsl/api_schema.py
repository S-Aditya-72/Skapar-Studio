from pydantic import BaseModel, Field
from enum import Enum


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class SchemaField(BaseModel):
    field_name: str = Field(description="Name of the field")
    field_type: str = Field(
        description="Type of the field (e.g., string, integer)")


class Endpoint(BaseModel):
    path: str = Field(description="API route path, e.g., /users")
    method: HttpMethod = Field(description="HTTP method")
    description: str = Field(description="What this endpoint does")
    requires_auth: bool = Field(
        description="Does it require authentication?", default=False)
    required_roles: list[str] = Field(
        description="Roles required to access", default_factory=list)
    request_schema: list[SchemaField] = Field(
        description="Expected input payload fields", default_factory=list)
    response_schema: list[SchemaField] = Field(
        description="Expected response payload fields", default_factory=list)


class APISchema(BaseModel):
    endpoints: list[Endpoint] = Field(
        description="List of API endpoints", default_factory=list)
