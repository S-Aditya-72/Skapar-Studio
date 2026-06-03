from pydantic import BaseModel, Field
from enum import Enum


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    UUID = "uuid"
    DATETIME = "datetime"
    FLOAT = "float"


class Column(BaseModel):
    name: str = Field(description="Column name")
    type: DataType = Field(description="Data type")
    is_primary_key: bool = Field(
        description="Is this the primary key?", default=False)
    is_nullable: bool = Field(description="Can this be null?", default=False)
    foreign_key_reference: str = Field(
        description="Table.column reference if it's a FK, else empty", default="")


class Table(BaseModel):
    name: str = Field(description="Table name")
    columns: list[Column] = Field(
        description="List of columns", default_factory=list)


class DatabaseSchema(BaseModel):
    tables: list[Table] = Field(
        description="List of database tables", default_factory=list)
