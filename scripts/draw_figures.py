# -*- coding: utf-8 -*-
"""Генерация рисунков 3, 4, 19 для диплома (matplotlib)."""
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import Ellipse, FancyBboxPatch

plt.rcParams['font.family'] = 'DejaVu Sans'

OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'figures')
os.makedirs(OUT, exist_ok=True)


def _save(name):
    path = os.path.join(OUT, name)
    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'  saved {path}')


# ────────────── РИСУНОК 3 — Use Case ──────────────
def fig3_usecase():
    fig, ax = plt.subplots(figsize=(12, 8.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 9); ax.axis('off')

    ax.add_patch(mp.Rectangle((2.5, 0.6), 7.0, 7.9, fill=False,
                                edgecolor='#222', linewidth=1.5))
    ax.text(6, 8.25, 'Корпоративный мессенджер',
            ha='center', va='center', fontsize=11, fontweight='bold')

    actors = [
        (0.6, 6.8, 'Сотрудник'),
        (0.6, 4.5, 'Руководитель\nподразделения'),
        (0.6, 2.0, 'Администратор\n(УИ)'),
        (11.4, 4.5, 'Корпоративная\nсистема SSO'),
    ]
    for x, y, name in actors:
        ax.add_patch(Ellipse((x, y + 0.4), 0.25, 0.3, fill=False, lw=1.4))
        ax.plot([x, x], [y + 0.25, y - 0.25], 'k-', lw=1.4)
        ax.plot([x - 0.25, x + 0.25], [y, y], 'k-', lw=1.4)
        ax.plot([x, x - 0.2], [y - 0.25, y - 0.6], 'k-', lw=1.4)
        ax.plot([x, x + 0.2], [y - 0.25, y - 0.6], 'k-', lw=1.4)
        ax.text(x, y - 1.0, name, ha='center', va='top', fontsize=9)

    usecases = [
        (4.5, 7.3, 'Вход в систему\n(SSO)'),
        (4.5, 6.3, 'Отправка\nсообщения'),
        (7.5, 6.3, 'Голосовой /\nвидеозвонок'),
        (4.5, 5.3, 'Создание\nчата / канала'),
        (7.5, 5.3, 'Обмен\nфайлами'),
        (4.5, 4.3, 'Создание\nопроса'),
        (7.5, 4.3, 'Просмотр\nуведомлений'),
        (4.5, 3.3, 'Поиск\nсообщений'),
        (7.5, 3.3, 'Редактирование\nизображений'),
        (4.5, 2.3, 'Модерация\nпользователей'),
        (7.5, 2.3, 'Журнал\nаудита'),
        (4.5, 1.3, 'Резервные\nкопии'),
        (7.5, 1.3, 'Мониторинг\nсистемы'),
    ]
    coords = {}
    for x, y, txt in usecases:
        ax.add_patch(Ellipse((x, y), 1.55, 0.65, fill=True,
                              facecolor='#EAF2FB', edgecolor='#1E5A9C', lw=1.1))
        ax.text(x, y, txt, ha='center', va='center', fontsize=8)
        coords[txt] = (x, y)

    def arrow(p1, p2):
        ax.annotate('', xy=p2, xytext=p1,
                     arrowprops=dict(arrowstyle='-', lw=0.8, color='#444'))

    employee = ['Вход в систему\n(SSO)', 'Отправка\nсообщения',
                'Голосовой /\nвидеозвонок', 'Создание\nчата / канала',
                'Обмен\nфайлами', 'Создание\nопроса', 'Просмотр\nуведомлений',
                'Поиск\nсообщений', 'Редактирование\nизображений']
    for uc in employee:
        arrow((0.85, 6.8), coords[uc])
    for uc in ['Создание\nчата / канала', 'Создание\nопроса',
               'Просмотр\nуведомлений']:
        arrow((0.85, 4.5), coords[uc])
    for uc in ['Вход в систему\n(SSO)', 'Модерация\nпользователей',
               'Журнал\nаудита', 'Резервные\nкопии', 'Мониторинг\nсистемы']:
        arrow((0.85, 2.0), coords[uc])
    arrow((11.15, 4.5), coords['Вход в систему\n(SSO)'])

    _save('fig3_usecase.png')


# ────────────── РИСУНОК 4 — Диаграмма состояний сообщения ──────────────
def fig4_states():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 6.5); ax.axis('off')

    states = {
        'Черновик':      (1.5, 5.0),
        'Отправлено':    (4.5, 5.0),
        'Доставлено':    (7.5, 5.0),
        'Прочитано':     (10.5, 5.0),
        'Редактируется': (4.5, 2.5),
        'Удалено':       (10.5, 2.5),
        'Закреплено':    (7.5, 0.7),
    }
    for name, (x, y) in states.items():
        ax.add_patch(FancyBboxPatch((x - 1.05, y - 0.45), 2.1, 0.9,
                                      boxstyle='round,pad=0.05,rounding_size=0.2',
                                      facecolor='#EAF2FB', edgecolor='#1E5A9C',
                                      lw=1.4))
        ax.text(x, y, name, ha='center', va='center', fontsize=10)

    # начальная и конечная точки
    ax.add_patch(Ellipse((0.3, 5.0), 0.25, 0.25, facecolor='black'))
    ax.add_patch(Ellipse((11.7, 2.5), 0.32, 0.32, fill=False, lw=1.5))
    ax.add_patch(Ellipse((11.7, 2.5), 0.18, 0.18, facecolor='black'))

    def arrow(p1, p2, label='', dx=0, dy=0.18, curve=0):
        style = 'arc3,rad=%.2f' % curve
        ax.annotate('', xy=p2, xytext=p1,
                     arrowprops=dict(arrowstyle='->', lw=1.1, color='#333',
                                       connectionstyle=style))
        if label:
            mx = (p1[0] + p2[0]) / 2 + dx
            my = (p1[1] + p2[1]) / 2 + dy
            ax.text(mx, my, label, ha='center', va='center', fontsize=8.5,
                     style='italic', color='#333')

    arrow((0.45, 5), (0.45, 5))  # точка
    arrow((0.45, 5.0), (states['Черновик'][0] - 1.05, 5.0), 'create()')
    arrow((states['Черновик'][0] + 1.05, 5.0),
          (states['Отправлено'][0] - 1.05, 5.0), 'send()')
    arrow((states['Отправлено'][0] + 1.05, 5.0),
          (states['Доставлено'][0] - 1.05, 5.0), 'ws.ack')
    arrow((states['Доставлено'][0] + 1.05, 5.0),
          (states['Прочитано'][0] - 1.05, 5.0), 'read()')

    arrow((states['Отправлено'][0], 4.55),
          (states['Редактируется'][0], 2.95), 'edit()')
    arrow((states['Редактируется'][0] + 0.9, 2.95),
          (states['Отправлено'][0] + 0.5, 4.55), 'save()', curve=0.3)

    arrow((states['Прочитано'][0], 4.55),
          (states['Удалено'][0], 2.95), 'delete()')
    arrow((states['Удалено'][0] + 0.5, 2.5), (11.7, 2.5), '')

    arrow((states['Доставлено'][0], 4.55),
          (states['Закреплено'][0], 1.15), 'pin()')
    arrow((states['Закреплено'][0] - 0.5, 1.15),
          (states['Доставлено'][0] - 0.5, 4.55), 'unpin()', curve=-0.3)

    _save('fig4_states.png')


