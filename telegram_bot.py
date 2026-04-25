"""
Telegram бот за Агро Асистент — Маслодайна Роза.

Команди:
  /start      — поздрав и помощ
  /проверка   — планирани пръскания + метеоусловия
  /помощ      — всички команди

Снимки:
  Анализират се локално с YOLOv11 (без Claude API разходи).
  Снимката се записва автоматично в правилната категория:
    diseases / pests / weeds / healthy
  Ако не посочиш парцела, ботът ще те попита.

Текстови въпроси:
  Всеки текст се предава директно на агента (Claude).

Категории (управлявани от YOLOv11 модела):
  diseases  — болести по растението (Black Spot, Downy Mildew, Powdery Mildew)
  pests     — насекоми и неприятели (ще се добави при следваща версия на модела)
  weeds     — плевели (ще се добави при следваща версия на модела)
  healthy   — здраво растение (по подразбиране при липса на открити проблеми)
"""

import os
import base64
import tempfile
import requests
from pathlib import Path
from flask import Flask, request
from dotenv import load_dotenv
from agent import chat as agent_chat
from tools import get_planned_sprays, get_weather, save_photo_archive

load_dotenv()

app = Flask(__name__)
TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WIND_LIMIT = 4.0   # м/с
RAIN_LIMIT = 0.0   # мм

# ---------------------------------------------------------------------------
# YOLOv11 модел — сваля се автоматично от Hugging Face ако липсва
# ---------------------------------------------------------------------------

HF_MODEL_URL = "https://huggingface.co/p7ivanov/rose-disease-detection/resolve/main/best_v1.pt"
MODEL_PATH   = Path("08_AI_Model/models/trained/best_v1.pt")


def _ensure_model() -> bool:
    """Проверява дали моделът съществува. Ако не — го сваля от Hugging Face.
    Връща True при успех, False при грешка."""
    if MODEL_PATH.exists():
        return True
    try:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Свалям модела от Hugging Face...")
        r = requests.get(HF_MODEL_URL, timeout=120, stream=True)
        r.raise_for_status()
        with open(MODEL_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Моделът е свален успешно: {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"Грешка при сваляне на модела: {e}")
        return False

# ---------------------------------------------------------------------------
# Памет за снимки, чакащи отговор "от кой парцел?"
# chat_id → {"photo_b64": str, "media_type": str, "caption": str}
# ---------------------------------------------------------------------------
_pending_photos: dict = {}


# ---------------------------------------------------------------------------
# Помощни функции
# ---------------------------------------------------------------------------

def send_message(chat_id: str, text: str) -> None:
    """Изпраща текстово съобщение."""
    if len(text) > 4096:
        text = text[:4050] + "\n\n[...съобщението е съкратено до 4096 знака]"
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def _extract_parcel(text: str) -> str | None:
    """Открива споменат парцел в текст. Връща 'Парцел 1', 'Парцел 2' или None."""
    t = (text or "").lower()
    if "парцел 1" in t or "парцел1" in t:
        return "Парцел 1"
    if "парцел 2" in t or "парцел2" in t:
        return "Парцел 2"
    return None


def _download_photo(file_id: str) -> tuple[str, str]:
    """Сваля снимка от Telegram по file_id.
    Връща (base64_string, media_type).
    """
    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=10,
    )
    file_path = r.json()["result"]["file_path"]
    photo_r = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_path}",
        timeout=30,
    )
    return base64.standard_b64encode(photo_r.content).decode(), "image/jpeg"


def _yolo_category(detections: list) -> str:
    """Определя категорията на снимката по резултата от YOLOv11.

    Текущи класове на модела (rose_v1):
      Black Spot, Downy Mildew, Powdery Mildew → diseases
      Normal                                   → healthy

    Бъдещи класове (при нова версия на модела):
      aphid, spider_mite, thrips, ...          → pests
      weed, thistle, ...                       → weeds
    """
    DISEASE_CLASSES = {"black spot", "downy mildew", "powdery mildew"}
    PEST_CLASSES    = set()   # ← попълва се при следваща версия на модела
    WEED_CLASSES    = set()   # ← попълва се при следваща версия на модела

    names = {d.lower() for d in detections}
    if names & DISEASE_CLASSES:
        return "diseases"
    if names & PEST_CLASSES:
        return "pests"
    if names & WEED_CLASSES:
        return "weeds"
    return "healthy"


