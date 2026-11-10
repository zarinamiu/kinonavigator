"""Симуляция cold-start фильма на MovieLens 100K.

Фильмы целиком разделяются на warm и synthetic-cold части.
Оценки cold-фильмов не используются для построения пользовательских
жанровых профилей. Они используются только как held-out relevance labels.

Это офлайн-симуляция, а не измерение production-качества.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ml-100k"
REPORT_DIR = ROOT / "report"
OUTPUT = REPORT_DIR / "recsys_cold_item_results.json"

SEED = 42
COLD_ITEM_FRACTION = 0.20
K = 10
POSITIVE_THRESHOLD = 4


def load_movies(path: Path) -> dict[int, dict[str, Any]]:
    movies: dict[int, dict[str, Any]] = {}

    with path.open("r", encoding="latin-1", newline="") as file:
        reader = csv.reader(file, delimiter="|")
        for row in reader:
            if len(row) < 24:
                continue

            movie_id = int(row[0])
            flags = [int(value) for value in row[5:24]]
            genres = [i for i, flag in enumerate(flags) if flag]

            movies[movie_id] = {
                "title": row[1],
                "genres": genres,
            }

    return movies


def load_ratings(path: Path) -> list[tuple[int, int, int]]:
    rows: list[tuple[int, int, int]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"Некорректная строка u.data:{line_number}")

            rows.append((
                int(fields[0]),
                int(fields[1]),
                int(fields[2]),
            ))

    if not rows:
        raise ValueError("Файл рейтингов пуст")

    return rows


def precision_recall_ndcg(
    ranked: list[int],
    relevant: set[int],
    k: int,
) -> tuple[float, float, float]:
    top = ranked[:k]
    hits = sum(movie_id in relevant for movie_id in top)

    precision = hits / k if k else 0.0
    recall = hits / len(relevant) if relevant else 0.0

    dcg = sum(
        1.0 / math.log2(position + 2)
        for position, movie_id in enumerate(top)
        if movie_id in relevant
    )
    ideal_size = min(len(relevant), k)
    idcg = sum(
        1.0 / math.log2(position + 2)
        for position in range(ideal_size)
    )
    ndcg = dcg / idcg if idcg else 0.0

    return precision, recall, ndcg


def cosine_genre_score(
    user_preferences: list[float],
    movie_genres: list[int],
) -> float:
    if not movie_genres:
        return 0.0

    numerator = sum(user_preferences[index] for index in movie_genres)
    denominator = math.sqrt(sum(value * value for value in user_preferences))
    movie_norm = math.sqrt(len(movie_genres))

    if denominator == 0 or movie_norm == 0:
        return 0.0

    return numerator / (denominator * movie_norm)


def main() -> None:
    ratings_path = DATA_DIR / "u.data"
    movies_path = DATA_DIR / "u.item"

    if not ratings_path.is_file() or not movies_path.is_file():
        raise SystemExit(
            "MovieLens 100K не найден. Нужны data/ml-100k/u.data и u.item."
        )

    movies = load_movies(movies_path)
    ratings = load_ratings(ratings_path)

    movie_ids = sorted(movies)
    if len(movie_ids) < 2:
        raise SystemExit("В каталоге слишком мало фильмов для split.")

    cold_count = max(1, round(len(movie_ids) * COLD_ITEM_FRACTION))
    rng = random.Random(SEED)
    cold_items = set(rng.sample(movie_ids, cold_count))
    warm_items = set(movie_ids) - cold_items

    warm_ratings: dict[int, list[tuple[int, int]]] = defaultdict(list)
    test_ratings: dict[int, list[tuple[int, int]]] = defaultdict(list)

    for user_id, movie_id, rating in ratings:
        if movie_id in cold_items:
            test_ratings[user_id].append((movie_id, rating))
        else:
            warm_ratings[user_id].append((movie_id, rating))

    evaluated_users = 0
    content_metrics = [[], [], []]
    random_metrics = [[], [], []]
    content_coverage: set[int] = set()
    random_coverage: set[int] = set()

    users_with_positive_test = 0

    for user_id in sorted(test_ratings):
        user_train = warm_ratings.get(user_id, [])



        if len(user_train) < 5:
            continue

        relevant = {
            movie_id
            for movie_id, rating in test_ratings[user_id]
            if rating >= POSITIVE_THRESHOLD
        }
        if not relevant:
            continue

        users_with_positive_test += 1





        genre_preferences = [0.0] * 19
        for movie_id, rating in user_train:
            if rating < POSITIVE_THRESHOLD:
                continue
            for genre_id in movies[movie_id]["genres"]:
                genre_preferences[genre_id] += float(rating - 3)





        content_ranked = sorted(
            cold_items,
            key=lambda movie_id: (
                -cosine_genre_score(
                    genre_preferences,
                    movies[movie_id]["genres"],
                ),
                movie_id,
            ),
        )

        user_rng = random.Random(SEED + user_id)
        random_ranked = sorted(cold_items)
        user_rng.shuffle(random_ranked)

        content_values = precision_recall_ndcg(
            content_ranked,
            relevant,
            K,
        )
        random_values = precision_recall_ndcg(
            random_ranked,
            relevant,
            K,
        )

        for index, value in enumerate(content_values):
            content_metrics[index].append(value)
        for index, value in enumerate(random_values):
            random_metrics[index].append(value)

        content_coverage.update(content_ranked[:K])
        random_coverage.update(random_ranked[:K])
        evaluated_users += 1

    def means(values: list[list[float]]) -> dict[str, float]:
        names = ("precision_at_k", "recall_at_k", "ndcg_at_k")
        return {
            name: statistics.fmean(values[index]) if values[index] else 0.0
            for index, name in enumerate(names)
        }

    result = {
        "evaluation_type": "synthetic_item_cold_start_holdout",
        "dataset": "MovieLens 100K",
        "seed": SEED,
        "cold_item_fraction": COLD_ITEM_FRACTION,
        "k": K,
        "positive_threshold": POSITIVE_THRESHOLD,
        "catalog_items": len(movie_ids),
        "warm_items": len(warm_items),
        "synthetic_cold_items": len(cold_items),
        "users_with_positive_cold_test": users_with_positive_test,
        "evaluated_users": evaluated_users,
        "candidate_items_per_user": len(cold_items),
        "content_genre_model": means(content_metrics),
        "random_baseline": means(random_metrics),
        "catalog_coverage_at_k": {
            "content_genre_model": (
                len(content_coverage) / len(cold_items)
                if cold_items
                else 0.0
            ),
            "random_baseline": (
                len(random_coverage) / len(cold_items)
                if cold_items
                else 0.0
            ),
        },
        "split_policy": (
            "Global item holdout: all ratings for synthetic-cold items "
            "are excluded from user-profile construction and used only "
            "as held-out relevance labels."
        ),
        "limitations": [
            "Synthetic offline item-cold-start simulation, not production.",
            "Genre features are used; no textual or external metadata.",
            "Results depend on seed, threshold, and 20% item holdout.",
            "Users without at least five warm ratings are excluded.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nРезультат сохранён: {OUTPUT}")


if __name__ == "__main__":
    main()
