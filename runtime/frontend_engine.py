import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Skapar Studio", layout="wide",
                   initial_sidebar_state="expanded")

API_BASE = "http://localhost:8000"

# --- STATE MANAGEMENT ---
if "app_schema" not in st.session_state:
    st.session_state.app_schema = None
if "active_page" not in st.session_state:
    st.session_state.active_page = None
if "has_booted" not in st.session_state:
    st.session_state.has_booted = False  # <--- New variable!

# --- VIEW 1: THE PROMPT COMPILER SCREEN ---
if not st.session_state.app_schema:
    # ONLY auto-load if this is the very first time opening the app
    if not st.session_state.has_booted:
        st.session_state.has_booted = True
        try:
            res = requests.get(f"{API_BASE}/api/system/schema")
            if res.status_code == 200 and "ui" in res.json():
                st.session_state.app_schema = res.json()
                st.session_state.active_page = res.json()["ui"]["nav_menu"][0]
                st.rerun()
        except:
            pass

    # The Lovable-style UI
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<h1 style='text-align: center;'>🤖 Skapar Studio</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Describe your software. The AI Compiler will generate the Database, API, and UI.</p>", unsafe_allow_html=True)

        st.write("")
        prompt = st.text_area("What do you want to build?",
                              placeholder="e.g., Build a CRM with login, contacts, dashboard, and role access...", height=100)

        if st.button("Compile & Run", type="primary", use_container_width=True):
            if prompt:
                with st.spinner("⚙️ Compiling architecture... (This takes about 60 seconds)"):
                    try:
                        response = requests.post(
                            f"{API_BASE}/api/system/compile", json={"prompt": prompt})
                        data = response.json()
                        if data.get("status") == "success":
                            st.session_state.app_schema = data["schema"]
                            st.session_state.active_page = data["schema"]["ui"]["nav_menu"][0]
                            st.success("Compilation Complete!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Compilation failed.")
                    except Exception as e:
                        st.error(f"Error connecting to Compiler Engine: {e}")
            else:
                st.warning("Please enter a prompt.")
        # Existing Compile Button Logic ends here...

        st.write("")  # Spacer
        if st.button("⚡ Quick Load Generated App (Bypass Wait)", use_container_width=True):
            try:
                res = requests.get(f"{API_BASE}/api/system/schema")
                data = res.json()
                if "ui" in data:
                    st.session_state.app_schema = data
                    st.session_state.active_page = data["ui"]["nav_menu"][0]
                    st.rerun()
                else:
                    st.error("No compiled app found on server.")
            except Exception as e:
                st.error("Backend server is not running!")
    st.stop()  # Stop rendering here if no schema

# --- VIEW 2: THE GENERATED APP ---
ui = st.session_state.app_schema.get("ui", {})
pages = {page["name"]: page for page in ui.get("pages", [])}
nav_menu = ui.get("nav_menu", list(pages.keys()))

# Sidebar Navigation
with st.sidebar:
    st.title("Skapar Studio")
    st.divider()

    st.session_state.active_page = st.radio("Navigation", nav_menu, index=nav_menu.index(
        st.session_state.active_page) if st.session_state.active_page in nav_menu else 0)

    st.divider()
    if st.button("← Back to Compiler", use_container_width=True):
        st.session_state.app_schema = None
        st.rerun()

# Main Dynamic Content
if st.session_state.active_page in pages:
    st.header(st.session_state.active_page)
    page_data = pages[st.session_state.active_page]

    for comp in page_data.get("components", []):
        comp_type = comp.get("type")
        label = comp.get("label", "")
        endpoint = comp.get("api_endpoint_binding", "")

        # Clean path variables
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
                    if res.status_code == 200 and res.json().get("data"):
                        st.dataframe(res.json()["data"],
                                     use_container_width=True)
                    else:
                        st.info("No data yet.")
                except Exception:
                    st.warning(f"Backend not reachable for {endpoint}")
            else:
                st.dataframe([{"Demo": "No endpoint bound"}])

        elif comp_type == "Form":
            with st.form(key=comp["id"]):
                inputs = {}
                for mapping in comp.get("payload_mapping", []):
                    inputs[mapping["api_field_name"]] = st.text_input(
                        mapping["ui_input_name"])

                submitted = st.form_submit_button("Submit", type="primary")
                if submitted:
                    if url:
                        try:
                            res = requests.post(url, json=inputs)
                            if res.ok:
                                st.success(f"Successfully saved!")
                                time.sleep(0.5)
                                st.rerun()  # Refresh the tables!
                            else:
                                st.error("Failed to save.")
                        except Exception:
                            st.error("Failed to connect to backend.")

        elif comp_type == "Button":
            if st.button(label, key=comp["id"]):
                if url:
                    try:
                        requests.get(url)
                        st.toast(f"Triggered {endpoint}!")
                    except:
                        st.error("Backend not reachable.")

        st.divider()