def _analyze_photo(
    chat_id: str,
    photo_b64: str,
    media_type: str,
    parcel: str,
    caption: str = "",
) -> None:
    """Анализира снимката с YOLOv11, записва я в правилната категория
    и връща резултата в Telegram. Не използва Claude API."""

    send_message(chat_id, "🔍 Анализирам снимката...")

    try:
        from ultralytics import YOLO
        import base64 as _b64

        # Проверяваме дали моделът съществува — ако не, го сваляме от Hugging Face
        if not _ensure_model():
            send_message(chat_id, "⚠️ Моделът не може да се свали. Провери интернет връзката.")
            return
        model_path = MODEL_PATH

        # Записваме base64 снимката във временен файл
        ext = media_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(_b64.b64decode(photo_b64))
            tmp_path = tmp.name

        # YOLOv11 анализ
        model   = YOLO(str(model_path))
        results = model.predict(tmp_path, conf=0.25, verbose=False)
        os.unlink(tmp_path)   # изтриваме временния файл

        # Извличаме засечените класове
        detections = []
        for r in results:
            for box in r.boxes:
                cls_name = model.names[int(box.cls[0])]
                conf     = float(box.conf[0])
                if cls_name.lower() != "normal":
                    detections.append((cls_name, conf))

        # Определяме категорията
        category = _yolo_category([d[0] for d in detections])

        # Записваме снимката в правилната папка
        import base64 as _b64
        from datetime import datetime, date
        from tools import PHOTOS_BASE_PATH
        year      = date.today().year
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_name = f"temp_{timestamp}.{ext}"
        temp_dir  = PHOTOS_BASE_PATH / str(year)
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / temp_name).write_bytes(_b64.b64decode(photo_b64))

        result = save_photo_archive(temp_name, parcel, category)

        # Съставяме отговора
        if not detections:
            msg = (
                f"✅ <b>Здраво растение</b>\n"
                f"Парцел: {parcel}\n"
                f"Не са открити болести, неприятели или плевели.\n"
                f"Снимката е запазена в: <i>healthy/{year}/</i>"
            )
        else:
            lines = [f"⚠️ <b>Открити проблеми — {parcel}</b>\n"]
            for cls_name, conf in detections:
                lines.append(f"  • {cls_name} — {conf:.0%} увереност")
            lines.append(f"\nСнимката е запазена в: <i>{category}/{year}/</i>")
            msg = "\n".join(lines)

        send_message(chat_id, msg)

    except Exception as e:
        send_message(chat_id, f"⚠️ Грешка при анализа: {e}")


# ---------------------------------------------------------------------------
# Обработка на команда /проверка
# ---------------------------------------------------------------------------

def _check_conditions(parcel: str, target_date: str) -> dict:
    weather = get_weather(parcel)
    if "error" in weather:
        return {"ok": False, "reason": weather["error"]}
    for day in weather["forecast"]:
        if day["date"] == target_date:
            wind = day["wind_max"]
            rain = day["precip"]
            if wind > WIND_LIMIT:
                return {"ok": False, "reason": f"силен вятър {wind} м/с (макс. {WIND_LIMIT})"}
            if rain > RAIN_LIMIT:
                return {"ok": False, "reason": f"валежи {rain} мм"}
            return {"ok": True, "wind": wind, "rain": rain}
    return {"ok": False, "reason": "датата не е в прогнозата (само 7 дни напред)"}