# ────────────── РИСУНОК 19 — Диаграмма развёртывания ──────────────
def fig19_deploy():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis('off')

    def node(x, y, w, h, title, items, color='#F4F7FB'):
        ax.add_patch(mp.Rectangle((x, y), w, h, facecolor=color,
                                    edgecolor='#1E5A9C', lw=1.4))
        ax.text(x + 0.15, y + h - 0.3, title, fontsize=10, fontweight='bold')
        for i, it in enumerate(items):
            ax.add_patch(FancyBboxPatch(
                (x + 0.25, y + h - 0.95 - i * 0.7), w - 0.5, 0.55,
                boxstyle='round,pad=0.02,rounding_size=0.08',
                facecolor='white', edgecolor='#666', lw=0.9))
            ax.text(x + w / 2, y + h - 0.67 - i * 0.7, it,
                     ha='center', va='center', fontsize=8.5)

    # Клиент
    node(0.3, 5.5, 3.0, 2.2, '«device» Рабочая станция',
         ['Web-браузер\n(Chrome / Edge / Yandex)',
          'SPA React 18 + Zustand'])

    # Сервер приложения
    node(4.5, 4.6, 3.4, 3.1, '«server» Сервер приложения (Москва)',
         ['Nginx 1.24 (TLS 1.3, reverse proxy)',
          'FastAPI 0.110 (uvicorn, asyncio)',
          'WebSocket-gateway',
          'WebRTC-signaling'])

    # БД
    node(9.0, 5.5, 2.8, 2.2, '«database» Сервер БД',
         ['PostgreSQL 16\n(TLS, шифрование на диске)',
          'Резервные копии (Yandex S3)'])

    # Внешние системы
    node(0.3, 1.5, 3.0, 2.2, '«external» Корпоративный AD/SSO',
         ['LDAP / OpenID Connect'])

    node(4.5, 1.5, 3.4, 2.2, '«external» STUN / TURN',
         ['coturn-сервер (UDP 3478)',
          'Транзит P2P-медиа'])

    node(9.0, 1.5, 2.8, 2.2, '«storage» Объектное хранилище',
         ['S3-совместимое (вложения)',
          'GPG-шифрование бэкапов'])

    def line(p1, p2, label, dy=0.15):
        ax.annotate('', xy=p2, xytext=p1,
                     arrowprops=dict(arrowstyle='-', lw=1.2, color='#333'))
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2 + dy
        ax.text(mx, my, label, ha='center', va='center', fontsize=8,
                 style='italic', color='#1E5A9C')

    line((3.3, 6.6), (4.5, 6.2), 'HTTPS / WSS\n(TLS 1.3)')
    line((7.9, 6.2), (9.0, 6.6), 'SQL\n(TLS)')
    line((6.2, 4.6), (1.8, 3.7), 'OIDC')
    line((6.2, 4.6), (6.2, 3.7), 'WebRTC signaling')
    line((7.9, 5.0), (9.0, 3.7), 'HTTPS (S3 API)')

    _save('fig19_deploy.png')


if __name__ == '__main__':
    print('Генерация рисунков...')
    fig3_usecase()
    fig4_states()
    fig19_deploy()
    print('Готово.')
