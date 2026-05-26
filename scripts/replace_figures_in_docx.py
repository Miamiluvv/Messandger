# -*- coding: utf-8 -*-
"""Заменяет рисунки 3, 4, 19 в docx на сгенерированные PNG.

Алгоритм: ищем подписи «Рисунок N — …», от подписи идём вверх по абзацам
до первого InlineShape (картинки) — это и есть рисунок N. Подменяем его
embed-blob на новый файл.
"""
import os
import sys
from docx import Document
from docx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(ROOT, 'assets', 'figures')

SRC = os.environ.get('DOC_SRC',
    os.path.join(ROOT, 'ДИПЛОМ_Махмудова_А_Д_v4.docx'))
DST = os.environ.get('DOC_DST',
    os.path.join(ROOT, 'ДИПЛОМ_Махмудова_А_Д_v5.docx'))

REPLACEMENTS = {
    3:  os.path.join(FIG_DIR, 'fig3_usecase.png'),
    4:  os.path.join(FIG_DIR, 'fig4_states.png'),
    19: os.path.join(FIG_DIR, 'fig19_deploy.png'),
}


def find_embed_rid(paragraph):
    """Возвращает rId первого встроенного изображения в абзаце, или None."""
    blips = paragraph._p.findall('.//' + qn('a:blip'))
    if not blips:
        return None
    embed = blips[0].get(qn('r:embed'))
    return embed


def main():
    doc = Document(SRC)
    paragraphs = list(doc.paragraphs)

    # Найдём индексы подписей
    captions = {}
    for i, p in enumerate(paragraphs):
        t = p.text.strip()
        for n in REPLACEMENTS:
            if t.startswith(f'Рисунок {n} —') or t.startswith(f'Рисунок {n}—'):
                captions[n] = i
                break

    print(f'Найдено подписей: {captions}')

    replaced = 0
    for n, cap_idx in captions.items():
        # Идём вверх от подписи и ищем абзац с картинкой
        rid = None
        for j in range(cap_idx - 1, max(cap_idx - 8, -1), -1):
            rid = find_embed_rid(paragraphs[j])
            if rid:
                break
        if not rid:
            print(f'  Рис. {n}: картинка не найдена выше подписи — пропуск')
            continue
        # Заменяем blob
        image_part = doc.part.related_parts[rid]
        with open(REPLACEMENTS[n], 'rb') as f:
            new_blob = f.read()
        image_part._blob = new_blob
        # Также чистим кэш content_type — оставим прежний (png должен совпасть)
        print(f'  Рис. {n}: заменён (rId={rid}, {len(new_blob)} байт)')
        replaced += 1

    doc.save(DST)
    print(f'\n✓ Сохранено: {DST} (заменено {replaced} рисунков)')


if __name__ == '__main__':
    main()
