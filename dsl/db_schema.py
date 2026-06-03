"""Database schema contract for the AI Software Compiler DSL.

Defines relational table structures that the compiler uses to generate
migrations, ORM models, and persistence layers deterministically.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DataType(str, Enum):
    """Logical column data types supported by the compiler's persistence layer."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    UUID = "uuid"
    DATETIME = "datetime"
    FLOAT = "float"


class Column(BaseModel):
    """A single column definition within a database table."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Snake_case identifier for the column (e.g. 'user_id', 'created_at'). "
            "Must be unique within the parent table and valid as a SQL/ORM column name."
        ),
    )
    type: DataType = Field(
        description=(
            "Logical data type for this column. Maps to native SQL and Python types "
            "during code generation (e.g. string -> VARCHAR/TEXT, uuid -> UUID)."
        ),
    )
    is_primary_key: bool = Field(
        description=(
            "True if this column is part of the table's primary key. "
            "At least one column per table should be marked primary key when the table "
            "represents an entity with a stable identifier."
        ),
    )
    is_nullable: bool = Field(
        description=(
            "True if the column may contain NULL values. Primary key columns should "
            "typically be non-nullable (is_nullable=False)."
        ),
    )
    foreign_key_reference: str | None = Field(
        default=None,
        description=(
            "Optional foreign key target in 'table_name.column_name' format "
            "(e.g. 'users.id'). Omit or set to null when this column is not a foreign key."
        ),
    )


class Table(BaseModel):
    """A logical database table composed of one or more columns."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Snake_case plural or singular table name (e.g. 'users', 'order_items'). "
            "Used as the physical SQL table name and ORM class naming input."
        ),
    )
    columns: list[Column] = Field(
        min_length=1,
        description=(
            "Ordered list of column definitions. Must include at least one column. "
            "Together they define the full shape of the table for migrations and models."
        ),
    )


class DatabaseSchema(BaseModel):
    """Root database contract: all tables that constitute the application's data model."""

    model_config = ConfigDict(extra="forbid")

    tables: list[Table] = Field(
        description=(
            "Complete set of tables for the application. Tables may reference each other "
            "via Column.foreign_key_reference. An empty list is valid only for "
            "stateless apps with no persistence."
        ),
    )
