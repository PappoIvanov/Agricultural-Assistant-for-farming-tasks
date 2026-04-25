"""
prepare_dataset.py — Разделя снимките на train / val / test.

Копира снимки и анотации от datasets/personal/ и datasets/public/
в datasets/merged/ с разпределение 80% train / 10% val / 10% test.

Използване (в Anaconda Prompt, среда agro_ml):
    conda activate agro_ml
    cd C:\\Users\\User\\Project_Claude\\08_AI_Model
    python scripts/prepare_dataset.py

ВНИМАНИЕ: Скриптът не изтрива съществуващи файлове в merged/.
Изчисти merged/ ръчно ако искаш да започнеш отначало.
"""

import shutil
import random
from pathlib import Path

# ── Конфигурация ──────────────────────────────────────────────────────────────

SOURCES = [
    Path("datasets/personal"),
    Path("datasets/public"),
]
DEST    = Path("datasets/merged")
SPLIT   = {"train": 0.80, "val": 0.10, "test": 0.10}
SEED    = 42

# ── Логика ────────────────────────────────────────────────────────────────────

def collect_pairs(source_dir: Path) -> list[tuple[Path, Path]]:
    """Връща двойки (image_path, label_path) от дадена директория."""
    images_dir = source_dir / "images"
    labels_dir = source_dir / "labels"
    pairs = []
    for img in images_dir.glob("*.*"):
        label = labels_dir / (img.stem + ".txt")
        if label.exists():
            pairs.append((img, label))
        else:
            print(f"  ⚠️  Няма анотация за: {img.name} — пропуснато")
    return pairs


def copy_to_split(pairs, split_name: str):
    img_dest = DEST / split_name / "images"
    lbl_dest = DEST / split_name / "labels"
    img_dest.mkdir(parents=True, exist_ok=True)
    lbl_dest.mkdir(parents=True, exist_ok=True)
    for img, lbl in pairs:
        shutil.copy2(img, img_dest / img.name)
        shutil.copy2(lbl, lbl_dest / lbl.name)


if __name__ == "__main__":
    random.seed(SEED)

    all_pairs = []
    for src in SOURCES:
        if not src.exists():
            print(f"  ℹ️  {src} не съществува — пропуснато")
            continue
        found = collect_pairs(src)
        print(f"  ✅ {src}: {len(found)} двойки")
        all_pairs.extend(found)

    if not all_pairs:
        print("\n⚠️  Няма снимки с анотации. Добави снимки в datasets/personal/ или datasets/public/")
        exit(0)

    random.shuffle(all_pairs)
    n       = len(all_pairs)
    n_train = int(n * SPLIT["train"])
    n_val   = int(n * SPLIT["val"])

    splits = {
        "train": all_pairs[:n_train],
        "val":   all_pairs[n_train : n_train + n_val],
        "test":  all_pairs[n_train + n_val :],
    }

    for name, pairs in splits.items():
        copy_to_split(pairs, name)
        print(f"  {name:5s}: {len(pairs)} снимки")

    print(f"\n✅ Готово! Общо {n} снимки разпределени в datasets/merged/")
