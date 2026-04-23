"""
daily_advisor.py
----------------
Сутрешен съветник — НУЛЕВ РАЗХОД НА ТОКЕНИ.

Работи само с Python логика и Open-Meteo (безплатно).
Claude API не се вика. Резултатът се праща на Telegram.

Може да се пусне:
  - Ръчно: python daily_advisor.py
  - На Render като Cron Job (0 7 * * *) — работи 24/7 без компютър
"""

import os
import requests
from datetime import date, timedelta
from dotenv import load_dotenv
from tools import get_weather, read_spray_history, read_agro_history, get_planned_sprays

load_dotenv()

# ---------------------------------------------------------------------------
# Константи
# ---------------------------------------------------------------------------

WIND_LIMIT_MS   = 4.0   # м/с — над това не се пръска
RAIN_LIMIT_MM   = 1.0   # мм — над това не се пръска
SPRAY_WARN_DAYS = 18    # дни без пръскане → напомняне
AGRO_WARN_DAYS  = 21    # дни без агротехника → напомняне


# ---------------------------------------------------------------------------
# Фенофаза (без API)
# ---------------------------------------------------------------------------

def phenophase(today: date) -> tuple[str, str]:
    """Връща (кратко описание, препоръчани операции) за текущия месец."""
    m = today.month
    if m in (1, 2):
        return (
            "Зимен покой",
            "Нищо по растенията. Подходящо за поддръжка на техниката и планиране."
        )
    elif m == 3:
        return (
            "Начало на вегетация — набъбване на пъпки",
            "Ранно профилактично пръскане (минерално масло / меден хидроксид). Плитка обработка на почвата."
        )
    elif m == 4:
        return (
            "Активен растеж — разлистване, формиране на бутони",
            "Профилактика срещу ръжда и брашнеста мана. Обработка на почвата 1-2 пъти. СПРИ пръскането 14-21 дни преди цъфтеж!"
        )
    elif m == 5:
        return (
            "⚠️ ЦЪФТЕЖ — АБСОЛЮТНА ЗАБРАНА ЗА ПРЪСКАНЕ",
            "Само ръчна плевене. Без никакви пръскания с препарати!"
        )
    elif m == 6:
        return (
            "След цъфтеж — развитие на леторасти",
            "Дълбока обработка на почвата. Торене NPK след беритбата. Контрол на болести ако е нужно."
        )
    elif m in (7, 8):
        return (
            "Лятно полупокойно — узряване",
            "Плевене при нужда. Следи за акари при горещо и сухо."
        )
    elif m in (9, 10):
        return (
            "Есенен растеж — подготовка за зима",
            "Есенни торове (суперфосфат, калий). Дълбоко изораване октомври. Последни профилактични пръскания ако е нужно."
        )
    else:
        return (
            "Залежаване / зимен покой",
            "Поддръжка на техниката. Планиране за следващия сезон."
        )


# ---------------------------------------------------------------------------
# Анализ на времето (без API — само парсване на вече извлечени данни)
# ---------------------------------------------------------------------------

def analyse_weather(parcel_name: str, today: date) -> dict:
    """Анализира прогнозата и връща структуриран резултат."""
    weather = get_weather(parcel_name)
    if "error" in weather:
        return {"ok": False, "error": weather["error"], "spray_days": [], "forecast": []}

    forecast = weather.get("forecast", [])
    spray_days = []
    warnings = []

    for day in forecast:
        d = date.fromisoformat(day["date"])
        if d < today or d > today + timedelta(days=5):
            continue
        wind = day.get("wind_max", 0)
        rain = day.get("precip", 0)
        temp_max = day.get("temp_max", 0)
        suitable = wind <= WIND_LIMIT_MS and rain <= RAIN_LIMIT_MM
        if suitable:
            spray_days.append(d.strftime("%d.%m (%A)").replace(
                "Monday","Пон").replace("Tuesday","Вт").replace(
                "Wednesday","Ср").replace("Thursday","Чет").replace(
                "Friday","Пет").replace("Saturday","Съб").replace("Sunday","Нед"))
        if wind > WIND_LIMIT_MS:
            warnings.append(f"{d.strftime('%d.%m')}: силен вятър {wind:.1f} м/с")
        if rain > RAIN_LIMIT_MM:
            warnings.append(f"{d.strftime('%d.%m')}: валежи {rain:.1f} мм")

    return {
        "ok": True,
        "spray_days": spray_days,
        "warnings": warnings,
        "forecast": forecast[:5],
    }


