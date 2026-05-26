# -*- coding: utf-8 -*-
"""Перенос рисунков 6 (ER) и 20 (алгоритм) в Приложение А.

Стратегия:
  Рис. 6 (ER-диаграмма) — перенести в приложение (А.6); из основного
  текста оставить только описание со ссылкой «представлена в Приложении А,
  рис. А.6». Подпись «Рисунок 6 —» из основного текста удаляется
  (саму картинку пользователь перенесёт в Word руками).

  Рис. 20 (алгоритм создания группового чата) — добавить копию в
  приложение (А.7), при этом в основном тексте сам рисунок и его
  описание оставить. В тексте добавить ссылку на приложение.

Картинки физически НЕ перемещаются (сохраняются как есть, чтобы не
испортить разметку); пользователю остаётся вырезать рисунок в Word и
вставить в нужное место рядом с подписями А.6 и А.7.
"""
import os, sys, shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diplom.helpers import (
    set_paragraph_text, insert_paragraph_after, insert_paragraphs_after,
    find_paragraph_starts_with, find_template_paragraph,
)
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, 'ДИПЛОМ_Махмудова_А_Д [HIGirw] [Mbuh0y].docx')


# ============== Текст для основного раздела ==============

# Заменяет существующий параграф «Представленная на рисунке 6 ER-...»
ER_NEW_MAIN = (
    "Полноразмерная ER-диаграмма базы данных мессенджера представлена "
    "в Приложении А (рисунок А.6). Основу схемы составляют сущности "
    "User (пользователи), Department (подразделения), Chat (чаты), "
    "ChatMember (участники чатов), Message (сообщения), Attachment "
    "(вложения), Notification (уведомления), запланированные сообщения, "
    "Poll (опросы) и PollOption (варианты ответов опроса). Между "
    "сущностями установлены связи «один-ко-многим» и «многие-ко-многим» "
    "(через таблицу ChatMember), отражающие предметную область "
    "корпоративных коммуникаций."
)

# Дополнение к описанию рис. 20 (добавляется в конец существующего абзаца)
ALG20_APPENDIX_NOTE = (
    " Полноразмерная блок-схема алгоритма с детализацией всех ветвлений "
    "и условий также представлена в Приложении А (рисунок А.7)."
)


# ============== Содержимое для Приложения А ==============

APP_A6_HEADING = "А.6 ER-диаграмма базы данных"
APP_A6_TEXT = [
    "ER-диаграмма базы данных корпоративного мессенджера представлена "
    "на рисунке А.6. Диаграмма отражает все основные сущности системы "
    "и связи между ними: пользователи (User), подразделения "
    "(Department), чаты (Chat), участники чатов (ChatMember), сообщения "
    "(Message), вложения (Attachment), уведомления (Notification), "
    "запланированные сообщения, опросы (Poll), варианты ответов опроса "
    "(PollOption), журнал аудита (AuditLog) и системные метрики. "
    "Связи между сущностями отражают предметную область корпоративных "
    "коммуникаций.",
]
APP_A6_FIG = "Рисунок А.6 — ER-диаграмма базы данных"

APP_A7_HEADING = "А.7 Блок-схема алгоритма создания группового чата"
APP_A7_TEXT = [
    "Полноразмерная блок-схема алгоритма создания группового чата "
    "представлена на рисунке А.7. Алгоритм начинается с открытия "
    "пользователем раздела «Чаты» и нажатия кнопки «Создать чат». "
    "Пользователь вводит название и описание, выбирает тип чата "
    "(личный, групповой, канал), добавляет участников из списка "
    "сотрудников Департамента и подтверждает создание. Сервер проверяет "
    "ролевые полномочия инициатора, создаёт запись в таблице Chat, "
    "добавляет всех выбранных участников в таблицу ChatMember и "
    "рассылает уведомления о создании чата по WebSocket-каналу. В "
    "случае ошибки на любом этапе пользователю отображается понятное "
    "сообщение, а уже выполненные операции откатываются в рамках "
    "транзакции базы данных.",
]
APP_A7_FIG = "Рисунок А.7 — Блок-схема алгоритма создания группового чата"


# ============== ИСПОЛНЕНИЕ ==============

def make_backup():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(ROOT, f'_BACKUP_до_приложения_{ts}.docx')
    shutil.copy2(TARGET, backup)
    print(f'  Бэкап: {os.path.basename(backup)}')


