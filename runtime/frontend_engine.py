import streamlit as st
import json
import requests

st.set_page_config(page_title="Compiled AI App", layout="wide")

API_BASE = "http://localhost:8000"

# Load the compiled JSON
try:
    with open("compiled_app.json", "r") as f:
        app_schema = json.load(f)
except FileNotFoundError:
    st.error("compiled_app.json not found! Please run the compiler first.")
    st.stop()

ui = app_schema.get("ui", {})
pages = {page["name"]: page for page in ui.get("pages", [])}
nav_menu = ui.get("nav_menu", list(pages.keys()))

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", nav_menu)

if selection in pages:
    st.title(selection)
    page_data = pages[selection]

    for comp in page_data.get("components", []):
        comp_type = comp.get("type")
        label = comp.get("label", "")
        endpoint = comp.get("api_endpoint_binding", "")

        # Clean the endpoint if it has path variables (e.g., /users/{id} -> /users/1)
        if "{" in endpoint:
            endpoint = endpoint.split("{")[0] + "1"

        url = f"{API_BASE}{endpoint}" if endpoint else ""

        st.subheader(label)

        if comp_type == "Text":
            st.write(label)

        elif comp_type == "Table":
            if url:
                try:
                    res = requests.get(url)
                    if res.status_code == 200:
                        st.json(res.json())
                except Exception:
                    st.warning(f"Backend not reachable for {endpoint}")
            else:
                st.dataframe([{"Demo": "No endpoint bound"}])

        elif comp_type == "Form":
            with st.form(key=comp["id"]):
                inputs = {}
                for mapping in comp.get("payload_mapping", []):
                    # We display the UI name, but save it under the API field name!
                    inputs[mapping["api_field_name"]] = st.text_input(
                        mapping["ui_input_name"])

                submitted = st.form_submit_button("Submit")
                if submitted:
                    if url:
                        try:
                            res = requests.post(url, json=inputs)
                            st.success(
                                f"Submitted to {endpoint}: {res.json()}")
                            st.rerun()  # Refresh to show updated data
                        except Exception:
                            st.error("Failed to connect to backend")

        elif comp_type == "Button":
            if st.button(label, key=comp["id"]):
                if url:
                    try:
                        requests.get(url)
                        st.toast(f"Triggered {endpoint}!")
                    except:
                        st.error("Backend not reachable")

        st.divider()
