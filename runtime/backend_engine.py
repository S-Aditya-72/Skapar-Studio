import sqlite3
from fastapi import FastAPI, Request
import json
import os

app = FastAPI(title="AI Generated Backend")


def generate_database(db_schema: dict, db_path: str = "app.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    type_mapping = {
        "string": "TEXT",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "uuid": "TEXT",
        "datetime": "TEXT",
        "float": "REAL"
    }

    for table in db_schema.get("tables", []):
        columns = []
        for col in table.get("columns", []):
            col_type = type_mapping.get(col.get("type", "string"), "TEXT")
            pk = "PRIMARY KEY" if col.get("is_primary_key") else ""
            columns.append(f"{col['name']} {col_type} {pk}")

        create_stmt = f"CREATE TABLE IF NOT EXISTS {table['name']} ({', '.join(columns)});"
        cursor.execute(create_stmt)

    conn.commit()
    conn.close()
    print(f"Database created at {db_path}")


def setup_api_routes(api_app: FastAPI, api_schema: dict):
    endpoints = api_schema.get("endpoints", [])
    if not endpoints:
        print("No endpoints found in schema.")

    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]

        # Create a dynamic route handler
        async def dynamic_handler(request: Request, path_val: str = path):
            if request.method in ["POST", "PUT"]:
                payload = await request.json()
                return {"status": "success", "message": f"Processed {request.method} to {path_val}", "data": payload}
            return {"status": "success", "message": f"Mock GET response from {path_val}", "data": []}

        # FastAPI needs unique names for dynamic functions
        dynamic_handler.__name__ = f"handler_{path.replace('/', '_').replace('{', '').replace('}', '')}_{method}"

        api_app.add_api_route(
            path=path,
            endpoint=dynamic_handler,
            methods=[method],
            summary=endpoint.get("description", "Dynamic Route")
        )
    print(f"✅ Dynamic API routes configured: {[e['path'] for e in endpoints]}")


# 🚀 NEW: Auto-load routes when Uvicorn starts this file in the subprocess!
if os.path.exists("compiled_app.json"):
    with open("compiled_app.json", "r") as f:
        app_schema = json.load(f)
        setup_api_routes(app, app_schema.get("api", {}))
