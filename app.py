import streamlit as st
import base64
from agent import chat, MODEL_HAIKU, MODEL_SONNET

st.set_page_config(
    page_title="Агро Асистент — Маслодайна Роза",
    page_icon="🌹",
    layout="centered",
)

st.title("🌹 Агро Асистент — Маслодайна Роза")

with st.sidebar:
    st.header("Настройки")
    model_choice = st.radio(
        "Модел",
        options=["Авто", "Haiku (бърз)", "Sonnet (прецизен)"],
        index=0,
        help="Авто — изборът се прави автоматично според заявката.",
    )

_FORCE_MODEL = {
    "Авто": None,
    "Haiku (бърз)": MODEL_HAIKU,
    "Sonnet (прецизен)": MODEL_SONNET,
}

if "messages" not in st.session_state:
    st.session_state.messages = []

# История на разговора
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Прикачване на снимка
uploaded_file = st.file_uploader(
    "Прикачи снимка (по избор)",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
)

image_data = None
if uploaded_file:
    image_bytes = uploaded_file.read()
    image_data = {
        "base64": base64.standard_b64encode(image_bytes).decode("utf-8"),
        "media_type": uploaded_file.type,
    }
    st.image(uploaded_file, width=300)

# Чат вход
if prompt := st.chat_input("Напиши съобщение..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Обработвам..."):
            response, used_model = chat(
                st.session_state.messages,
                image_data=image_data,
                force_model=_FORCE_MODEL[model_choice],
            )
        st.markdown(response)
        model_label = "Haiku" if "haiku" in used_model else "Sonnet"
        st.caption(f"Модел: {model_label}")

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
