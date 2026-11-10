"""Дополнительная диагностика popularity fallback на MovieLens 100K.

Измеряет только operational-показатели:
- catalog coverage@10 при исключении уже просмотренных фильмов;
- время расчёта выдачи для пользователей с историей;
- поведение popularity fallback для нового пользователя;
- число item-cold фильмов и наличие у них жанровых метаданных.

Этот скрипт не измеряет релевантность и не заменяет ranking evaluation.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ml-100k"
REPORT_DIR = ROOT / "report"
OUTPUT_PATH = REPORT_DIR / "recsys_extra_results.json"
K = 10


def load_movies(path: Path) -> dict[int, dict[str, Any]]:
    movies: dict[int, dict[str, Any]] = {}

    with path.open("r", encoding="latin-1", newline="") as file:
        reader = csv.reader(file, delimiter="|")
        for row in reader:
            if len(row) < 24:
                continue

            movie_id = int(row[0])
            title = row[1]
            genre_flags = [int(value) for value in row[5:24]]
            genres = [
                f"genre_{index}"
                for index, flag in enumerate(genre_flags)
                if flag
            ]

            movies[movie_id] = {
                "title": title,
                "genres": genres,
            }

    return movies


def load_ratings(
    path: Path,
) -> tuple[dict[int, dict[int, int]], Counter[int], Counter[int]]:
    user_ratings: dict[int, dict[int, int]] = defaultdict(dict)
    movie_count: Counter[int] = Counter()
    movie_rating_sum: Counter[int] = Counter()
    all_ratings: list[int] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            fields = line.strip().split("\t")
            if len(fields) < 3:
                raise ValueError(
                    f"Некорректная строка u.data:{line_number}"
                )

            user_id = int(fields[0])
            movie_id = int(fields[1])
            rating = int(fields[2])

            user_ratings[user_id][movie_id] = rating
            movie_count[movie_id] += 1
            movie_rating_sum[movie_id] += rating
            all_ratings.append(rating)

    if not all_ratings:
        raise ValueError("Файл оценок пуст")

    return user_ratings, movie_count, movie_rating_sum


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def main() -> None:
    ratings_path = DATA_DIR / "u.data"
    movies_path = DATA_DIR / "u.item"

    if not ratings_path.is_file() or not movies_path.is_file():
        raise SystemExit(
            "MovieLens 100K не найден. Ожидаются файлы:\n"
            f"  {ratings_path}\n"
            f"  {movies_path}"
        )

    movies = load_movies(movies_path)
    user_ratings, movie_count, movie_rating_sum = load_ratings(ratings_path)

    all_rating_count = sum(movie_count.values())
    global_mean = (
        sum(movie_rating_sum.values()) / all_rating_count
        if all_rating_count
        else 0.0
    )





    smoothing = 2.0
    popularity: dict[int, float] = {}

    for movie_id in movies:
        count = movie_count[movie_id]
        total = movie_rating_sum[movie_id]
        popularity[movie_id] = (
            (total + smoothing * global_mean) / (count + smoothing)
            if count + smoothing
            else 0.0
        )

    all_movie_ids = set(movies)
    latencies_ms: list[float] = []
    recommended_movie_ids: set[int] = set()
    evaluated_users = 0

    for user_id, ratings in sorted(user_ratings.items()):
        seen = set(ratings)

        started = time.perf_counter()
        ranked = sorted(
            (
                (movie_id, score)
                for movie_id, score in popularity.items()
                if movie_id not in seen
            ),
            key=lambda item: (-item[1], item[0]),
        )[:K]
        elapsed_ms = (time.perf_counter() - started) * 1000

        latencies_ms.append(elapsed_ms)
        evaluated_users += 1
        recommended_movie_ids.update(movie_id for movie_id, _ in ranked)





    new_user_ranked = sorted(
        popularity.items(),
        key=lambda item: (-item[1], item[0]),
    )[:K]

    item_cold_ids = all_movie_ids - set(movie_count)
    cold_items_with_genres = sum(
        bool(movies[movie_id]["genres"])
        for movie_id in item_cold_ids
    )

    coverage = (
        len(recommended_movie_ids) / len(all_movie_ids)
        if all_movie_ids
        else 0.0
    )

    result = {
        "evaluation_type": "operational_diagnostic_not_relevance_evaluation",
        "dataset": "MovieLens 100K",
        "method": "smoothed_popularity_fallback",
        "k": K,
        "users_with_history": evaluated_users,
        "catalog_size": len(all_movie_ids),
        "catalog_coverage_at_k": coverage,
        "unique_recommended_movies": len(recommended_movie_ids),
        "latency_ms": {
            "p50_per_user": statistics.median(latencies_ms)
            if latencies_ms
            else 0.0,
            "p95_per_user": percentile(latencies_ms, 0.95),
            "max_per_user": max(latencies_ms, default=0.0),
            "total_measured_scoring_time": sum(latencies_ms),
        },
        "new_user_cold_start": {
            "history_size": 0,
            "fallback": "global popularity",
            "recommendation_count": len(new_user_ranked),
            "top_k_movie_ids": [movie_id for movie_id, _ in new_user_ranked],
            "accuracy_measured": False,
            "accuracy_reason": (
                "For a user without history there are no user-specific "
                "relevance labels in this diagnostic."
            ),
        },
        "item_cold_start": {
            "unrated_catalog_items": len(item_cold_ids),
            "unrated_items_with_genre_metadata": cold_items_with_genres,
            "accuracy_measured": False,
        },
        "limitations": [
            "Operational diagnostic only; not a ranking-quality evaluation.",
            "Does not replace Precision@K, Recall@K or NDCG@K.",
            "Popularity scores use all available ratings in u.data.",
            "Do not compare this latency directly with a production service.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nРезультат сохранён в: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
