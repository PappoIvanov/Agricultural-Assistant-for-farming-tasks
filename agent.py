import os
import json
import anthropic
from dotenv import load_dotenv
from tools import (
    get_weather, save_spray_record, read_spray_history, calculate_concentration,
    list_literature, read_literature,
    read_diagnostic_diary, save_diagnostic_case,
    send_telegram, save_planned_spray, get_planned_sprays, complete_planned_spray,
    search_literature, save_agro_operation, read_agro_history,
    save_to_knowledge_base, save_photo_archive,
)


load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"

# Ключови думи, при които се минава на Sonnet
_COMPLEX_KEYWORDS = [
    "анализирай", "анализ", "сравни", "обясни подробно", "диагноза",
    "болест", "неприятел", "идентифицирай", "pdf", "документ", "доклад",
    "литература", "научна", "препоръчай стратегия", "дългосрочен",
]


def select_model(messages: list, image_data: dict = None) -> str:
    """Haiku по подразбиране; Sonnet при изображения, PDF или сложни заявки."""
    if image_data:
        return MODEL_SONNET
    last_text = messages[-1].get("content", "").lower() if messages else ""
    if any(kw in last_text for kw in _COMPLEX_KEYWORDS):
        return MODEL_SONNET
    # Дълги съобщения — вероятно сложен контекст
    if len(last_text) > 600:
        return MODEL_SONNET
    return MODEL_HAIKU

from datetime import date as _date

_current_year = _date.today().year
_current_date = _date.today().isoformat()

