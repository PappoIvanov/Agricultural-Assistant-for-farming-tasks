"""
predict.py — Тества обучения модел върху нова снимка.

Използване (в Anaconda Prompt, среда agro_ml):
    conda activate agro_ml
    cd C:\\Users\\User\\Project_Claude\\08_AI_Model
    python scripts/predict.py --image "път/до/снимката.jpg"

Резултатът се записва в: runs/detect/predict/
"""

import argparse
from pathlib import Path
from ultralytics import YOLO

# ── Конфигурация ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "models/trained/best.pt"   # най-добрият модел от тренировката
CONF_THRESHOLD = 0.25                       # минимална увереност за детекция

# ── Аргументи ─────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Детекция на болести по роза")
parser.add_argument("--image", required=True, help="Път до снимката")
parser.add_argument("--model", default=DEFAULT_MODEL, help="Път до .pt модел")
parser.add_argument("--conf",  default=CONF_THRESHOLD, type=float)
args = parser.parse_args()

# ── Предсказване ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"⚠️  Моделът не е намерен: {model_path}")
        print("Първо стартирай train.py или постави .pt файл в models/trained/")
        exit(1)

    model = YOLO(str(model_path))

    results = model.predict(
        source = args.image,
        conf   = args.conf,
        save   = True,
        project = "runs/detect",
        name    = "predict",
    )

    for r in results:
        boxes = r.boxes
        if len(boxes) == 0:
            print("Не са открити болести или неприятели.")
        else:
            print(f"\nОткрити: {len(boxes)} обект(а)")
            for box in boxes:
                cls_id = int(box.cls[0])
                conf   = float(box.conf[0])
                name   = model.names[cls_id]
                print(f"  • {name} — увереност: {conf:.1%}")
