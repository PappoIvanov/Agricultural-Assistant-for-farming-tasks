import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from tools import get_planned_sprays, get_weather, send_telegram

load_dotenv()

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WIND_LIMIT = 4.0
RAIN_LIMIT = 0.0


def send_message(chat_id: str, text: str):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def check_conditions(parcel: str, target_date: str) -> dict:
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


def handle_check(chat_id: str):
    result = get_planned_sprays(days_ahead=3)
    sprays = result.get("sprays", [])

    if not sprays:
        send_message(chat_id, "🌹 Няма планирани пръскания за следващите 3 дни.")
        return

    lines = ["🌹 <b>Агро Асистент — Проверка</b>", ""]

    for spray in sprays:
        target_date = spray["planned_date"]
        parcel = spray["parcel"]
        products = spray.get("products", [])
        products_str = "\n".join(
            f"  • {p['name']} — {p.get('dose', '?')}" for p in products
        )
        cond = check_conditions(parcel, target_date)

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


@app.route(f"/webhook", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})
    text = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if text == "/проверка" or text == "/check":
        handle_check(chat_id)
    elif text == "/start":
        send_message(chat_id, "🌹 <b>Агро Асистент</b>\nНапиши /проверка за да видиш планираните пръскания и прогнозата.")

    return "ok", 200


@app.route("/")
def index():
    return "Agro Assistant Bot is running.", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
