from pydantic import BaseModel, Field
from .requirements_schema import RequirementsSchema
from .db_schema import DatabaseSchema
from .auth_schema import AuthSchema
from .api_schema import APISchema
from .ui_schema import UISchema


class MasterAppSchema(BaseModel):
    requirements: RequirementsSchema = Field(default=None)
    database: DatabaseSchema
    auth: AuthSchema
    api: APISchema
    ui: UISchema
