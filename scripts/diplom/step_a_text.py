# -*- coding: utf-8 -*-
"""Глобальные текстовые замены: тире, формулировки про рисунок, ссылки [N]."""
import re
from .helpers import set_paragraph_text


RULES = [
    # ── A. Единое тире ──
    (re.compile(r"(?<=\S) - (?=\S)"), " — "),
    (re.compile(r"–"), "—"),
    (re.compile(r"—\s*—"), "—"),

    # ── B. "(рисунок N)" → "на рисунке N" ──
    (re.compile(r"\(рисунок\s+(\d+)\)"), r"на рисунке \1"),
    (re.compile(r"\(рисунке\s+(\d+)\)"), r"на рисунке \1"),
    (re.compile(r"\(рис\.\s+(\d+)\)"), r"на рис. \1"),

    # ── C. Ссылки [N] к нормативным актам ──
    # 152-ФЗ
    (re.compile(r"(Федеральный закон[^№]{0,40}№\s*152-ФЗ\s*«О персональных данных»)"),
     r"\1 [4]"),
    (re.compile(r"(?<!\[)\b152-ФЗ\b(?!\s*[«\[])"), "152-ФЗ [4]"),
    # 149-ФЗ
    (re.compile(r"(Федеральный закон[^№]{0,40}№\s*149-ФЗ\s*«Об информации[^»]+»)"),
     r"\1 [5]"),
    (re.compile(r"(?<!\[)\b149-ФЗ\b(?!\s*[«\[])"), "149-ФЗ [5]"),
    # Приказ ФСТЭК № 21
    (re.compile(r"(Приказ\s+ФСТЭК\s+России\s+от\s+18\.02\.2013\s+№\s*21)"),
     r"\1 [6]"),
    (re.compile(r"(приказ(?:а|у|ом)?\s+ФСТЭК(?:\s+России)?\s+№\s*21)", re.IGNORECASE),
     r"\1 [6]"),
    # ГОСТы
    (re.compile(r"(ГОСТ\s+Р\s+7\.0\.97-2016)"), r"\1 [7]"),
    (re.compile(r"(ГОСТ\s+7\.32-2017)"), r"\1 [8]"),
    # ПП РФ № 1119
    (re.compile(r"(Постановление\s+Правительства\s+(?:Российской\s+Федерации|РФ)\s+от\s+01\.11\.2012\s+№\s*1119)"),
     r"\1 [9]"),
    (re.compile(r"(постановления?\s+Правительства\s+(?:Российской\s+Федерации|РФ)\s+№\s*1119)",
                re.IGNORECASE), r"\1 [9]"),
    # Конституция, ГК, НК — только при первом упоминании (точечно — без проверки на дублирование)
    (re.compile(r"(Конституция[^,\.]{0,40}Российской\s+Федерации)(?!\s*\[)"),
     r"\1 [1]"),
    (re.compile(r"(Гражданский\s+кодекс\s+Российской\s+Федерации)(?!\s*\[)"),
     r"\1 [2]"),
    (re.compile(r"(Налоговый\s+кодекс\s+Российской\s+Федерации)(?!\s*\[)"),
     r"\1 [3]"),
]


def apply(text):
    for pat, repl in RULES:
        text = pat.sub(repl, text)
    return text


def run(doc):
    changed = 0
    # Список использованных источников исключаем из глобальных замен,
    # чтобы не вставлять [N] в названия законов внутри самого списка.
    in_sources = False
    for p in doc.paragraphs:
        txt = p.text
        if txt.startswith("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"):
            in_sources = True
            continue
        if in_sources and (txt.startswith("ПРИЛОЖЕНИЕ") or txt.startswith("Приложение")):
            in_sources = False
        if in_sources:
            # внутри списка применяем только правки тире и форму "(рисунок N)"
            new = txt
            for pat, repl in RULES[:5]:  # первые 5 — это тире и "рисунок N"
                new = pat.sub(repl, new)
            if new != txt:
                set_paragraph_text(p, new)
                changed += 1
            continue
        if not txt:
            continue
        new = apply(txt)
        if new != txt:
            set_paragraph_text(p, new)
            changed += 1
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    old = p.text
                    if not old:
                        continue
                    new = apply(old)
                    if new != old:
                        set_paragraph_text(p, new)
                        changed += 1
    print(f"[A,B,C] Параграфов с заменами: {changed}")