def handle_check(chat_id: str) -> None:
    result = get_planned_sprays(days_ahead=5)
    sprays = result.get("sprays", [])

    if not sprays:
        send_message(chat_id, "🌹 Няма планирани пръскания за следващите 5 дни.")
        return

    lines = ["🌹 <b>Агро Асистент — Проверка</b>", ""]

    for spray in sprays:
        target_date = spray["planned_date"]
        parcel      = spray["parcel"]
        products    = spray.get("products", [])
        products_str = "\n".join(
            f"  • {p['name']} — {p.get('dose', '?')}"
            + (f" (общо: {p['amount']})" if p.get("amount") else "")
            for p in products
        )
        cond = _check_conditions(parcel, target_date)

        if cond["ok"]:
            lines.append(f"✅ <b>{target_date} — {parcel}</b>")
            lines.append(f"Условията позволяват пръскане")
            lines.append(f"Вятър: {cond['wind']} м/с | Валежи: {cond['rain']} мм")
        else:
            lines.append(f"⛔ <b>{target_date} — {parcel}</b>")
            lines.append(f"Пръскането трябва да се отложи")
            lines.append(f"Причина: {cond['reason']}")

        lines.append(f"Препарати:\n{products_str}")
        lines.append(f"Разтвор: {spray['volume_liters']} л | Дюзи: {spray['nozzle_count']}")
        if spray.get("notes"):
            lines.append(f"Бележка: {spray['notes']}")
        lines.append("")

    send_message(chat_id, "\n".join(lines))


# ---------------------------------------------------------------------------
# Главен webhook
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    data    = request.json or {}
    message = data.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()
    caption = message.get("caption", "").strip()
    photos  = message.get("photo", [])

    # Сигурност — само от конфигурирания потребител
    if chat_id != CHAT_ID:
        return "ok", 200

    # ── Команди ──────────────────────────────────────────────────────────
    if text == "/start":
        send_message(chat_id, (
            "🌹 <b>Агро Асистент — Маслодайна Роза</b>\n\n"
            "Изпрати снимка за анализ или задай въпрос директно.\n\n"
            "/проверка — планирани пръскания + прогноза\n"
            "/помощ — всички команди"
        ))
        return "ok", 200

    if text in ("/проверка", "/check"):
        handle_check(chat_id)
        return "ok", 200

    if text == "/помощ":
        send_message(chat_id, (
            "🌹 <b>Команди:</b>\n\n"
            "/проверка — планирани пръскания + метеоусловия\n\n"
            "<b>Снимки:</b>\n"
            "Изпрати снимка с или без текст.\n"
            "Посочи парцела: <i>Парцел 1</i> или <i>Парцел 2</i>\n"
            "Ако не го посочиш, ще те попитам.\n\n"
            "<b>Въпроси:</b>\n"
            "Пиши директно — агентът ще отговори."
        ))
        return "ok", 200

    # ── Снимка ───────────────────────────────────────────────────────────
    if photos:
        # Вземаме версията с най-висока резолюция
        best = max(photos, key=lambda p: p.get("file_size", 0))
        file_id = best["file_id"]

        # Парцелът може да е в caption или в text (ако е изпратен отделно)
        parcel = _extract_parcel(caption) or _extract_parcel(text)

        try:
            photo_b64, media_type = _download_photo(file_id)
        except Exception as e:
            send_message(chat_id, f"⚠️ Не мога да изтегля снимката: {e}")
            return "ok", 200

        if parcel:
            # Парцелът е известен — директен анализ
            _analyze_photo(chat_id, photo_b64, media_type, parcel, caption)
        else:
            # Запазваме снимката и питаме за парцела
            _pending_photos[chat_id] = {
                "photo_b64":  photo_b64,
                "media_type": media_type,
                "caption":    caption,
            }
            send_message(chat_id, (
                "📍 <b>От кой парцел е тази снимка?</b>\n\n"
                "Отговори с: <b>Парцел 1</b> или <b>Парцел 2</b>"
            ))

        return "ok", 200

    # ── Отговор с парцел за чакаща снимка ───────────────────────────────
    if chat_id in _pending_photos and text:
        parcel = _extract_parcel(text)
        if parcel:
            pending = _pending_photos.pop(chat_id)
            _analyze_photo(
                chat_id,
                pending["photo_b64"],
                pending["media_type"],
                parcel,
                pending["caption"],
            )
        else:
            send_message(
                chat_id,
                "Не разпознах парцела. Отговори с <b>Парцел 1</b> или <b>Парцел 2</b>."
            )
        return "ok", 200

    # ── Общ текстов въпрос към агента ────────────────────────────────────
    if text:
        messages = [{"role": "user", "content": text}]
        try:
            response, _ = agent_chat(messages)
            send_message(chat_id, response)
        except Exception as e:
            send_message(chat_id, f"⚠️ Грешка: {e}")

    return "ok", 200


@app.route("/")
def index():
    return "Agro Assistant Bot is running.", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
