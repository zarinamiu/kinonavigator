"""Семь архитектурных схем для отчёта КиноНавигатора.

Рисуются matplotlib в PNG (200 dpi) и SVG. Причина отказа от mermaid-cli:
в окружении нет системных библиотек для headless-браузера
(libnspr4.so), поэтому mmdc не запускается.

Пометки на схемах:
  [проверено]  — подтверждено запуском в этом окружении
  [планируется] — заявлено в сценарии, но не проверено здесь
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path("diagrams")
OUT.mkdir(exist_ok=True)

# Палитра
DONE = "#d7e9d5"       # проверено
DONE_EDGE = "#4a7c4a"
PLAN = "#f7e6c4"       # планируется
PLAN_EDGE = "#a8762a"
NEUTRAL = "#e6eaf2"
NEUTRAL_EDGE = "#5c6b8a"

FONT = {
    "font.family": "DejaVu Sans",
    "font.size": 9,
}
plt.rcParams.update(FONT)


def box(ax, x, y, w, h, text, kind="done", fontsize=8, bold=False):
    fill, edge = {
        "done": (DONE, DONE_EDGE),
        "plan": (PLAN, PLAN_EDGE),
        "neutral": (NEUTRAL, NEUTRAL_EDGE),
    }[kind]

    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.3,
        facecolor=fill,
        edgecolor=edge,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center",
        fontsize=fontsize,
        fontweight="bold" if bold else "normal",
        color="#1a1a1a",
        wrap=True,
    )
    return patch


def arrow(ax, start, end, text="", style="-|>", color="#333333",
          rad=0.0, fontsize=7, dashed=False, label_offset=0.13):
    patch = FancyArrowPatch(
        start, end,
        arrowstyle=style,
        mutation_scale=12,
        linewidth=1.2,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        linestyle="--" if dashed else "-",
        shrinkA=2, shrinkB=2,
    )
    ax.add_patch(patch)

    if text:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2 + label_offset
        ax.text(
            mx, my, text,
            ha="center", va="bottom",
            fontsize=fontsize,
            color="#333333",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85),
        )


def frame(xlim=(0, 10), ylim=(0, 7)):
    fig, ax = plt.subplots(figsize=(11, 7.4))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def legend(ax, x=0.12, y=6.72):
    handles = [
        patches.Patch(facecolor=DONE, edgecolor=DONE_EDGE, label="проверено запуском"),
        patches.Patch(facecolor=PLAN, edgecolor=PLAN_EDGE, label="планируется / не проверено"),
        patches.Patch(facecolor=NEUTRAL, edgecolor=NEUTRAL_EDGE, label="внешняя система"),
    ]
    ax.legend(
        handles=handles, loc="upper right",
        fontsize=7.5, frameon=True, ncol=3,
        bbox_to_anchor=(0.99, 1.02),
    )


def check_overlaps(ax, name):
    """Проверяет, не наезжают ли подписи друг на друга и на рамки блоков.

    Считаем по реальным bbox после отрисовки: если два текста пересекаются
    больше чем на 12% площади меньшего, это визуальный дефект.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    text_specs = []
    for text in ax.texts:
        if not text.get_text().strip():
            continue
        try:
            bbox = text.get_window_extent(renderer=renderer)
        except Exception:
            continue
        if bbox.width <= 0 or bbox.height <= 0:
            continue
        text_specs.append((text.get_text()[:28], bbox))

    problems = []

    for index, (label_a, box_a) in enumerate(text_specs):
        for label_b, box_b in text_specs[index + 1:]:
            overlap_w = max(
                0.0,
                min(box_a.x1, box_b.x1) - max(box_a.x0, box_b.x0),
            )
            overlap_h = max(
                0.0,
                min(box_a.y1, box_b.y1) - max(box_a.y0, box_b.y0),
            )
            if not overlap_w or not overlap_h:
                continue

            overlap = overlap_w * overlap_h
            smaller = min(box_a.width * box_a.height, box_b.width * box_b.height)
            ratio = overlap / smaller if smaller else 0.0

            if ratio > 0.12:
                problems.append((label_a, label_b, round(ratio, 2)))

    if problems:
        print(f"     НАЛОЖЕНИЯ в {name}: {len(problems)}")
        for row in problems[:6]:
            print(f"       {row[0]!r} × {row[1]!r} — {row[2]:.0%}")
    else:
        print(f"     наложений не найдено ({len(text_specs)} подписей)")

    return problems