def main():
    print('=== Рисунки 6 и 20 → Приложение А ===\n')
    make_backup()
    doc = Document(TARGET)
    log = []

    body_tpl = find_template_paragraph(
        doc, lambda p: p.text.startswith('Архитектура системы спроектирована'))
    head_tpl = find_template_paragraph(
        doc, lambda p: p.text.startswith('2.6 Размещение мессенджера'))
    caption_tpl = find_template_paragraph(
        doc, lambda p: p.text.strip().startswith('Рисунок 17 — '))

    # ── 1. Рис. 6 в основном тексте ────────────────────────
    er_para = find_paragraph_starts_with(
        doc, "Представленная на рисунке 6 ER-диаграмма")
    if er_para is not None:
        set_paragraph_text(er_para, ER_NEW_MAIN)
        # Удаляем СЛЕДУЮЩИЙ за этим параграф «Сущность Message хранит...»
        # (это уточнение к диаграмме, теперь оно избыточно — основной текст
        #  переехал в Приложение А)
        next_para = find_paragraph_starts_with(
            doc, "Сущность Message хранит как текстовые сообщения")
        if next_para is not None:
            next_para._p.getparent().remove(next_para._p)
        # Удаляем подпись «Рисунок 6 — ER-диаграмма базы данных» из основного
        # текста (картинку пользователь сам вырежет в Word)
        cap_para = find_paragraph_starts_with(
            doc, "Рисунок 6 — ER-диаграмма")
        if cap_para is not None:
            cap_para._p.getparent().remove(cap_para._p)
        log.append('Рис. 6: текст в основной части заменён на ссылку, подпись удалена')
    else:
        log.append('Рис. 6: якорь НЕ найден')

    # ── 2. Рис. 20 в основном тексте — добавляем ссылку ─────
    alg_para = find_paragraph_starts_with(
        doc, "Алгоритм, представленный на рисунке 20")
    if alg_para is None:
        alg_para = find_paragraph_starts_with(
            doc, "Для иллюстрации внутренней логики системы")
    if alg_para is not None:
        # Добавляем в конец текста ссылку на Приложение А
        old = alg_para.text
        if 'Приложении А (рисунок А.7)' not in old:
            set_paragraph_text(alg_para, old.rstrip() + ALG20_APPENDIX_NOTE)
            log.append('Рис. 20: добавлена ссылка на Приложение А (А.7)')
    else:
        log.append('Рис. 20: якорь НЕ найден')

    # ── 3. Приложение А — добавляем А.6 и А.7 в конец ──────
    # Найдём ПОСЛЕДНИЙ непустой параграф в документе (это конец Приложения А)
    paragraphs = list(doc.paragraphs)
    last_p = None
    for p in paragraphs:
        if p.text.strip():
            last_p = p
    if last_p is not None:
        cursor = last_p
        # А.6
        cursor = insert_paragraph_after(cursor, '')
        cursor = insert_paragraph_after(cursor, APP_A6_HEADING,
                                          bold=True, clone_from=head_tpl)
        for txt in APP_A6_TEXT:
            cursor = insert_paragraph_after(cursor, txt, clone_from=body_tpl)
        cursor = insert_paragraph_after(cursor, '')   # место для картинки
        cursor = insert_paragraph_after(cursor, APP_A6_FIG,
                                          clone_from=caption_tpl)
        # А.7
        cursor = insert_paragraph_after(cursor, '')
        cursor = insert_paragraph_after(cursor, APP_A7_HEADING,
                                          bold=True, clone_from=head_tpl)
        for txt in APP_A7_TEXT:
            cursor = insert_paragraph_after(cursor, txt, clone_from=body_tpl)
        cursor = insert_paragraph_after(cursor, '')   # место для картинки
        cursor = insert_paragraph_after(cursor, APP_A7_FIG,
                                          clone_from=caption_tpl)
        log.append('Приложение А: добавлены А.6 (ER) и А.7 (алгоритм)')
    else:
        log.append('Приложение А: не нашли точку вставки')

    doc.save(TARGET)
    print('\n--- Журнал ---')
    for l in log:
        print(' ', l)
    print(f'\n✓ Сохранено: {os.path.basename(TARGET)}')
    print('\n⚠ ВАЖНО: в Word нужно ВРУЧНУЮ:')
    print('  • Вырезать картинку рисунка 6 (ER-диаграмма) из основного текста')
    print('    и вставить в Приложение А над подписью «Рисунок А.6 — ER-диаграмма».')
    print('  • Скопировать (не вырезать) рисунок 20 в Приложение А над')
    print('    подписью «Рисунок А.7 — Блок-схема алгоритма».')


if __name__ == '__main__':
    main()
