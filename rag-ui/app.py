"""
File: app.py
Purpose: Streamlit-based chat UI client for Rag API Progix.

This module provides a simple interactive frontend that sends requests to
the `/chat` endpoint and renders both JSON and streaming responses.
"""

import json
import os
from urllib.parse import urlparse, urlunparse
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
DEFAULT_CHAT_ENDPOINT = DEFAULT_RAG_API_URL or f"{DEFAULT_SCHEME}://{DEFAULT_HOST}:{DEFAULT_PORT}{DEFAULT_API_BASE_PATH}{DEFAULT_CHAT_PATH}"


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = None


def _parse_service_payload(
    rag_type: str,
    class_name: Optional[str],
    company_id: Optional[int],
    machine_cat: Optional[int],
    machine_id: Optional[int],
    dashboard_id: Optional[int],
    model_id: Optional[int],
    extra_json_text: str,
) -> Dict[str, Any]:
    service_payload: Dict[str, Any] = {"ragType": rag_type}
    if class_name is not None:
        service_payload["className"] = class_name
    if company_id is not None:
        service_payload["companyId"] = company_id
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
                external_sources = meta.get("externalSources")
                external_summary = meta.get("externalSummary")
                if isinstance(external_sources, list) and external_sources:
                    with st.expander("External Sources"):
                        if external_summary:
                            st.markdown(f"**Summary**\n\n{external_summary}")
                        for item in external_sources:
                            if not isinstance(item, dict):
                                continue
                            title = item.get("title") or "Untitled"
                            url = item.get("url") or ""
                            content = item.get("content") or ""
                            with st.container(border=True):
                                st.markdown(f"**{title}**")
                                if url:
                                    st.markdown(url)
                                if content:
                                    st.markdown(content)


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


def _normalize_chat_endpoint(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("RAG API Chat URL must include scheme, host, and port.")
    normalized_path = "/" + parsed.path.strip("/")
    if not normalized_path or normalized_path == "/":
        normalized_path = DEFAULT_CHAT_PATH
    elif not normalized_path.endswith(DEFAULT_CHAT_PATH):
        normalized_path = f"{normalized_path.rstrip('/')}{DEFAULT_CHAT_PATH}"
    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))


def _build_related_api_url(chat_endpoint: str, route_path: str) -> str:
    parsed = urlparse(chat_endpoint.strip())
    chat_path = "/" + parsed.path.strip("/")
    base_path = chat_path[: -len(DEFAULT_CHAT_PATH)] if chat_path.endswith(DEFAULT_CHAT_PATH) else chat_path
    normalized_route = "/" + route_path.strip("/")
    related_path = f"{base_path.rstrip('/')}{normalized_route}" if base_path.strip("/") else normalized_route
    return urlunparse((parsed.scheme, parsed.netloc, related_path, "", "", ""))


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


def _call_summary_check(url: str, timeout_sec: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(url, params=params, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")
    return body


def main() -> None:
    st.set_page_config(page_title="RAG API Streamlit UI", page_icon="🤖", layout="wide")
    _init_state()

    st.title("RAG API Streamlit UI")
    st.caption("Client for testing the `/chat` endpoint")

    with st.sidebar:
        st.subheader("Connection")
        rag_api_chat_url = st.text_input("RAG API Chat URL", value=DEFAULT_CHAT_ENDPOINT)
        try:
            chat_endpoint = _normalize_chat_endpoint(rag_api_chat_url)
        except ValueError as exc:
            st.error(str(exc))
            return
        timeout_sec = st.slider("Timeout (sec)", min_value=5, max_value=180, value=90)

        st.subheader("Live Checks")
        health_endpoint = _build_related_api_url(chat_endpoint, "/health")
        weaviate_endpoint = _build_related_api_url(chat_endpoint, "/health/weaviate-live")
        neo4j_endpoint = _build_related_api_url(chat_endpoint, "/health/neo4j-live")
        weaviate_summary_endpoint = _build_related_api_url(chat_endpoint, "/health/weaviate-summary")
        neo4j_summary_endpoint = _build_related_api_url(chat_endpoint, "/health/neo4j-summary")

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

        if st.button("Neo4j Live Check"):
            result = _call_health_check(neo4j_endpoint, timeout_sec)
            if result.get("ok"):
                st.success(result)
            else:
                st.error(result)

        st.subheader("Request Fields")
        user_id = st.text_input("userId", value="streamlit-user")
        rag_type = st.selectbox(
            "RAG Type",
            options=["standard", "conversational", "corrective", "self_rag", "fusion", "hyde", "graph",
                     "adaptive", "agentic"],
            index=0,
        )
        class_name = st.selectbox("Class / Label", options=["General", "Machine"], index=0)
        if class_name == "Machine":
            company_id = st.number_input("company_id", min_value=0, value=0, step=1)
            machine_cat = st.number_input("machine_cat", min_value=0, value=0, step=1)
            machine_id = st.number_input("machine_id", min_value=0, value=0, step=1)
        else:
            company_id = None
            machine_cat = None
            machine_id = None
            st.caption("Class 'General' does not use company/machine filters.")

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

        st.subheader("Summaries")
        if st.button("Refresh Weaviate Summary"):
            try:
                result = _call_summary_check(
                    weaviate_summary_endpoint,
                    timeout_sec,
                    params={"class_name": class_name} if class_name else None,
                )
                st.json(result)
            except Exception as exc:
                st.error(f"Failed to fetch Weaviate summary: {exc}")

        if st.button("Refresh Neo4j Summary"):
            try:
                result = _call_summary_check(
                    neo4j_summary_endpoint,
                    timeout_sec,
                    params={"label": class_name} if class_name else None,
                )
                st.json(result)
            except Exception as exc:
                st.error(f"Failed to fetch Neo4j summary: {exc}")

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
            class_name=class_name,
            company_id=company_id,
            machine_cat=machine_cat,
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
            meta["externalSources"] = body.get("externalSources", [])
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
