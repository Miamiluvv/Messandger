# -*- coding: utf-8 -*-
"""Оркестратор правок дипломной работы Махмудовой А.Д.

Запускает все шаги по порядку и сохраняет результат как
ДИПЛОМ_Махмудова_А_Д_v2.docx.
"""
import os
import shutil
import sys

from docx import Document

# Подключаем пакет шагов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diplom import (
    step_a_text,
    step_d_auth,
    step_e_appendix,
    step_f_calls,
    step_g_security,
    step_h_economics,
    step_j_sources,
    step_k_remarks,
)

BASE = r"c:\Users\dalga\CascadeProjects\windsurf-project"
# По умолчанию правим самый свежий файл из присланных пользователем.
SRC = os.path.join(BASE, "ДИПЛОМ_Махмудова_А_Д [HIGirw] [Mbuh0y].docx")
DST = os.path.join(BASE, "ДИПЛОМ_Махмудова_А_Д_v3.docx")
# Допускаем переопределение через переменные окружения
SRC = os.environ.get("DIPLOM_SRC", SRC)
DST = os.environ.get("DIPLOM_DST", DST)


def main():
    if not os.path.exists(SRC):
        print(f"ERROR: исходный файл не найден: {SRC}")
        return 1

    # Копируем исходник для безопасности
    shutil.copyfile(SRC, DST)
    print(f"Создана копия: {DST}")

    doc = Document(DST)

    print("\n=== Шаги правки ===")
    # ВАЖНО: порядок имеет значение.
    # K (замечания) — ДО шагов, которые добавляют новые рисунки в подписи.
    step_k_remarks.run(doc)
    # F — описания звонков и редактора фото (вставка после рис. 17 и перед рис. 18)
    step_f_calls.run(doc)
    # D — замена авторизации на интеграцию (после F, т.к. F не трогает авторизацию)
    step_d_auth.run(doc)
    # G — раздел безопасности (перед 2.8 Тестирование)
    step_g_security.run(doc)
    # E — перенос рисунков 6 и 20 в приложение А
    step_e_appendix.run(doc)
    # H+I — экономика (пересчёт + подраздел 3.6)
    step_h_economics.run(doc)
    # J — реструктуризация источников
    step_j_sources.run(doc)
    # A,B,C — глобальные текстовые замены в самом конце,
    # чтобы они применились и к свежевставленным абзацам.
    step_a_text.run(doc)

    doc.save(DST)
    print(f"\n✓ Сохранено: {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