SYSTEM_PROMPT = f"""Ти си агро асистент за стопанство с маслодайна роза (Rosa damascena) в България.
Помагаш на стопанина да води дневник на пръсканията, да изчислява концентрации на препарати,
да следи метеорологичните условия и да взима решения кога и с какво да пръска.

Стопанство:
- Култура: Маслодайна роза (Rosa damascena)
- Парцел 1: 10 дка
- Парцел 2: 2 дка
- Обща площ: 12 дка
- Важно: По време на цъфтеж (май) — абсолютна забрана за пръскане!

Трактори и техника:
- Т-25 (Д-21, 20 к.с.): пръска на III предавка = 8.37 км/ч, ВОМ 545 об/мин
- ЮМЗ-6КЛ/КМ (Д-65, 62 к.с.): пръска на II предавка без редуктор = 9.0 км/ч, ВОМ 540 об/мин
- Дюзи: зелени Lechler TR 80-015 (0.46 л/мин при 2 бара) и жълти TR 80-02 (0.62 л/мин при 2 бара)

Правила за дати:
- Днешна дата: {_current_date}. Текуща година: {_current_year}.
- Ако потребителят напише само "25.04" или "25.04.25", интерпретирай като {_current_year}-04-25.
- Никога не записвай планирано пръскане с минала дата — върни грешка и поискай бъдеща дата.

Фенологичен календар на Rosa damascena (България):
- Януари–февруари: зимен покой, без листа
- Март: начало на вегетация, набъбване на пъпки
- Април: активен вегетативен растеж, разлистване, формиране на бутони
- Май: цъфтеж — АБСОЛЮТНА ЗАБРАНА ЗА ПРЪСКАНЕ
- Юни: след цъфтеж, развитие на леторасти, зреене на плодове
- Юли–август: лятно полупокойно състояние, узряване
- Септември–октомври: есенен растеж, подготовка за зима
- Ноември–декември: залежаване, зимен покой
Използвай този календар за да определяш фенофазата автоматично по дата, без да питаш потребителя.

Правила за препарати:
- Цялата литература се намира в папка: 05_Литература/
- За търсене в документи използвай search_literature(query) — връща само релевантните части, без да чете целия файл.
- За избор на препарати използвай search_literature с ключови думи от типа "роза разрешен", "декоративна роза", "Rosa damascena". БАБХ документите използват "декоративна роза" или "Rosa damascena" — не "маслодайна роза". Ако първото търсене не даде резултат, опитай с друг синоним.
- Никога не назовавай болест или вредител без да си проверил името в литературата с search_literature. Ако не намериш — кажи изрично че не си сигурен.
- read_literature използвай само за малки файлове (под 50 кб) — за големи PDF и DOCX винаги използвай search_literature.
- Никога не препоръчвай препарат без да си проверил дали е разрешен.

Правила за поведение:
- Не показвай вътрешното си мислене — не коментирай четенето на файлове, извикването на инструменти или затрудненията си. Показвай само крайния резултат.
- Пиши само на правилен, стандартен книжовен български език. Никога не смесвай езици.
- Ако не си сигурен в нещо — кажи го изрично. Никога не измисляй факти, имена на болести, вредители или препарати.
- Задавай уточняващи въпроси когато информацията е недостатъчна за точен отговор.
- Когато потребителят описва симптоми или качва снимка — ПЪРВО извикай read_diagnostic_diary, след това анализирай.
- Ако в дневника има подобен минал случай — споменай го изрично.
- Когато поставяш диагноза — запиши случая с save_diagnostic_case.
- Когато потребителят каже че диагнозата е грешна — обнови записа с корекцията.
- Когато питат за концентрация — използвай calculate_concentration.
- Когато питат за времето — използвай get_weather.
- Когато питат за файл от литературата — използвай list_literature и read_literature.
- Когато потребителят казва че планира пръскане на дадена дата — ако не е споменал трактор, ЗАДЪЛЖИТЕЛНО първо питай: "С кой трактор ще пръскаш — Т-25 или ЮМЗ-6?". След като знаеш трактора, изчисли общото количество за всеки препарат с calculate_concentration(dose_per_dka, area_dka, volume_liters), след което покажи резюме: дата, парцел, трактор, предавка и скорост, препарати с дози и изчислени общи количества, литри разтвор, брой дюзи. Изчакай изричното потвърждение ("да", "запиши", "добре") преди да извикаш save_planned_spray. Никога не записвай без потвърждение.
- Когато питат за предстоящи пръскания — използвай get_planned_sprays.
- Когато потребителят съобщава за извършена агротехническа операция (дискуване, култивиране, фрезоване, резитба, торене, поливане) — запиши с save_agro_operation.
- Когато питат кога да извършат следваща агротехническа операция — ПЪРВО прочети историята с read_agro_history, след това провери времето с get_weather, и препоръчай конкретна дата като вземеш предвид: изминалото време, прогнозата (мокра почва не се обработва), сезона и фенофазата. Ако е прикачена снимка — анализирай покритието с плевели.
- Когато потребителят казва че е напръскал по план — първо извикай get_planned_sprays, намери записа по парцел и дата, маркирай го с complete_planned_spray(spray_id), след това запиши в дневника с save_spray_record.
Правила за снимки:
- Когато потребителят качи снимка: ВЕДНАГА прочети диагностичния дневник с read_diagnostic_diary.
- Ако потребителят НЕ Е споменал парцела в съобщението → попитай "Снимката от кой парцел е?" и изчакай отговора преди да анализираш.
- Ако парцелът е споменат (в текста ИЛИ в системния контекст на снимката) → не питай, директно анализирай.
- След анализа задължително: (1) запиши наблюдението с save_to_knowledge_base — включи парцел, дата, симптоми; (2) запиши диагнозата с save_diagnostic_case; (3) извикай save_photo_archive(temp_filename, parcel_name, category) където category се определя от ПРЕОБЛАДАВАЩИЯ резултат по сумарен процент на увереност от YOLOv11: сумирай процентите на всички засечени обекти по категория (diseases/pests/weeds) и избери тази с най-висок общ процент. Ако нищо не е засечено или YOLOv11 е върнал само здраво растение — category='healthy'. Пример: засечени 45% болест + 30% плевели → category='diseases'.
- В отговора ясно посочи: какво виждаш → диагноза → какво е записано → потвърди запазената снимка.
- Когато анализираш снимка и установиш конкретно: болест, неприятел, степен на нападение, или ново наблюдение — запиши го в базата знания с save_to_knowledge_base. Заглавие: "Наблюдение [дата]: [какво]". Записвай само конкретни факти, не предположения.
- Когато search_literature върне информация, която е нова и важна и НЕ е в текущата база знания — запиши я с save_to_knowledge_base. Не записвай дублирана информация.
- Когато потребителят потвърди диагноза или сподели резултат от предишно третиране — запиши го с save_to_knowledge_base като "Потвърдено наблюдение".

Отговаряй на български. Бъди конкретен и практичен."""

