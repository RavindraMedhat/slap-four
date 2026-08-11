"""Firestore access for Streamlit - talks to Firestore directly via a
service account key (Admin-equivalent access), with no Cloud Functions and
no Blaze billing plan required at all. Firestore itself is free on the
Spark plan within its generous daily quota."""

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account


@st.cache_resource
def get_db():
    info = dict(st.secrets["firebase_service_account"])
    creds = service_account.Credentials.from_service_account_info(info)
    return firestore.Client(credentials=creds, project=info["project_id"])
