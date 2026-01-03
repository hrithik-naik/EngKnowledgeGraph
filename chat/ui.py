import streamlit as st
import requests
from requests.exceptions import RequestException, Timeout

API_URL = "http://engknowledgegraph-backend:8000/query"
 # change if running in Docker


def call_backend(query: str) -> str:
    """
    Call FastAPI backend.
    Returns assistant response text.
    Falls back safely on failure.
    """
    try:
        response = requests.post(
            API_URL,
            json={"query": query},
            timeout=5,
        )

        if response.status_code != 200:
            return (
                "⚠️ Backend error.\n\n"
                "Query service is unavailable right now."
            )

        data = response.json()
        return data.get(
            "answer",
            "⚠️ Empty response from backend.",
        )

    except Timeout:
        return (
            "⏳ Request timed out.\n\n"
            "Backend might be starting up."
        )
    except RequestException:
        return (
            "⚠️ Unable to reach backend.\n\n"
            "Showing placeholder response."
        )


def main():
    st.set_page_config(
        page_title="EngKnowledgeGraph",
        page_icon="🕸️",
        layout="centered",
    )

    st.title("🕸️ EngKnowledgeGraph")
    st.caption("Chat interface for querying infrastructure graph")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input(
        "Ask something about the infrastructure..."
    )

    if user_input:
        # User message
        st.session_state.messages.append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user"):
            st.markdown(user_input)

        # Assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = call_backend(user_input)
                st.markdown(answer)

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )


if __name__ == "__main__":
    main()