def save(fig, name, ax=None):
    if ax is not None:
        check_overlaps(ax, name)
    for suffix in ("png", "svg"):
        fig.savefig(
            OUT / f"{name}.{suffix}",
            bbox_inches="tight",
            dpi=200,
        )
    plt.close(fig)
    print("  ", name)


# ---------------------------------------------------------------- 1. Контекст
def diagram_context():
    fig, ax = frame()
    ax.set_title(
        "1. System Context — КиноНавигатор\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    box(ax, 0.4, 4.4, 2.1, 1.5, "Пользователь\n(Зарина / Мила)", "neutral", 9)

    box(ax, 3.4, 3.9, 3.2, 2.4,
        "КиноНавигатор\n\nPython-приложение\nкаталог + RecSys +\nвалидатор + LLM-разбор",
        "done", 9, bold=True)

    box(ax, 7.5, 5.0, 2.1, 1.3, "Ollama\nлокальные модели\n[проверено]", "done", 8)
    box(ax, 7.5, 3.3, 2.1, 1.3, "MovieLens 100K\nфайлы u.data/u.item", "neutral", 8)
    box(ax, 7.5, 1.6, 2.1, 1.3, "Phoenix\nлокальный UI\n[проверено]", "done", 8)

    box(ax, 0.4, 1.4, 2.1, 1.3, "GitHub\nzarinamiu/kinonavigator", "neutral", 8)

    arrow(ax, (2.5, 5.15), (3.4, 5.15), "запрос на языке\nпользователя")
    arrow(ax, (6.6, 5.5), (7.5, 5.5), "HTTP 11434")
    arrow(ax, (7.5, 3.95), (6.6, 4.4), "оценки", rad=0.12)
    arrow(ax, (6.6, 4.0), (7.5, 2.3), "OTLP", rad=-0.12, dashed=True)
    arrow(ax, (2.5, 2.05), (3.4, 3.95), "git clone", rad=0.15, dashed=True)

    ax.text(
        0.4, 0.55,
        "Проверено здесь: Python-приложение, SQLite, Ollama, Phoenix, MovieLens-оценка на выборке.\n"
        "Не проверено здесь: запуск в VM (нет /dev/kvm), полный прогон MovieLens.",
        fontsize=7.5, color="#444444", va="bottom",
    )
    save(fig, "01_system_context", ax)


# -------------------------------------------------------------- 2. Контейнеры
def diagram_container():
    fig, ax = frame()
    ax.set_title(
        "2. Container — из чего состоит приложение\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    box(ax, 0.3, 4.6, 2.0, 1.5, "CLI / терминал\npython app.py", "neutral", 9)

    # граница приложения
    border = FancyBboxPatch(
        (2.7, 0.9), 4.6, 5.5,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        linewidth=1.6, facecolor="#fafafa",
        edgecolor="#8a97b0", linestyle="--",
    )
    ax.add_patch(border)
    ax.text(2.8, 6.15, "Python-приложение", fontsize=8.5,
            style="italic", color="#5c6b8a")

    box(ax, 3.0, 5.0, 2.0, 0.95, "LLM-разбор\nllm_router.py", "done", 8)
    box(ax, 5.2, 5.0, 1.9, 0.95, "Реестр tools\nagent_tools.py", "done", 8)
    box(ax, 3.0, 3.7, 4.1, 0.95, "Рекомендации app.py\npopular / content / item_cf / hybrid", "done", 8)
    box(ax, 3.0, 2.4, 4.1, 0.95, "Валидатор\nvalidate_recommendations()", "done", 8)
    box(ax, 3.0, 1.15, 1.9, 0.95, "Журнал\ntraces.jsonl", "done", 8)
    box(ax, 5.2, 1.15, 1.9, 0.95, "Профиль\nSQLite", "done", 8)

    box(ax, 7.9, 4.0, 1.85, 1.3, "Ollama\nqwen2.5 / llama3.2", "neutral", 8)
    box(ax, 7.9, 2.2, 1.85, 1.3, "Phoenix\nUI + OTLP :6006", "neutral", 8)

    arrow(ax, (2.3, 5.35), (3.0, 5.45), "")
    arrow(ax, (4.0, 4.98), (4.0, 4.65), "")
    arrow(ax, (5.0, 4.65), (5.0, 4.98), "")
    arrow(ax, (4.0, 3.68), (4.0, 3.35), "")
    arrow(ax, (3.5, 2.38), (3.5, 2.1), "")
    arrow(ax, (6.2, 2.38), (6.2, 2.1), "")
    arrow(ax, (7.1, 5.3), (7.9, 4.9), "HTTP")
    arrow(ax, (7.1, 1.65), (7.9, 2.5), "OTLP", dashed=True, rad=-0.1)

    ax.text(2.7, 0.35,
            "Все пять модулей [проверено]. Phoenix проверен тестовой трассой, "
            "автотрассировка приложения не подключена.",
            fontsize=7.5, color="#444444")
    save(fig, "02_container", ax)


# ------------------------------------------------------- 3. Компоненты агента
def diagram_agents():
    fig, ax = frame()
    ax.set_title(
        "3. Components: агентный поток\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    box(ax, 0.4, 4.1, 1.9, 1.2, "Запрос\nпользователя", "neutral", 8.5)
    box(ax, 2.8, 4.1, 2.1, 1.2, "1. Разбор\nllm_router\n→ local fallback", "done", 8.5)
    box(ax, 5.4, 4.1, 2.1, 1.2, "2. Выбор\nалгоритма\nhybrid / content", "done", 8.5)
    box(ax, 5.4, 2.2, 2.1, 1.2, "3. Кандидаты\n8 → top-5", "done", 8.5)
    box(ax, 2.8, 2.2, 2.1, 1.2, "4. Валидатор\nкаталог + запреты", "done", 8.5)
    box(ax, 0.4, 2.2, 1.9, 1.2, "5. Ответ\n+ объяснение", "done", 8.5)

    box(ax, 8.0, 4.1, 1.75, 1.2, "Ollama\nOLLAMA_MODEL", "neutral", 8)
    box(ax, 8.0, 2.2, 1.75, 1.2, "SQLite\nпрофиль", "neutral", 8)

    arrow(ax, (2.3, 4.7), (2.8, 4.7), "")
    arrow(ax, (4.9, 4.7), (5.4, 4.7), "жанры,\nзапреты")
    arrow(ax, (6.45, 4.08), (6.45, 3.42), "")
    arrow(ax, (5.4, 2.8), (4.9, 2.8), "оценки")
    arrow(ax, (2.8, 2.8), (2.3, 2.8), "прошли\nпроверку")
    arrow(ax, (3.85, 4.08), (3.85, 3.42), "повтор или\nfallback", dashed=True, rad=0.35)
    arrow(ax, (7.55, 4.7), (8.0, 4.7), "")
    arrow(ax, (6.45, 2.18), (8.0, 2.6), "профиль", rad=-0.15, dashed=True)

    ax.text(0.4, 1.35,
            "Пунктир — ветка восстановления: если разбор вернул пустой или некорректный\n"
            "результат, вызывается повтор или локальный разбор из app.py.\n"
            "Фреймворки LangGraph и CrewAI проверены отдельными smoke-тестами,\n"
            "в основной поток приложения не встроены.",
            fontsize=7.5, color="#444444", va="top")
    save(fig, "03_components_agents", ax)


# -------------------------------------------------------- 4. Компоненты RecSys
def diagram_recsys():
    fig, ax = frame()
    ax.set_title(
        "4. Components: RecSys\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    box(ax, 0.35, 3.9, 1.85, 1.15, "Каталог\n12 фильмов", "neutral", 8.5)
    box(ax, 0.35, 1.8, 1.85, 1.15, "Оценки\n6 пользователей", "neutral", 8.5)

    box(ax, 2.75, 5.0, 2.1, 1.0, "Popularity\nбайесовское среднее", "done", 8)
    box(ax, 2.75, 3.6, 2.1, 1.0, "Content-based\nкосинус жанров", "done", 8)
    box(ax, 2.75, 2.2, 2.1, 1.0, "Item-item CF\nкосинус по оценкам", "done", 8)
    box(ax, 2.75, 0.8, 2.1, 1.0, "Hybrid\n0.6/0.3/0.1", "done", 8)

    box(ax, 5.6, 2.9, 1.95, 1.3, "Нормировка\n0..1\nпо максимуму", "done", 8)
    box(ax, 8.0, 2.9, 1.8, 1.3, "Валидатор\nзапреты + каталог", "done", 8)

    for y in (5.5, 4.1, 2.7, 1.3):
        arrow(ax, (2.2, 4.5), (2.75, y), "", rad=0.05)

    arrow(ax, (4.85, 5.0), (5.6, 3.9), "")
    arrow(ax, (4.85, 4.1), (5.6, 3.7), "")
    arrow(ax, (4.85, 2.7), (5.6, 3.3), "")
    arrow(ax, (5.6, 3.2), (4.85, 1.35), "", dashed=True, rad=0.2)
    arrow(ax, (7.55, 3.55), (8.0, 3.55), "")
    arrow(ax, (7.0, 4.98), (8.3, 4.02), "", rad=-0.1, dashed=True, label_offset=0.05)

    ax.text(0.35, 6.4,
            "Precision@10 / Recall@10 / NDCG@10 на выборке из 5 пользователей: "
            "item_cf лучший (NDCG 0.3457),\npopularity 0.0353, hybrid 0.2028, "
            "content 0.0000 — у content все 10 верхних позиций делят один и тот же балл.",
            fontsize=7.5, color="#444444", va="top")
    save(fig, "04_components_recsys", ax)


# ------------------------------------------------------------ 5. Модель данных
def diagram_data():
    fig, ax = frame()
    ax.set_title(
        "5. Модели и данные\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    # MOVIES
    box(ax, 0.3, 4.3, 2.6, 1.4, "MOVIES / каталог\nid, title, genres[]", "done", 8.5, True)
    box(ax, 0.3, 2.5, 2.6, 1.4, "RATINGS\nuser_id → {movie_id: 1..5}", "done", 8.5, True)

    # profiles
    box(ax, 3.5, 4.3, 2.7, 1.4,
        "profiles (SQLite)\nuser_id TEXT PK\ngenres TEXT, updated_at", "done", 8, True)

    box(ax, 3.5, 2.5, 2.7, 1.4,
        "traces.jsonl\nstep, preferences,\nduration_ms, count", "done", 8, True)

    # MovieLens
    box(ax, 6.9, 4.3, 2.8, 1.4,
        "MovieLens 100K\nu.data: 100 000 оценок\nu.item: 1682 фильма", "neutral", 8, True)
    box(ax, 6.9, 2.5, 2.8, 1.4,
        "Train / Test\n20% положительных\n942 пользователя", "done", 8, True)

    arrow(ax, (2.9, 4.8), (3.5, 4.8), "жанры")
    arrow(ax, (1.6, 4.28), (1.6, 3.92), "")
    arrow(ax, (6.9, 4.7), (6.2, 4.7), "источник", dashed=True)
    arrow(ax, (8.3, 4.28), (8.3, 3.92), "")

    ax.text(0.3, 1.95,
            "Схема profiles:\n"
            "  CREATE TABLE profiles (user_id TEXT PRIMARY KEY, genres TEXT NOT NULL,\n"
            "                         updated_at TEXT DEFAULT CURRENT_TIMESTAMP);\n"
            "Удаление профиля функцией не предусмотрено — только DELETE вручную.\n"
            "Обновление: INSERT ... ON CONFLICT DO UPDATE, перезаписывает жанры и время.",
            fontsize=7.5, color="#333333", va="top", family="DejaVu Sans")
    save(fig, "05_data_model", ax)


# ------------------------------------------------------------ 6. Deployment
def diagram_deployment():
    fig, ax = frame(xlim=(0, 10), ylim=(0, 7))
    ax.set_title(
        "6. Deployment — локальный запуск (VM не проверена)\n",
        fontsize=13, fontweight="bold", pad=18,
    )

    border = FancyBboxPatch(
        (0.5, 0.6), 9.0, 5.5,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        linewidth=1.6, facecolor="#fbfbfb",
        edgecolor="#8a97b0", linestyle="--",
    )
    ax.add_patch(border)
    ax.text(0.7, 5.85, "Машина Милы (Linux, x86_64, 2 ядра, 1.9 ГБ RAM)",
            fontsize=8.5, style="italic", color="#5c6b8a")

    box(ax, 0.8, 4.3, 2.3, 1.3, "Терминал\nbash", "neutral", 8.5)
    box(ax, 3.4, 4.3, 2.6, 1.3, "python app.py\n.venv (изолированное)", "done", 8.5)
    box(ax, 6.4, 4.3, 2.7, 1.3, "SQLite\ndata/profiles.sqlite", "done", 8.5)
    box(ax, 3.4, 2.6, 2.6, 1.2, "logs/traces.jsonl\nлокальный файл", "done", 8.5)
    box(ax, 6.4, 2.6, 2.7, 1.2, "Ollama :11434\n4 модели", "done", 8.5)
    box(ax, 0.8, 2.6, 2.3, 1.2, "Phoenix :6006\nотдельный venv", "done", 8.5)

    box(ax, 3.4, 1.0, 2.6, 1.1, "VM (UTM/VirtualBox)\n[планируется, не проверено]", "plan", 8)
    box(ax, 6.4, 1.0, 2.7, 1.1, "Docker\nне используется", "plan", 8)

    arrow(ax, (3.1, 4.95), (3.4, 4.95), "")
    arrow(ax, (6.0, 4.95), (6.4, 4.95), "")
    arrow(ax, (4.7, 4.28), (4.7, 3.82), "пишет")
    arrow(ax, (6.0, 4.6), (7.4, 3.82), "LLM-разбор", rad=-0.1)
    arrow(ax, (3.1, 3.2), (3.4, 3.2), "OTLP", dashed=True)
    arrow(ax, (4.7, 2.58), (4.7, 2.12), "", dashed=True, style="-|>")

    ax.text(0.8, 0.25,
            "Проверено: приложение, SQLite, журнал, Ollama, Phoenix, отдельные venv.\n"
            "Не проверено: /dev/kvm отсутствует, гипервизор в окружении недоступен — "
            "запуск назван локальным в .venv, а не в виртуальной машине.\n"
            "Docker не использовался по требованию преподавателя.",
            fontsize=7.5, color="#444444", va="bottom")
    save(fig, "06_deployment", ax)


# -------------------------------------------------------------- 7. Sequence
def diagram_sequence():
    fig, ax = plt.subplots(figsize=(11.5, 7.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(
        "7. Sequence — полный запрос с валидатором и веткой ошибки\n",
        fontsize=13, fontweight="bold", pad=16,
    )

    actors = [
        ("Пользователь", 0.9, NEUTRAL, NEUTRAL_EDGE),
        ("Разборщик\nllm_router", 2.6, DONE, DONE_EDGE),
        ("RecSys\napp.py", 4.3, DONE, DONE_EDGE),
        ("Валидатор", 6.0, DONE, DONE_EDGE),
        ("Ответчик", 7.7, DONE, DONE_EDGE),
        ("Ollama", 9.2, NEUTRAL, NEUTRAL_EDGE),
    ]

    for name, x, fill, edge in actors:
        patch = FancyBboxPatch(
            (x - 0.55, 9.0), 1.1, 0.65,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            linewidth=1.2, facecolor=fill, edgecolor=edge,
        )
        ax.add_patch(patch)
        ax.text(x, 9.33, name, ha="center", va="center",
                fontsize=7.5, fontweight="bold")
        ax.plot([x, x], [1.0, 9.0], color="#9aa5bb", linewidth=0.9,
                linestyle=(0, (4, 4)))

    def msg(y, x1, x2, text, dashed=False, color="#222222"):
        ax.annotate(
            "", xy=(x2, y), xytext=(x1, y),
            arrowprops=dict(
                arrowstyle="-|>", mutation_scale=11,
                linewidth=1.1, color=color,
                linestyle="--" if dashed else "-",
            ),
        )
        ax.text(
            (x1 + x2) / 2, y + 0.12, text,
            ha="center", va="bottom", fontsize=7,
            color=color,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9),
        )

    msg(8.4, 0.9, 2.6, "запрос: «фантастику без ужасов»")
    msg(7.9, 2.6, 9.2, "prompt + format=json", dashed=True)
    msg(7.4, 9.2, 2.6, "JSON: genres / exclude_genres", dashed=True)
    msg(6.9, 2.6, 4.3, "жанры: [фантастика], запрет: [ужасы]")
    msg(6.4, 4.3, 4.3, "hybrid(жанры, user)")
    msg(5.9, 4.3, 6.0, "8 кандидатов")
    msg(5.4, 6.0, 6.0, "проверка каталога и запретов")
    msg(4.9, 6.0, 7.7, "5 проверенных фильмов")
    msg(4.4, 7.7, 0.9, "рекомендации + объяснение")

    # alt-блок
    rect = patches.Rectangle(
        (1.7, 1.5), 6.6, 2.5,
        linewidth=1.3, edgecolor=PLAN_EDGE,
        facecolor="none", linestyle="--",
    )
    ax.add_patch(rect)
    ax.text(1.85, 3.82, "alt", fontsize=8, fontweight="bold",
            color=PLAN_EDGE,
            bbox=dict(boxstyle="round,pad=0.15", fc="white",
                      ec=PLAN_EDGE, linewidth=1))

    msg(3.4, 9.2, 2.6, "таймаут / некорректный JSON", dashed=True, color="#a33a2a")
    msg(2.9, 2.6, 2.6, "повтор или локальный разбор", color="#a33a2a")
    ax.text(1.95, 2.35,
            "fallback: parse_request_locally()\n→ приложение отвечает без модели",
            fontsize=7, color="#a33a2a", va="top")
    msg(2.05, 2.6, 7.7, "жанры из локального разбора", dashed=True, color="#a33a2a")

    ax.text(0.3, 0.45,
            "Верхняя половина — подтверждённый успешный путь (35 тестов, живые прогоны).\n"
            "Нижняя — ветка ошибки, покрытая тестами на заглушках: "
            "ошибка сети, HTTP 404, битый JSON, пустые жанры.",
            fontsize=7.3, color="#444444", va="bottom")
    save(fig, "07_sequence", ax)


def main() -> None:
    print("Строю схемы в", OUT.resolve())
    diagram_context()
    diagram_container()
    diagram_agents()
    diagram_recsys()
    diagram_data()
    diagram_deployment()
    diagram_sequence()

    files = sorted(OUT.glob("*"))
    print(f"\nВсего файлов: {len(files)}")
    for file in files:
        print(f"  {file.name:34s} {file.stat().st_size / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
