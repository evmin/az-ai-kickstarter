import logging
import os
import streamlit as st
import requests
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

def call_backend(backend_endpoint, payload):
    """
    Call the backend API with the given payload. Raises and exception if HTTP response code is not 200.
    """
    url = f'{backend_endpoint}/blog'
    headers = {}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response

def get_principal_name():
    result = st.context.headers.get('x-ms-client-principal-name')
    if result:
        return result
    else:
        return "Anonymous"

def get_principal_id():
    result = st.context.headers.get('x-ms-client-principal-id')
    if result:
        return result
    else:
        return "default_user_id"

load_dotenv_from_azd()

st.write(get_principal_name())
st.markdown('<a href="/.auth/logout" target = "_self">Sign Out</a>', unsafe_allow_html=True)

st.write("Calling backend API...")
st.write(call_backend(os.getenv('BACKEND_ENDPOINT', 'http://localhost:8000'), {"topic": "cookies", "user_id": get_principal_id()}).json())
