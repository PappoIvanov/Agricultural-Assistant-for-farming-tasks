import os
import json
import requests
from datetime import date
from dotenv import load_dotenv
from tools import get_planned_sprays, get_weather

load_dotenv()

WIND_LIMIT = 4.0    # м/с
RAIN_LIMIT = 1.0    # мм

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


def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )


def main():
    result = get_planned_sprays(days_ahead=3)
    sprays = result.get("sprays", [])

    if not sprays:
        send_telegram("🌹 <b>Агро Асистент</b>\nНяма планирани пръскания за следващите 3 дни.")
        return

    lines = ["🌹 <b>Агро Асистент — Сутрешна проверка</b>", ""]

    for spray in sprays:
        target_date = spray["date"]
        parcel = spray["parcel"]
        products = ", ".join(p["name"] for p in spray["products"])
        cond = check_conditions(parcel, target_date)

        if cond["ok"]:
            lines.append(f"✅ <b>{target_date} — {parcel}</b>")
            lines.append(f"Условията позволяват пръскане")
            lines.append(f"Вятър: {cond['wind']} м/с | Валежи: {cond['rain']} мм")
        else:
            lines.append(f"⛔ <b>{target_date} — {parcel}</b>")
            lines.append(f"Пръскането трябва да се отложи — {cond['reason']}")

        lines.append(f"Препарати: {products}")
        if spray.get("notes"):
            lines.append(f"Бележка: {spray['notes']}")
        lines.append("")

    send_telegram("\n".join(lines))


if __name__ == "__main__":
    main()
