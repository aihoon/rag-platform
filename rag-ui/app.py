"""
File: app.py
Purpose: Streamlit-based chat UI client for Rag API Progix.

This module provides a simple interactive frontend that sends requests to
the `/chat` endpoint and renders both JSON and streaming responses.
"""

import json
import os
from urllib.parse import urlparse
from typing import Any, Dict, Optional

import requests
import streamlit as st

DEFAULT_RAG_API_URL = os.environ.get("RAG_API_URL", "").strip()
if DEFAULT_RAG_API_URL:
    parsed_default_url = urlparse(DEFAULT_RAG_API_URL)
    DEFAULT_SCHEME = parsed_default_url.scheme or "http"
    DEFAULT_HOST = parsed_default_url.hostname or "localhost"
    DEFAULT_PORT = parsed_default_url.port or 8000
    DEFAULT_API_BASE_PATH = "/" + parsed_default_url.path.strip("/")
else:
    DEFAULT_SCHEME = "https"
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 8000
    DEFAULT_API_BASE_PATH = "/rag-api"

DEFAULT_CHAT_PATH = "/chat"


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = None


def _parse_service_payload(
    rag_type: str,
    company_id: Optional[int],
    machine_cat: Optional[str],
    machine_id: Optional[int],
    dashboard_id: Optional[int],
    model_id: Optional[int],
    extra_json_text: str,
) -> Dict[str, Any]:
    service_payload: Dict[str, Any] = {"ragType": rag_type}

    resolved_company_id = 0 if company_id is None else company_id
    service_payload["companyId"] = resolved_company_id
    if machine_cat is not None:
        service_payload["machineCat"] = machine_cat
    if machine_id is not None:
        service_payload["machineId"] = machine_id
    if dashboard_id is not None:
        service_payload["dashboardId"] = dashboard_id
    if model_id is not None:
        service_payload["modelId"] = model_id

    extra_json_text = extra_json_text.strip()
    if extra_json_text:
        extra = json.loads(extra_json_text)
        if not isinstance(extra, dict):
            raise ValueError("Additional service JSON must be an object (dict).")
        service_payload.update(extra)

    return service_payload


def _render_messages() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            meta = msg.get("meta")
            if meta:
                with st.expander("Metadata"):
                    st.json(meta)


def _request(
    endpoint: str,
    payload: Dict[str, Any],
    timeout_sec: int,
):
    return requests.post(
        endpoint,
        json=payload,
        timeout=timeout_sec,
        stream=True,
    )


def _build_endpoint(
    scheme: str,
    host: str,
    port: int,
    api_base_path: str,
    chat_path: str,
) -> str:
    base_path = api_base_path.strip("/")
    chat_route = chat_path.strip("/")
    root = f"{scheme}://{host}:{port}"

    if base_path:
        return f"{root}/{base_path}/{chat_route}"
    return f"{root}/{chat_route}"


def _build_api_url(
    scheme: str,
    host: str,
    port: int,
    api_base_path: str,
    route_path: str,
) -> str:
    base_path = api_base_path.strip("/")
    route = route_path.strip("/")
    root = f"{scheme}://{host}:{port}"
    if base_path:
        return f"{root}/{base_path}/{route}"
    return f"{root}/{route}"


