"""
train.py — Стартира тренировката на YOLOv11 модел за болести по роза.

Използване (в Anaconda Prompt, среда agro_ml):
    conda activate agro_ml
    cd C:\\Users\\User\\Project_Claude\\08_AI_Model
    python scripts/train.py

Резултатите се записват автоматично в: runs/detect/rose_v1/
"""

from ultralytics import YOLO

# ── Конфигурация ──────────────────────────────────────────────────────────────

MODEL      = "yolo11n.pt"          # nano модел — добър старт (лек и бърз)
CONFIG     = "configs/rose_diseases.yaml"
EPOCHS     = 50                    # брой епохи — увеличи до 100 при добри резултати
IMG_SIZE   = 640                   # стандартен размер за YOLO
BATCH_SIZE = 8                     # намали до 4 ако паметта свърши
PROJECT    = "runs/detect"
NAME       = "rose_v1"             # папка с резултатите

# ── Тренировка ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    model = YOLO(MODEL)

    results = model.train(
        data      = CONFIG,
        epochs    = EPOCHS,
        imgsz     = IMG_SIZE,
        batch     = BATCH_SIZE,
        project   = PROJECT,
        name      = NAME,
        patience  = 20,            # спира рано ако няма подобрение
        save      = True,
        plots     = True,          # генерира графики на точността
    )

    print("\n✅ Тренировката завърши!")
    print(f"Резултати: {PROJECT}/{NAME}/")
