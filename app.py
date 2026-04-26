import os
import re
import tempfile
import streamlit as st
import base64
from datetime import date
from pathlib import Path
from agent import chat, MODEL_HAIKU, MODEL_SONNET
from tools import save_temp_photo, save_photo_archive, PHOTOS_BASE_PATH

# Увери се, че работната директория е папката на проекта
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Път до YOLOv11 модела — дефиниран преди всичко друго
MODEL_PATH = Path("08_AI_Model/models/trained/best_v1.pt")


def _extract_parcel(text: str) -> str | None:
    """Извлича 'Парцел 1' или 'Парцел 2' от текст на потребителя."""
    m = re.search(r'парцел\s*([12])', text.lower())
    return f"Парцел {m.group(1)}" if m else None


def _category_from_yolo(yolo_result: str) -> str:
    """Определя категорията от текстовия резултат на YOLOv11.
    Текущи класове: Black Spot / Downy Mildew / Powdery Mildew → diseases; Normal → healthy.
    """
    if not yolo_result or "Не са открити" in yolo_result:
        return "healthy"
    text_lower = yolo_result.lower()
    if any(c in text_lower for c in ["black spot", "downy mildew", "powdery mildew"]):
        return "diseases"
    if any(c in text_lower for c in ["pest", "aphid", "spider mite", "insect"]):
        return "pests"
    if any(c in text_lower for c in ["weed", "плевел"]):
        return "weeds"
    if "normal" in text_lower:
        return "healthy"
    return "diseases"


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

    # Debug панел
    with st.expander("Debug — текущо състояние"):
        st.json({
            "temp_photo_filename": st.session_state.get("temp_photo_filename"),
            "parcel_name":         st.session_state.get("parcel_name"),
            "yolo_result":         st.session_state.get("yolo_result"),
            "messages_count":      len(st.session_state.get("messages", [])),
        })

# ---------------------------------------------------------------------------
# Session state — запазва данните между rerun-ите
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "temp_photo_filename" not in st.session_state:
    st.session_state.temp_photo_filename = None
if "yolo_result" not in st.session_state:
    st.session_state.yolo_result = None
if "parcel_name" not in st.session_state:
    st.session_state.parcel_name = None

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
# Upload на снимка
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

    # Записваме снимката временно и пускаме YOLOv11 само веднъж при ново качване
    if st.session_state.temp_photo_filename is None:
        st.session_state.parcel_name = None  # нова снимка → нулираме парцела
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

    # Питане за парцела — показва се докато не е посочен
    if st.session_state.temp_photo_filename and st.session_state.parcel_name is None:
        st.warning("Снимката от кой парцел е — Парцел 1 или Парцел 2?")

else:
    # Снимката е премахната — нулираме
    st.session_state.temp_photo_filename = None
    st.session_state.yolo_result = None
    st.session_state.parcel_name = None

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
        # Извличаме парцела от съобщението и го запазваме
        detected_parcel = _extract_parcel(prompt)
        if detected_parcel:
            st.session_state.parcel_name = detected_parcel

        # Fallback архивиране — ако агентът не е извикал save_photo_archive
        if st.session_state.temp_photo_filename and st.session_state.parcel_name:
            temp_path = (
                PHOTOS_BASE_PATH
                / str(date.today().year)
                / st.session_state.temp_photo_filename
            )
            if temp_path.exists():
                category = _category_from_yolo(st.session_state.yolo_result or "")
                result = save_photo_archive(
                    st.session_state.temp_photo_filename,
                    st.session_state.parcel_name,
                    category,
                )
                if result.get("status") == "ok":
                    st.toast(f"Снимката е запазена → {category}/{date.today().year}/{result['saved_as']}")

        # Нулираме след успешно архивиране
        if st.session_state.temp_photo_filename:
            temp_path = (
                PHOTOS_BASE_PATH
                / str(date.today().year)
                / st.session_state.temp_photo_filename
            )
            if not temp_path.exists():
                st.session_state.temp_photo_filename = None
                st.session_state.yolo_result = None
                st.session_state.parcel_name = None
        st.rerun()