def _call_health_check(url: str, timeout_sec: int) -> Dict[str, Any]:
    try:
        resp = requests.get(url, timeout=timeout_sec)
        if resp.ok:
            return {"ok": True, "status_code": resp.status_code, "data": resp.json()}
        return {
            "ok": False,
            "status_code": resp.status_code,
            "data": resp.text,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    st.set_page_config(page_title="RAG API Streamlit UI", page_icon="🤖", layout="wide")
    _init_state()

    st.title("RAG API Streamlit UI")
    st.caption("Client for testing the `/chat` endpoint")

    with st.sidebar:
        st.subheader("Connection")
        scheme_options = ["https", "http"]
        scheme_index = 0 if DEFAULT_SCHEME == "https" else 1
        scheme = st.selectbox("Scheme", options=scheme_options, index=scheme_index)
        host = st.text_input("Host", value=DEFAULT_HOST)
        port = st.number_input(
            "Port",
            min_value=1,
            max_value=65535,
            value=DEFAULT_PORT,
            step=1,
        )
        api_base_path = st.text_input("API Base Path", value=DEFAULT_API_BASE_PATH)
        chat_path = st.text_input("Chat Path", value=DEFAULT_CHAT_PATH)
        chat_endpoint = _build_endpoint(
            scheme=scheme,
            host=host.strip(),
            port=int(port),
            api_base_path=api_base_path,
            chat_path=chat_path,
        )
        timeout_sec = st.slider("Timeout (sec)", min_value=5, max_value=180, value=90)

        st.subheader("Live Checks")
        health_endpoint = _build_api_url(
            scheme=scheme,
            host=host.strip(),
            port=int(port),
            api_base_path=api_base_path,
            route_path="/health",
        )
        weaviate_endpoint = _build_api_url(
            scheme=scheme,
            host=host.strip(),
            port=int(port),
            api_base_path=api_base_path,
            route_path="/health/weaviate-live",
        )

        if st.button("API Health Check"):
            result = _call_health_check(health_endpoint, timeout_sec)
            if result.get("ok"):
                st.success(result)
            else:
                st.error(result)

        if st.button("Weaviate Live Check"):
            result = _call_health_check(weaviate_endpoint, timeout_sec)
            if result.get("ok"):
                st.success(result)
            else:
                st.error(result)

        st.subheader("Request Fields")
        user_id = st.text_input("userId", value="streamlit-user")
        rag_type = st.selectbox(
            "RAG Type",
            options=["standard", "conversational", "corrective"],
            index=0,
        )
        company_id_value = st.text_input("Company ID (default: 0)", value="")
        company_id: Optional[int] = None
        if company_id_value.strip():
            company_id = int(company_id_value.strip())

        machine_cat = st.text_input("Machine Category (optional)", value="")

        machine_id_value = st.text_input("Machine ID (optional)", value="")
        machine_id: Optional[int] = None
        if machine_id_value.strip():
            machine_id = int(machine_id_value.strip())

        dashboard_id_value = st.text_input("Dashboard ID (optional)", value="")
        model_id_value = st.text_input("Model ID (optional)", value="")
        dashboard_id = int(dashboard_id_value) if dashboard_id_value.strip() else None
        model_id = int(model_id_value) if model_id_value.strip() else None

        extra_service_json = st.text_area(
            "extra JSON (optional)",
            value="",
            placeholder='{"key":"value"}',
            height=100,
        )

        if st.button("Reset conversation"):
            st.session_state.messages = []
            st.session_state.chat_id = None
            st.rerun()

    _render_messages()

    user_input = st.chat_input("Enter your message")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        service_payload = _parse_service_payload(
            rag_type=rag_type,
            company_id=company_id,
            machine_cat=machine_cat.strip() or None,
            machine_id=machine_id,
            dashboard_id=dashboard_id,
            model_id=model_id,
            extra_json_text=extra_service_json,
        )
    except Exception as exc:
        error_msg = f"Service payload build error: {exc}"
        st.error(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        return

    payload: Dict[str, Any] = {
        "userInput": user_input,
        "chatId": st.session_state.chat_id,
        "userId": user_id,
        "service": service_payload,
    }

    with st.chat_message("assistant"):
        placeholder = st.empty()
        assembled_text = ""
        meta: Dict[str, Any] = {"endpoint": chat_endpoint}

        try:
            resp = _request(
                endpoint=chat_endpoint,
                payload=payload,
                timeout_sec=timeout_sec,
            )
        except requests.RequestException as exc:
            err = f"Request failed: {exc}"
            placeholder.error(err)
            st.session_state.messages.append(
                {"role": "assistant", "content": err, "meta": meta}
            )
            return

        chat_id_header = resp.headers.get("X-Chat-ID")
        if chat_id_header:
            st.session_state.chat_id = chat_id_header
            meta["chatId"] = chat_id_header

        content_type = resp.headers.get("content-type", "")
        is_stream = "text/event-stream" in content_type

        if not resp.ok:
            detail = resp.text
            try:
                detail = resp.json()
            except ValueError:
                pass
            err = f"HTTP {resp.status_code}: {detail}"
            placeholder.error(err)
            st.session_state.messages.append(
                {"role": "assistant", "content": err, "meta": meta}
            )
            return

        if not is_stream:
            body = resp.json()
            assembled_text = body.get("message") or "(Empty response)"
            meta["intent"] = body.get("intent")
            meta["streaming"] = body.get("streaming")
            meta["sources"] = body.get("sources", [])
            placeholder.markdown(assembled_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": assembled_text, "meta": meta}
            )
            return

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            chunk_type = chunk.get("type")
            status = chunk.get("status")

            if chunk_type == "text" and status == "processing":
                assembled_text += chunk.get("content", "")
                placeholder.markdown(assembled_text)
            elif chunk_type == "text" and status == "complete":
                break
            elif chunk_type == "error":
                error_text = chunk.get("message", "A streaming error occurred.")
                assembled_text = f"[Error] {error_text}"
                placeholder.error(assembled_text)
                break

        if not assembled_text:
            assembled_text = "(No streaming output)"
            placeholder.markdown(assembled_text)

        meta["streaming"] = True
        st.session_state.messages.append(
            {"role": "assistant", "content": assembled_text, "meta": meta}
        )


if __name__ == "__main__":
    main()
