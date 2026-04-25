"""
Telegram бот за Агро Асистент — Маслодайна Роза.

Команди:
  /start      — поздрав и помощ
  /проверка   — планирани пръскания + метеоусловия
  /помощ      — всички команди

Снимки:
  Изпрати снимка (с или без текст).
  Ако не посочиш парцела, ботът ще те попита.
  Ботът анализира и отговаря с диагноза + препоръки.

Текстови въпроси:
  Всеки текст се предава директно на агента.
"""

import os
import base64
import requests
from flask import Flask, request
from dotenv import load_dotenv
from agent import chat as agent_chat
from tools import get_planned_sprays, get_weather

load_dotenv()

app = Flask(__name__)
TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WIND_LIMIT = 4.0   # м/с
RAIN_LIMIT = 0.0   # мм

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


def _analyze_photo(
    chat_id: str,
    photo_b64: str,
    media_type: str,
    parcel: str,
    caption: str = "",
) -> None:
    """Изпраща снимката към агента и връща анализа в Telegram."""
    user_text = caption.strip() if caption else "Анализирай тази снимка от стопанството."
    user_text += f" Снимката е от {parcel}."

    messages = [{"role": "user", "content": user_text}]
    image_data = {"base64": photo_b64, "media_type": media_type}

    send_message(chat_id, "🔍 Анализирам снимката, моля изчакай...")
    try:
        response, _ = agent_chat(messages, image_data=image_data)
        send_message(chat_id, response)
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
