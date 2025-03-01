import base64
import json
import logging
import os
import requests
import streamlit as st
from dotenv import load_dotenv
from io import StringIO
from subprocess import run, PIPE

def load_dotenv_from_azd():
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info(f"Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info(f"AZD environment not found. Trying to load from .env file...")
        load_dotenv()

def get_principal_id():
    result = st.context.headers.get('x-ms-client-principal-id')
    if result:
        return result
    else:
        return "default_user_id"

def get_principal_display_name():
    """
    Get the display name of the current user from the request headers.
    See https://learn.microsoft.com/en-us/azure/container-apps/authentication#access-user-claims-in-application-code for more information.
    """
    default_user_name = "Default User"
    principal = st.context.headers.get('x-ms-client-principal')
    if principal:
        principal = json.loads(base64.b64decode(principal).decode('utf-8'))
        claims = principal.get("claims", [])
        return next((claim["val"] for claim in claims if claim["typ"] == "name"), default_user_name)
    else:
        return default_user_name

def is_valid_json(json_string): 
    try: 
        json.loads(json_string) 
        return True 
    except json.JSONDecodeError: 
        return False

load_dotenv_from_azd()

st.sidebar.write(f"Welcome, {get_principal_display_name()}!")
st.sidebar.markdown(
    '<a href="/.auth/logout" target = "_self">Sign Out</a>', unsafe_allow_html=True
)

st.write("Requesting a blog post about cookies:")
result = None
with st.status("Agents are crafting a response...", expanded=True) as status:
    try:
        url = f'{os.getenv('BACKEND_ENDPOINT', 'http://localhost:8000')}/blog'
        payload = {"topic": "cookies", "user_id": get_principal_id()}
        with requests.post(url, json=payload, stream=True) as response:
            for line in response.iter_lines():
                result = line.decode('utf-8')
                # For each line as JSON
                # result = json.loads(line.decode('utf-8'))
                if not is_valid_json(result):
                   status.write(result)  
                   
        status.update(label="Backend call complete", state="complete", expanded=False)
    except Exception as e:
        status.update(
            label=f"Backend call failed: {e}", state="complete", expanded=False
        )
# st.markdown(result["content"])
st.markdown(json.loads(result)["content"])