# ---------------------------------------------------------------------------
# Проверка на историята (без API)
# ---------------------------------------------------------------------------

def days_since_last(history_entries: list, keyword: str = None) -> int | None:
    """Връща броя дни от последния запис. None ако няма записи."""
    if not history_entries:
        return None
    last_entry = history_entries[-1]
    # Търси дата в формат YYYY-MM-DD в текста
    import re
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", last_entry)
    if not dates:
        return None
    try:
        last_date = date.fromisoformat(dates[0])
        return (date.today() - last_date).days
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Изграждане на съобщението
# ---------------------------------------------------------------------------

def build_message(today: date) -> str:
    lines = [f"<b>🌹 Агро Асистент — {today.strftime('%d.%m.%Y')}</b>", ""]

    # Фенофаза
    phase, phase_advice = phenophase(today)
    lines.append(f"<b>Фенофаза:</b> {phase}")
    lines.append(f"<i>{phase_advice}</i>")
    lines.append("")

    # Планирани пръскания
    planned = get_planned_sprays(days_ahead=5).get("sprays", [])
    if planned:
        lines.append("<b>📋 Планирани пръскания (следващите 5 дни):</b>")
        for s in planned:
            prods = ", ".join(p["name"] for p in s.get("products", []))
            lines.append(f"  • {s['planned_date']} — {s['parcel']}: {prods}")
        lines.append("")

    # Времето и анализ за всеки парцел
    for parcel_name in ["Парцел 1", "Парцел 2"]:
        lines.append(f"<b>🌤 {parcel_name}:</b>")
        w = analyse_weather(parcel_name, today)

        if not w["ok"]:
            lines.append(f"  ⚠️ {w['error']}")
        else:
            if w["spray_days"]:
                days_str = ", ".join(w["spray_days"])
                lines.append(f"  ✅ Подходящи дни за пръскане: {days_str}")
            else:
                lines.append("  ⛔ Няма подходящи дни за пръскане тази седмица")

            if w["warnings"]:
                for warn in w["warnings"]:
                    lines.append(f"  ⚠️ {warn}")

        lines.append("")

    # Напомняния от историята
    reminders = []

    spray_hist = read_spray_history(limit=5).get("entries", [])
    days_spray = days_since_last(spray_hist)
    if days_spray is None:
        reminders.append("Няма записани пръскания. Провери дали дневникът е актуален.")
    elif days_spray > SPRAY_WARN_DAYS and today.month not in (5,):
        reminders.append(f"Последното пръскане е преди {days_spray} дни. Провери дали е нужно профилактично третиране.")

    agro_hist = read_agro_history(limit=5).get("entries", [])
    days_agro = days_since_last(agro_hist)
    if days_agro is None:
        reminders.append("Няма записани агротехнически операции.")
    elif days_agro > AGRO_WARN_DAYS:
        reminders.append(f"Последната агротехническа операция е преди {days_agro} дни. Нужна ли е обработка на почвата?")

    # Специални предупреждения по месец
    if today.month == 4 and today.day >= 20:
        reminders.append("⚠️ Наближава цъфтеж! Спри всички пръскания 14-21 дни преди него.")
    if today.month == 5:
        reminders.append("🚫 МАЙ — ЗАБРАНЕНО ПРЪСКАНЕ. Само ръчна плевене.")

    if reminders:
        lines.append("<b>📌 Напомняния:</b>")
        for r in reminders:
            lines.append(f"  • {r}")
        lines.append("")

    lines.append("<i>За подробен анализ или диагноза — пиши на агента в Streamlit.</i>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Изпращане на Telegram
# ---------------------------------------------------------------------------

def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ГРЕШКА] Липсват TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в .env")
        return
    if len(message) > 4000:
        message = message[:4000] + "\n[съкратено]"
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )
    if r.ok:
        print("[OK] Изпратено на Telegram.")
    else:
        print(f"[ГРЕШКА] {r.text}")


# ---------------------------------------------------------------------------
# Главна функция
# ---------------------------------------------------------------------------

def main():
    today = date.today()
    print(f"[{today}] Генерирам сутрешна справка (без Claude API)...")
    msg = build_message(today)
    print("\n--- СЪОБЩЕНИЕ ---")
    print(msg)
    print("-----------------\n")
    send_telegram(msg)


if __name__ == "__main__":
    main()