TOOLS = [
    {
        "name": "get_weather",
        "description": "Връща 7-дневна прогноза за даден парцел.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string", "description": "Парцел 1 или Парцел 2"},
            },
            "required": ["parcel_name"],
        },
    },
    {
        "name": "save_spray_record",
        "description": "Записва пръскане в работния дневник.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel": {"type": "string"},
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "dose": {"type": "string"},
                            "amount": {"type": "string"},
                        },
                    },
                },
                "volume_liters": {"type": "number"},
                "nozzle_count": {"type": "integer"},
                "notes": {"type": "string"},
                "record_date": {"type": "string"},
            },
            "required": ["parcel", "products", "volume_liters", "nozzle_count"],
        },
    },
    {
        "name": "read_spray_history",
        "description": "Чете последните записи от дневника.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "calculate_concentration",
        "description": "Изчислява количеството препарат спрямо площ, работен разтвор и корекция за редови насаждения.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dose_per_dka": {"type": "number", "description": "Доза мл/дка от етикета"},
                "area_dka": {"type": "number", "description": "Площ в декари"},
                "volume_liters": {"type": "number", "description": "Работен разтвор в литри"},
                "row_spacing_m": {"type": "number"},
                "canopy_width_m": {"type": "number"},
            },
            "required": ["dose_per_dka", "area_dka", "volume_liters"],
        },
    },
        {
        "name": "list_literature",
        "description": "Показва всички налични файлове в папката с литература (05_Литература/).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "read_literature",
        "description": "Чете съдържанието на файл от папката с литература. Поддържа .txt, .md, .pdf, .docx.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Името на файла, напр. 'Болести_Роза.pdf'",
                },
            },
            "required": ["filename"],
        },
    },
        {
        "name": "read_diagnostic_diary",
        "description": "Чете диагностичния дневник с минали случаи, диагнози и корекции. Извиквай го ПРЕДИ анализ на симптоми или снимки.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "save_diagnostic_case",
        "description": "Записва случай на симптоми и диагноза в дневника. Използвай когато потребителят описва проблем или потвърждава/коригира диагноза.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symptoms": {"type": "string", "description": "Описание на симптомите"},
                "initial_diagnosis": {"type": "string", "description": "Предложената диагноза"},
                "correction": {"type": "string", "description": "Корекция от потребителя ако има"},
                "action_taken": {"type": "string", "description": "Какво е предприето — пръскане, торене и т.н."},
                "outcome": {"type": "string", "description": "Резултат след действието"},
                "case_date": {"type": "string"},
            },
            "required": ["symptoms", "initial_diagnosis"],
        },
    },
        {
        "name": "send_telegram",
        "description": "Изпраща Telegram съобщение до стопанина. Използвай при важни препоръки, напомняния за пръскане или предупреждения за времето.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Текстът на съобщението"},
            },
            "required": ["message"],
        },
    },
        {
        "name": "save_planned_spray",
        "description": "Записва планирано бъдещо пръскане с дата, поле и препарати.",
        "input_schema": {
            "type": "object",
            "properties": {
                "planned_date": {"type": "string", "description": "Дата във формат YYYY-MM-DD"},
                "parcel": {"type": "string"},
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "dose": {"type": "string"},
                            "amount": {"type": "string", "description": "Общо количество за цялото пръскане, напр. '300 мл'"},
                        },
                    },
                },
                "volume_liters": {"type": "number"},
                "nozzle_count": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": ["planned_date", "parcel", "products", "volume_liters", "nozzle_count"],
        },
    },
    {
        "name": "get_planned_sprays",
        "description": "Връща планираните пръскания за следващите N дни.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Брой дни напред (по подразбиране 3)"},
            },
        },
    },
    {
        "name": "complete_planned_spray",
        "description": "Маркира планирано пръскане като изпълнено. Извиквай след като потребителят потвърди че е напръскал.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spray_id": {"type": "integer", "description": "ID на записа от get_planned_sprays"},
            },
            "required": ["spray_id"],
        },
    },
    {
        "name": "save_agro_operation",
        "description": "Записва агротехническа операция — дискуване, култивиране, фрезоване, резитба, торене, поливане и др.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation_type": {"type": "string", "description": "Вид операция: дискуване, култивиране, фрезоване, резитба, торене, поливане и др."},
                "parcel": {"type": "string"},
                "notes": {"type": "string"},
                "equipment": {"type": "string", "description": "Използвана машина или оборудване"},
                "record_date": {"type": "string", "description": "Дата YYYY-MM-DD, по подразбиране днес"},
            },
            "required": ["operation_type", "parcel"],
        },
    },
    {
        "name": "read_agro_history",
        "description": "Чете историята на агротехническите операции. Използвай преди да препоръчваш следваща операция.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel": {"type": "string"},
                "operation_type": {"type": "string", "description": "Филтрирай по вид операция"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "search_literature",
        "description": "Търси по ключови думи в литературата и връща само релевантните части. Използвай вместо read_literature за големи файлове.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Ключови думи за търсене, напр. 'хербицид маслодайна роза разрешен'"},
                "filename": {"type": "string", "description": "Конкретен файл за търсене (по избор). Ако не е зададен, търси във всички файлове."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_to_knowledge_base",
        "description": "Записва нова информация в базата знания. Използвай когато: (1) анализираш снимка и установиш нещо конкретно; (2) намериш важна нова информация в литературата; (3) потребителят сподели ново наблюдение или корекция.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Заглавие на записа, напр. 'Наблюдение: листни въшки на Парцел 1'"},
                "content": {"type": "string", "description": "Съдържанието — конкретни факти, прагове, симптоми, препоръки"},
                "source": {"type": "string", "description": "Източник — 'снимка от потребителя', 'литература: [файл]', 'наблюдение на място'"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "save_photo_archive",
        "description": "Преименува временно запазена снимка и я премества в правилната категория според анализа. Извиквай задължително след анализ на снимка.",
        "input_schema": {
            "type": "object",
            "properties": {
                "temp_filename": {
                    "type": "string",
                    "description": "Временното файлово ime от системния контекст, напр. 'temp_20260425_143022.jpg'",
                },
                "parcel_name": {
                    "type": "string",
                    "description": "Парцел 1 или Парцел 2",
                },
                "category": {
                    "type": "string",
                    "enum": ["diseases", "pests", "weeds", "healthy"],
                    "description": "Категория според анализа: 'diseases' — болести по растението, 'pests' — насекоми и неприятели, 'weeds' — плевели, 'healthy' — здраво растение без проблеми.",
                },
            },
            "required": ["temp_filename", "parcel_name", "category"],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "save_spray_record": save_spray_record,
    "read_spray_history": read_spray_history,
    "calculate_concentration": calculate_concentration,
    "list_literature": list_literature,
    "read_literature": read_literature,
    "read_diagnostic_diary": read_diagnostic_diary,
    "save_diagnostic_case": save_diagnostic_case,
    "send_telegram": send_telegram,
    "save_planned_spray": save_planned_spray,
    "get_planned_sprays": get_planned_sprays,
    "complete_planned_spray": complete_planned_spray,
    "search_literature": search_literature,
    "save_agro_operation": save_agro_operation,
    "read_agro_history": read_agro_history,
    "save_to_knowledge_base": save_to_knowledge_base,
    "save_photo_archive": save_photo_archive,
}


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    func = TOOL_FUNCTIONS.get(tool_name)
    if func:
        result = func(**tool_input)
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"error": f"Непознат инструмент: {tool_name}"})


