"""
Преобразува PDF и DOCX файлове в 05_Литература/ към .txt или .md.
- Файлове с таблици → .md (markdown таблици)
- Файлове без таблици → .txt (обикновен текст)
Пропуска файлове, които вече са обработени.
Пускай: python preprocess_literature.py
"""

from pathlib import Path

LITERATURE_DIR = Path("05_Литература")


def _table_to_markdown(table: list) -> str:
    if not table or not table[0]:
        return ""
    rows = [[cell or "" for cell in row] for row in table]
    header = "| " + " | ".join(rows[0]) + " |"
    separator = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join([header, separator, body])


def _process_pdf(path: Path) -> tuple[str, bool]:
    import pdfplumber
    pages_text = []
    has_tables = False

    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                has_tables = True
                page_parts = [f"## Страница {i}"]
                for table in tables:
                    page_parts.append(_table_to_markdown(table))
                plain = page.extract_text()
                if plain:
                    used_text = plain
                    for table in tables:
                        for row in table:
                            for cell in row:
                                if cell:
                                    used_text = used_text.replace(cell, "")
                    leftover = used_text.strip()
                    if leftover:
                        page_parts.append(leftover)
                pages_text.append("\n\n".join(page_parts))
            else:
                plain = page.extract_text()
                if plain:
                    pages_text.append(f"## Страница {i}\n\n{plain}")

    return "\n\n---\n\n".join(pages_text), has_tables


def _process_docx(path: Path) -> tuple[str, bool]:
    from docx import Document
    doc = Document(str(path))
    parts = []
    has_tables = bool(doc.tables)

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())

    for i, table in enumerate(doc.tables, 1):
        parts.append(f"\n### Таблица {i}")
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        parts.append(_table_to_markdown(rows))

    return "\n\n".join(parts), has_tables


def process_all():
    if not LITERATURE_DIR.exists():
        print("Папката 05_Литература/ не е намерена.")
        return

    files = [f for f in LITERATURE_DIR.rglob("*")
             if f.is_file() and f.suffix.lower() in (".pdf", ".docx")]

    if not files:
        print("Няма PDF или DOCX файлове за обработка.")
        return

    for path in files:
        txt_out = path.with_suffix(".txt")
        md_out = path.with_suffix(".md")

        if txt_out.exists() or md_out.exists():
            print(f"  Пропускам (вече обработен): {path.name}")
            continue

        print(f"  Обработвам: {path.name} ...", end=" ", flush=True)
        try:
            if path.suffix.lower() == ".pdf":
                text, has_tables = _process_pdf(path)
            else:
                text, has_tables = _process_docx(path)

            if has_tables:
                out_path = md_out
                label = "таблици → .md"
            else:
                out_path = txt_out
                label = "текст → .txt"

            out_path.write_text(text, encoding="utf-8")
            print(f"{label}  ✓")

        except Exception as e:
            print(f"ГРЕШКА: {e}")

    print("\nГотово.")


if __name__ == "__main__":
    process_all()
