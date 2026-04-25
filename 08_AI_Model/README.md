# 08_AI_Модел — YOLOv11 за болести по Rosa damascena

## Структура

```
08_AI_Модел/
├── datasets/         ← снимки и анотации (НЕ в git — твърде тежки)
├── configs/          ← YAML конфигурации (в git)
├── scripts/          ← Python скриптове (в git)
├── models/           ← .pt модели (НЕ в git)
└── runs/             ← резултати от тренировки (НЕ в git)
```

## Conda среда

```
conda activate agro_ml
```

## Ред на изпълнение

1. Добави снимки в `datasets/personal/images/` и анотации в `datasets/personal/labels/`
2. `python scripts/prepare_dataset.py`  — разделя на train/val/test
3. `python scripts/train.py`            — тренира модела
4. `python scripts/predict.py --image "снимка.jpg"` — тества

## Класове болести

Виж `configs/rose_diseases.yaml`
