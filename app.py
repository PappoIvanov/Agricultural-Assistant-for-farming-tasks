import os
import tempfile
import streamlit as st
import base64
from pathlib import Path
from agent import chat, MODEL_HAIKU, MODEL_SONNET
from tools import save_temp_photo

# Увери се, че работната директория е папката на проекта
os.chdir(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Агро Асистент — Маслодайна Роза",
    page_icon="🌹",
    layout="centered",
)

st.title("🌹 Агро Асистент — Маслодайна Роза")

with st.sidebar:
    st.header("Models which the agent uses")

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
    st.caption("Моделът се избира автоматично. Не е нужна ръчна настройка.")

# Запазваме _FORCE_MODEL за съвместимост с chat() функцията
_FORCE_MODEL = {
    "Авто": None,
    "Haiku (бърз)": MODEL_HAIKU,
    "Sonnet (прецизен)": MODEL_SONNET,
}
model_choice = "Авто"

# ---------------------------------------------------------------------------
# YOLOv11 — локален анализ на снимки
# ---------------------------------------------------------------------------

MODEL_PATH = Path("08_AI_Model/models/trained/best_v1.pt")

def _yolo_analyze(image_b64: str, media_type: str) -> str | None:
    """Анализира снимката с YOLOv11 локално.
    Връща текстов резултат за Claude или None ако моделът не е наличен.
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
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# История на разговора
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Прикачване на снимка
# ---------------------------------------------------------------------------

uploaded_file = st.file_uploader(
    "Прикачи снимка (по избор)",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
)

image_data          = None
temp_photo_filename = None
yolo_result         = None

if uploaded_file:
    image_bytes = uploaded_file.read()
    image_data  = {
        "base64":     base64.standard_b64encode(image_bytes).decode("utf-8"),
        "media_type": uploaded_file.type,
    }
    st.image(uploaded_file, width=300)

    # Записваме снимката временно
    try:
        temp_photo_filename = save_temp_photo(image_data["base64"], uploaded_file.type)
    except Exception as e:
        st.warning(f"Снимката не може да се запази временно: {e}")

    # YOLOv11 локален анализ — само ако моделът е наличен
    if MODEL_PATH.exists():
        with st.spinner("YOLOv11 анализира снимката..."):
            yolo_result = _yolo_analyze(image_data["base64"], uploaded_file.type)
        if yolo_result:
            st.info(yolo_result)
    else:
        st.error("YOLOv11 моделът не е намерен. Анализът на снимки не е наличен.")

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
                # Ако има YOLOv11 резултат — добавяме го към prompt-а
                # Claude получава текстовия резултат вместо да анализира снимката сам
                enhanced_prompt = prompt
                if yolo_result:
                    enhanced_prompt = (
                        f"{prompt}\n\n"
                        f"[{yolo_result}]\n"
                        f"Използвай горния YOLOv11 анализ като основа и дай агрономска интерпретация, "
                        f"препоръка за действие и запиши наблюдението."
                    )
                    # Не подаваме снимката на Claude — YOLOv11 вече я е анализирал
                    messages_to_send = st.session_state.messages[:-1] + [
                        {"role": "user", "content": enhanced_prompt}
                    ]
                    response, used_model = chat(
                        messages_to_send,
                        image_data=None,
                        force_model=MODEL_HAIKU,
                        temp_photo_filename=temp_photo_filename,
                    )
                else:
                    # Без YOLOv11 — само текстов въпрос, без анализ на снимка
                    response, used_model = chat(
                        st.session_state.messages,
                        image_data=None,
                        force_model=MODEL_HAIKU,
                        temp_photo_filename=temp_photo_filename,
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
        st.rerun()
                                                                                                                                                                    