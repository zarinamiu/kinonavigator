"""Графики по фактическим данным прогонов.

Источники:
  report/llm_runs.json               — замер моделей Ollama
  report/recsys_sample_results.json  — метрики RecSys на выборке
Числа не выдумываются: скрипт падает, если файла нет.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
FIGURES = REPORT / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.dpi": 200,
})

BAR = "#4a7c9e"
BAR_ALT = "#c47c3a"
BAR_GOOD = "#4a7c4a"
BAR_BAD = "#a34a3a"


def load(path):
    if not path.exists():
        raise FileNotFoundError(f"Нет данных: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(fig, name):
    for suffix in ("png", "svg"):
        fig.savefig(FIGURES / f"{name}.{suffix}", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  ", name)


# ------------------------------------------------------- 1. Замер моделей
def chart_models():
    runs = load(REPORT / "llm_runs.json")

    models = []
    times = []
    ok_flags = []

    for run in runs:
        model = run["model"]
        if model not in models:
            models.append(model)
            times.append([])
            ok_flags.append([])

        index = models.index(model)
        if run.get("ok") and run.get("seconds"):
            times[index].append(run["seconds"])
            ok_flags[index].append(run.get("genre_ok") and run.get("exclusion_ok"))

    labels = []
    means = []
    colours = []

    for model, values, flags in zip(models, times, ok_flags):
        labels.append(model)
        means.append(sum(values) / len(values) if values else 0.0)
        colours.append(BAR_GOOD if (flags and all(flags)) else BAR_BAD)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    positions = np.arange(len(labels))
    bars = ax.barh(positions, means, color=colours)

    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Среднее время ответа, секунд (2 попытки, prompt одинаковый)")
    ax.set_title(
        "Локальные модели Ollama: время ответа\n"
        "красный — ответ не распознал жанр или потерял запрет",
        fontsize=11,
    )

    for bar, value in zip(bars, means):
        ax.text(
            value + 0.6, bar.get_y() + bar.get_height() / 2,
            f"{value:.1f} c", va="center", fontsize=9,
        )

    ax.set_xlim(0, max(means) * 1.22 if means else 1)
    save(fig, "01_время_моделей")


# --------------------------------------------------- 2. Качество разбора
def chart_quality():
    runs = load(REPORT / "llm_runs.json")

    criteria = ["JSON валиден", "Жанр верный", "Запрет учтён", "Без выдуманных фильмов"]
    keys = ["json_valid", "genre_ok", "exclusion_ok", None]

    models = []
    for run in runs:
        if run["model"] not in models:
            models.append(run["model"])

    matrix = []

    for model in models:
        attempts = [run for run in runs if run["model"] == model and run.get("ok")]

        row = []
        row.append(sum(bool(a.get("json_valid")) for a in attempts) / len(attempts) if attempts else 0)
        row.append(sum(bool(a.get("genre_ok")) for a in attempts) / len(attempts) if attempts else 0)
        row.append(sum(bool(a.get("exclusion_ok")) for a in attempts) / len(attempts) if attempts else 0)
        row.append(
            sum(not bool(a.get("invented_titles")) for a in attempts) / len(attempts)
            if attempts else 0
        )
        matrix.append(row)

    matrix = np.array(matrix)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    image = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(np.arange(len(criteria)))
    ax.set_xticklabels(criteria, fontsize=9)
    ax.set_yticks(np.arange(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Доля успешных попыток по критериям (одинаковый промпт)", fontsize=11)
    ax.grid(False)

    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(
                column, row, f"{matrix[row, column]:.0%}",
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#1a1a1a",
            )

    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="доля попыток")
    save(fig, "02_качество_разбора")


# ------------------------------------------------------ 3. Метрики RecSys
def chart_recsys():
    data = load(REPORT / "recsys_sample_results.json")
    metrics = data["metrics"]

    methods = ["popularity", "content", "item_cf", "hybrid"]
    prettier = {
        "popularity": "Popularity",
        "content": "Content",
        "item_cf": "Item-CF",
        "hybrid": "Hybrid",
    }

    precision = [metrics[name]["precision"] for name in methods]
    recall = [metrics[name]["recall"] for name in methods]
    ndcg = [metrics[name]["ndcg"] for name in methods]

    positions = np.arange(len(methods))
    width = 0.26

    fig, ax = plt.subplots(figsize=(9.5, 4.8))

    ax.bar(positions - width, precision, width, label=f"Precision@{data['k']}", color=BAR)
    ax.bar(positions, recall, width, label=f"Recall@{data['k']}", color=BAR_ALT)
    ax.bar(positions + width, ndcg, width, label=f"NDCG@{data['k']}", color=BAR_GOOD)

    ax.set_xticks(positions)
    ax.set_xticklabels([prettier[name] for name in methods])
    ax.set_ylabel("Значение метрики")
    ax.set_title(
        f"MovieLens 100K, пользователей в оценке: {data['users_evaluated']}\n"
        f"seed={data['seed']}, K={data['k']} — выборка мала, "
        "это проверка методики",
        fontsize=10.5,
    )
    ax.legend()
    ax.set_ylim(0, max(max(precision), max(recall), max(ndcg)) * 1.25)

    for index, name in enumerate(methods):
        value = ndcg[index]
        ax.text(
            index + width, value + 0.012, f"{value:.3f}",
            ha="center", fontsize=8.5,
        )

    save(fig, "03_метрики_recsys")


# --------------------------------------------- 4. Разброс по пользователям
def chart_per_user():
    data = load(REPORT / "recsys_sample_results.json")
    rows = data["per_user"]

    labels = [f"user {row['user_id']}" for row in rows]
    ndcg = [row["hybrid"]["ndcg"] for row in rows]
    held = [row["held_out"] for row in rows]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(11, 4.2),
        gridspec_kw={"width_ratios": [1.5, 1]},
    )

    positions = np.arange(len(rows))
    bars = ax1.bar(positions, ndcg, color=BAR, width=0.6)
    ax1.set_xticks(positions)
    ax1.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax1.set_ylabel(f"NDCG@{data['k']}, гибрид")
    ax1.set_title("Разброс метрики по пользователям", fontsize=10.5)

    for bar, value in zip(bars, ndcg):
        ax1.text(
            bar.get_x() + bar.get_width() / 2, value + 0.01,
            f"{value:.2f}", ha="center", fontsize=8.5,
        )

    ax2.scatter(held, ndcg, s=70, color=BAR_ALT)
    ax2.set_xlabel("Удержано фильмов в тесте")
    ax2.set_ylabel(f"NDCG@{data['k']}")
    ax2.set_title("Зависимость от размера теста", fontsize=10.5)

    for label, x, y in zip(labels, held, ndcg):
        ax2.annotate(label, (x, y), fontsize=7.5,
                     xytext=(4, 4), textcoords="offset points")

    save(fig, "04_разброс_по_пользователям")


# ------------------------------------- 5. Концентрация в content-based
def chart_content():
    """Почему content-based дал 0.0000: одинаковые баллы на верхушке."""
    import sys
    sys.path.insert(0, str(ROOT))

    import recsys_eval as R

    movies = R.load_movies()
    ratings = R.load_ratings()
    train, test = R.split_by_user(ratings)
    catalog = set(movies)

    uid = next(iter(test))
    candidates = catalog - set(train[uid])
    scores = R.content_scores(train[uid], movies, candidates)

    values = sorted(scores.values(), reverse=True)

    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    ax.plot(range(1, min(60, len(values)) + 1), values[:60],
            marker="o", markersize=3, color=BAR)

    top_value = values[0]
    tied = sum(1 for value in values if abs(value - top_value) < 1e-9)

    ax.axhline(top_value, linestyle="--", color=BAR_BAD, linewidth=1.2)
    ax.annotate(
        f"максимум {top_value:.3f} держат {tied} фильмов с одинаковым\n"
        "набором жанров — порядок решает случай, а не релевантность",
        xy=(tied / 2, top_value), xytext=(12, top_value * 0.86),
        fontsize=8.5, color=BAR_BAD,
        arrowprops=dict(arrowstyle="->", color=BAR_BAD, linewidth=1),
    )

    ax.set_xlabel("Позиция в ранжировании")
    ax.set_ylabel("Балл content-based")
    ax.set_title(
        "Почему content-based дал 0.0000 на выборке\n"
        "первые позиции — неразличимые по баллу фильмы",
        fontsize=10.5,
    )

    save(fig, "05_ничьи_content")


def main():
    print("Строю графики в", FIGURES.resolve())
    chart_models()
    chart_quality()
    chart_recsys()
    chart_per_user()
    chart_content()

    files = sorted(FIGURES.glob("*"))
    print(f"\nФайлов: {len(files)}")
    for file in files:
        print(f"  {file.name:42s} {file.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