def chat(
    messages: list,
    image_data: dict = None,
    force_model: str = None,
    temp_photo_filename: str = None,
) -> tuple[str, str]:
    """
    Изпраща съобщения към Claude и обработва tool use.
    messages: списък от {"role": "user"/"assistant", "content": "..."}
    image_data: {"base64": "...", "media_type": "image/jpeg"} ако има прикачена снимка
    force_model: MODEL_HAIKU или MODEL_SONNET — ако None, се избира автоматично
    temp_photo_filename: временното ime на запазената снимка — подава се невидимо на агента
    Връща (отговор, използван_модел).
    """
    model = force_model if force_model else select_model(messages, image_data)

    # Пази само последните 15 съобщения за да не се препълва контекстът
    MAX_HISTORY = 15
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]

    api_messages = []
    for msg in messages[:-1]:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    last = messages[-1]
    if image_data:
        # Добавяме temp_filename невидимо — не се записва в историята на чата
        photo_context = ""
        if temp_photo_filename:
            photo_context = (
                f"\n\n[СИСТЕМЕН КОНТЕКСТ: Снимката е временно запазена като: {temp_photo_filename}. "
                f"След като установиш от кой парцел е, извикай save_photo_archive('{temp_photo_filename}', parcel_name).]"
            )
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_data["media_type"],
                    "data": image_data["base64"],
                },
            },
            {"type": "text", "text": last["content"] + photo_context},
        ]
    else:
        if temp_photo_filename:
            content = (
                last["content"] +
                f"\n\n[СИСТЕМЕН КОНТЕКСТ: Снимката е временно запазена като: {temp_photo_filename}. "
                f"Това е снимка от полето анализирана с YOLOv11. "
                f"Ако не знаеш от кой парцел е — попитай. "
                f"След като знаеш парцела, извикай save_photo_archive('{temp_photo_filename}', parcel_name, category).]"
            )
        else:
            content = last["content"]

    api_messages.append({"role": "user", "content": content})

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=api_messages,
    )

    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = process_tool_call(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        api_messages.append({"role": "assistant", "content": response.content})
        api_messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=api_messages,
        )

    text = "".join(block.text for block in response.content if hasattr(block, "text"))
    return text, model
