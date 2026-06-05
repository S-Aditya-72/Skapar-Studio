import sqlite3
from fastapi import FastAPI, Request
import json
import os

app = FastAPI(title="AI Generated Backend (Fully Functional)")


def get_db_connection():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn


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
    print(f"🗄️ Database created with real tables at {db_path}")


def get_actual_table_name(cursor, path_val: str):
    """Smarter matching to handle /contacts (API) vs Contact (Table)"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    base_name = path_val.strip('/').split('/')[0].lower()

    for t in tables:
        t_lower = t.lower()
        # Match exactly, or if one has a trailing 's'
        if t_lower == base_name or t_lower + "s" == base_name or t_lower == base_name + "s":
            return t
    return None


def setup_api_routes(api_app: FastAPI, api_schema: dict):
    endpoints = api_schema.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]

        async def dynamic_handler(request: Request, path_val: str = path):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Use our smart matcher to find the real table name!
                table_name = get_actual_table_name(cursor, path_val)

                if not table_name:
                    # If it's something like /analytics, just echo.
                    if request.method == "POST":
                        payload = await request.json()
                        return {"status": "success", "message": f"Echo: {path_val}", "data": payload}
                    return {"status": "success", "data": [{"warning": f"Endpoint '{path_val}' has no matching DB table."}]}

                if request.method == "POST":
                    payload = await request.json()
                    if not payload:
                        return {"status": "error", "message": "Empty payload"}

                    columns = ', '.join(payload.keys())
                    placeholders = ', '.join(['?' for _ in payload])
                    values = tuple(payload.values())

                    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                    cursor.execute(query, values)
                    conn.commit()
                    return {"status": "success", "message": f"Saved to {table_name}", "data": payload}

                elif request.method == "GET":
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = [dict(row) for row in cursor.fetchall()]
                    return {"status": "success", "data": rows}

            except sqlite3.OperationalError as e:
                return {"status": "error", "message": str(e)}
            finally:
                if 'conn' in locals():
                    conn.close()

        dynamic_handler.__name__ = f"handler_{path.replace('/', '_').replace('{', '').replace('}', '')}_{method}"

        api_app.add_api_route(
            path=path,
            endpoint=dynamic_handler,
            methods=[method]
        )


if os.path.exists("compiled_app.json"):
    with open("compiled_app.json", "r") as f:
        app_schema = json.load(f)
        setup_api_routes(app, app_schema.get("api", {}))
