import os
import tempfile
import streamlit as st
import base64
from datetime import date
from pathlib import Path
from agent import chat, MODEL_HAIKU, MODEL_SONNET
from tools import save_temp_photo, PHOTOS_BASE_PATH

# Увери се, че работната директория е папката на проекта
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Път до YOLOv11 модела — дефиниран преди всичко друго
MODEL_PATH = Path("08_AI_Model/models/trained/best_v1.pt")

st.set_page_config(
    page_title="Агро Асистент — Маслодайна Роза",
    page_icon="🌹",
    layout="centered",
)

st.title("🌹 Агро Асистент — Маслодайна Роза")

# ---------------------------------------------------------------------------
# Странично меню
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Модели")

    st.markdown("**Снимки:**")
    if MODEL_PATH.exists():
        st.success("YOLOv11 — локален анализ")
        st.caption("Болестите се засичат локално. Claude Haiku дава агрономска препоръка.")
    else:
        st.warning("YOLOv11 моделът не е намерен")

    st.markdown("**Текстови въпроси:**")
    st.info("Claude Haiku")
    st.caption("Бърз и евтин модел за всички текстови заявки.")

    st.divider()
    st.caption("Моделът се избира автоматично.")

# ---------------------------------------------------------------------------
# Session state — запазва данните между rerun-ите
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "temp_photo_filename" not in st.session_state:
    st.session_state.temp_photo_filename = None
if "yolo_result" not in st.session_state:
    st.session_state.yolo_result = None

# ---------------------------------------------------------------------------
# YOLOv11 — локален анализ на снимки
# ---------------------------------------------------------------------------

def _yolo_analyze(image_b64: str, media_type: str) -> str | None:
    """Анализира снимката с YOLOv11 локално.
    Връща текстов резултат за Claude или None при грешка.
    """
    if not MODEL_PATH.exists():
        return None
    try:
        from ultralytics import YOLO
        import base64 as _b64

        ext = media_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"

        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(_b64.b64decode(image_b64))
            tmp_path = tmp.name

        model   = YOLO(str(MODEL_PATH))
        results = model.predict(tmp_path, conf=0.25, verbose=False)
        os.unlink(tmp_path)

        detections = []
        for r in results:
            for box in r.boxes:
                cls_name = model.names[int(box.cls[0])]
                conf     = float(box.conf[0])
                detections.append((cls_name, conf))

        if not detections:
            return "YOLOv11 анализ: Не са открити болести. Растението изглежда здраво."

        lines = ["YOLOv11 анализ на снимката:"]
        for cls_name, conf in detections:
            lines.append(f"  - {cls_name}: {conf:.0%} увереност")
        return "\n".join(lines)

    except Exception as e:
        return f"YOLOv11 анализ: грешка ({e})"

# ---------------------------------------------------------------------------
# История на разговора
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Upload на снимка — над чат полето, само показва снимката
# ---------------------------------------------------------------------------

uploaded_file = st.file_uploader(
    "📷 Прикачи снимка за анализ",
    type=["jpg", "jpeg", "png"],
    label_visibility="visible",
)

if uploaded_file:
    image_bytes = uploaded_file.read()
    image_data  = {
        "base64":     base64.standard_b64encode(image_bytes).decode("utf-8"),
        "media_type": uploaded_file.type,
    }
    st.image(uploaded_file, width=300)

    # Записваме снимката временно и пускаме YOLOv11 само веднъж
    if st.session_state.temp_photo_filename is None:
        try:
            st.session_state.temp_photo_filename = save_temp_photo(
                image_data["base64"], uploaded_file.type
            )
        except Exception as e:
            st.warning(f"Снимката не може да се запази временно: {e}")

        if MODEL_PATH.exists():
            with st.spinner("YOLOv11 анализира снимката..."):
                st.session_state.yolo_result = _yolo_analyze(
                    image_data["base64"], uploaded_file.type
                )
        else:
            st.error("YOLOv11 моделът не е намерен. Анализът на снимки не е наличен.")

    if st.session_state.yolo_result:
        st.info(st.session_state.yolo_result)

else:
    # Снимката е премахната — нулираме
    st.session_state.temp_photo_filename = None
    st.session_state.yolo_result = None

# ---------------------------------------------------------------------------
# Чат вход
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Напиши съобщение..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    success = False
    with st.chat_message("assistant"):
        with st.spinner("Обработвам..."):
            try:
                if st.session_state.yolo_result:
                    # YOLOv11 резултатът се подава на Claude като текст
                    enhanced_prompt = (
                        f"{prompt}\n\n"
                        f"[{st.session_state.yolo_result}]\n"
                        f"Използвай горния YOLOv11 анализ като основа и дай агрономска "
                        f"интерпретация и препоръка за действие."
                    )
                    messages_to_send = st.session_state.messages[:-1] + [
                        {"role": "user", "content": enhanced_prompt}
                    ]
                    response, used_model = chat(
                        messages_to_send,
                        image_data=None,
                        force_model=MODEL_HAIKU,
                        temp_photo_filename=st.session_state.temp_photo_filename,
                    )
                else:
                    # Текстов въпрос без снимка
                    response, used_model = chat(
                        st.session_state.messages,
                        image_data=None,
                        force_model=MODEL_HAIKU,
                        temp_photo_filename=None,
                    )

                st.markdown(response)
                model_label = "Haiku" if "haiku" in used_model else "Sonnet"
                st.caption(f"Модел: {model_label}")
                st.session_state.messages.append({"role": "assistant", "content": response})
                success = True

            except Exception as e:
                err = str(e)
                if "rate_limit" in err:
                    st.warning("Достигнат е лимитът на заявките. Изчакай 1 минута и опитай отново.")
                else:
                    st.error(f"Грешка: {err}")
                    st.error("Виж черния прозорец на терминала за повече детайли.")

    if success:
        # Нулираме снимката САМО ако агентът я е архивирал
        # (временният файл вече не е в 07_Photos/{year}/)
        if st.session_state.temp_photo_filename:
            temp_path = (
                PHOTOS_BASE_PATH
                / str(date.today().year)
                / st.session_state.temp_photo_filename
            )
            if not temp_path.exists():
                st.session_state.temp_photo_filename = None
                st.session_state.yolo_result = None
        st.rerun()
