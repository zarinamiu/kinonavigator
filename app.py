from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "profiles.sqlite"
TRACE_PATH = LOG_DIR / "traces.jsonl"


MOVIES = [
    {"id": 1, "title": "Звёздный маршрут", "genres": ["фантастика", "приключения"]},
    {"id": 2, "title": "Тихий космос", "genres": ["фантастика", "драма"]},
    {"id": 3, "title": "Планета друзей", "genres": ["фантастика", "комедия"]},
    {"id": 4, "title": "Смешной вечер", "genres": ["комедия"]},
    {"id": 5, "title": "Лесная история", "genres": ["драма", "приключения"]},
    {"id": 6, "title": "Тайна старого дома", "genres": ["ужасы", "триллер"]},
    {"id": 7, "title": "Большая гонка", "genres": ["боевик", "приключения"]},
    {"id": 8, "title": "Летний дневник", "genres": ["романтика", "драма"]},
    {"id": 9, "title": "Команда исследователей", "genres": ["фантастика", "приключения"]},
    {"id": 10, "title": "Ночная загадка", "genres": ["триллер", "детектив"]},
    {"id": 11, "title": "Космическая шутка", "genres": ["фантастика", "комедия"]},
    {"id": 12, "title": "Дом у моря", "genres": ["драма", "романтика"]},
]

RATINGS = {
    1: {1: 5, 2: 4, 3: 4, 4: 5, 9: 5, 11: 4},
    2: {1: 4, 3: 5, 4: 4, 7: 3, 9: 5, 11: 5},
    3: {2: 5, 5: 4, 6: 4, 8: 5, 10: 4, 12: 5},
    4: {1: 5, 2: 4, 3: 5, 9: 4, 11: 5},
    5: {4: 4, 5: 5, 7: 4, 8: 4, 12: 4},
    6: {2: 4, 3: 4, 6: 5, 9: 5, 10: 5, 11: 4},
}

MOVIE_BY_ID = {movie["id"]: movie for movie in MOVIES}


def log_event(event: dict[str, Any]) -> None:
    record = {"time": time.time(), **event}
    with TRACE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def popularity_scores() -> dict[int, float]:
    all_ratings = [
        rating
        for user_ratings in RATINGS.values()
        for rating in user_ratings.values()
    ]
    average = sum(all_ratings) / len(all_ratings) if all_ratings else 0.0

    scores = {}
    for movie in MOVIES:
        values = [
            user_ratings[movie["id"]]
            for user_ratings in RATINGS.values()
            if movie["id"] in user_ratings
        ]

        if values:
            scores[movie["id"]] = (
                sum(values) + 2 * average
            ) / (len(values) + 2)
        else:
            scores[movie["id"]] = 0.0

    return scores


def recommend_popular(limit: int = 8) -> list[tuple[int, float]]:
    scores = popularity_scores()
    return sorted(
        scores.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )[:limit]


def recommend_content(
    wanted_genres: list[str],
    limit: int = 8,
) -> list[tuple[int, float]]:
    wanted = {genre.casefold() for genre in wanted_genres}
    results = []

    for movie in MOVIES:
        movie_genres = {genre.casefold() for genre in movie["genres"]}

        if not wanted:
            score = 0.0
        else:
            shared = len(wanted & movie_genres)
            union = len(wanted | movie_genres)
            score = shared / union if union else 0.0

        results.append((movie["id"], score))

    return sorted(results, key=lambda pair: pair[1], reverse=True)[:limit]


def cosine_similarity(
    first: dict[int, float],
    second: dict[int, float],
) -> float:
    common_users = set(first) & set(second)
    if not common_users:
        return 0.0

    dot = sum(first[user] * second[user] for user in common_users)
    first_length = math.sqrt(sum(value * value for value in first.values()))
    second_length = math.sqrt(sum(value * value for value in second.values()))

    if first_length == 0 or second_length == 0:
        return 0.0

    return dot / (first_length * second_length)


def recommend_item_cf(
    user_id: int | None,
    limit: int = 8,
) -> list[tuple[int, float]]:
    if user_id not in RATINGS:
        return recommend_popular(limit)

    user_ratings = RATINGS[user_id]
    results = []

    for candidate in MOVIES:
        candidate_id = candidate["id"]

        if candidate_id in user_ratings:
            continue

        candidate_ratings = {
            uid: ratings[candidate_id]
            for uid, ratings in RATINGS.items()
            if candidate_id in ratings
        }

        score = 0.0
        for seen_movie_id, user_rating in user_ratings.items():
            seen_ratings = {
                uid: ratings[seen_movie_id]
                for uid, ratings in RATINGS.items()
                if seen_movie_id in ratings
            }
            similarity = cosine_similarity(candidate_ratings, seen_ratings)
            score += max(similarity, 0.0) * user_rating

        results.append((candidate_id, score))

    return sorted(results, key=lambda pair: pair[1], reverse=True)[:limit]


def recommend_hybrid(
    wanted_genres: list[str],
    user_id: int | None,
    limit: int = 8,
) -> list[tuple[int, float]]:
    if user_id not in RATINGS:
        if wanted_genres:
            return recommend_content(wanted_genres, limit)
        return recommend_popular(limit)

    already_seen = set(RATINGS[user_id])

    content = dict(
        recommend_content(wanted_genres, len(MOVIES))
    )
    collaborative = dict(
        recommend_item_cf(user_id, len(MOVIES))
    )
    popular = popularity_scores()

    def scale(scores: dict[int, float]) -> dict[int, float]:
        maximum = max(scores.values(), default=0.0)

        if maximum <= 0:
            return {movie_id: 0.0 for movie_id in scores}

        return {
            movie_id: score / maximum
            for movie_id, score in scores.items()
        }

    content = scale(content)
    collaborative = scale(collaborative)
    popular = scale(popular)

    results = []

    for movie in MOVIES:
        movie_id = movie["id"]

        if movie_id in already_seen:
            continue

        score = (
            0.60 * content.get(movie_id, 0.0)
            + 0.30 * collaborative.get(movie_id, 0.0)
            + 0.10 * popular.get(movie_id, 0.0)
        )

        results.append((movie_id, score))

    return sorted(
        results,
        key=lambda pair: pair[1],
        reverse=True,
    )[:limit]

def parse_request_locally(text: str) -> dict[str, Any]:
    text = text.casefold().replace("ё", "е")

    word_forms = {
        "фантастика": ["фантастика", "фантастику", "фантастики"],
        "комедия": ["комедия", "комедию", "комедии"],
        "драма": ["драма", "драму", "драмы"],
        "ужасы": ["ужасы", "ужасов", "ужас"],
        "триллер": ["триллер", "триллеры"],
        "приключения": ["приключение", "приключения"],
        "романтика": ["романтика", "романтику"],
        "детектив": ["детектив", "детективы"],
        "боевик": ["боевик", "боевики"],
    }

    genres = []
    excluded = []

    for genre, forms in word_forms.items():
        if any(form in text for form in forms):
            genres.append(genre)

        if any(
            f"без {form}" in text or f"не {form}" in text
            for form in forms
        ):
            excluded.append(genre)

    genres = [genre for genre in genres if genre not in excluded]

    return {
        "genres": genres,
        "exclude_genres": excluded,
        "need_clarification": not bool(genres),
    }


def save_profile(user_id: str, genres: list[str]) -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            INSERT INTO profiles (user_id, genres)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET genres=excluded.genres,
                          updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, json.dumps(genres, ensure_ascii=False)),
        )


def load_profile(user_id: str) -> list[str] | None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        row = db.execute(
            "SELECT genres FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    return json.loads(row[0]) if row else None


def validate_recommendations(
    rows: list[tuple[int, float]],
    excluded_genres: list[str],
    required_genres: list[str] | None = None,
) -> list[tuple[int, float]]:
    forbidden = {
        genre.casefold()
        for genre in excluded_genres
    }
    required = {
        genre.casefold()
        for genre in (required_genres or [])
    }

    valid = []

    for movie_id, score in rows:
        movie = MOVIE_BY_ID.get(movie_id)

        if movie is None:
            continue

        movie_genres = {
            genre.casefold()
            for genre in movie["genres"]
        }

        if movie_genres & forbidden:
            continue

        if required and not (movie_genres & required):
            continue

        valid.append((movie_id, score))

    return valid

def explain_movie(
    movie: dict[str, Any],
    wanted_genres: list[str],
) -> str:
    matched = sorted(set(movie["genres"]) & set(wanted_genres))
    if matched:
        return "Совпадает по жанру: " + ", ".join(matched)

    return "Подобран алгоритмом по каталогу и оценкам."


def recommend(
    text: str,
    user_id: str = "new",
    algorithm: str = "hybrid",
) -> dict[str, Any]:
    started = time.perf_counter()
    preferences = parse_request_locally(text)

    log_event({
        "step": "parse",
        "preferences": preferences,
    })

    genres = preferences["genres"] or load_profile(user_id) or []

    if preferences["need_clarification"] and not genres:
        result = {
            "status": "clarification",
            "message": "Уточните, пожалуйста, жанр или настроение.",
        }
        log_event({"step": "clarification"})
        return result

    numeric_user_id = None
    if user_id.isdigit() and int(user_id) in RATINGS:
        numeric_user_id = int(user_id)

    if algorithm == "popular":
        candidates = recommend_popular()
    elif algorithm == "content":
        candidates = recommend_content(genres)
    elif algorithm == "item_cf":
        candidates = recommend_item_cf(numeric_user_id)
    else:
        candidates = recommend_hybrid(genres, numeric_user_id)

    checked = validate_recommendations(
        candidates,
        preferences["exclude_genres"],
        genres,
    )

    if not checked:
        result = {
            "status": "no_results",
            "message": (
                "В каталоге не нашлось фильмов, подходящих "
                "под указанные жанры и ограничения."
            ),
            "recommendations": [],
        }
        log_event({
            "step": "no_results",
            "genres": genres,
            "excluded_genres": preferences["exclude_genres"],
        })
        return result

    items = []
    for movie_id, score in checked[:5]:
        movie = MOVIE_BY_ID[movie_id]
        items.append({
            "title": movie["title"],
            "genres": movie["genres"],
            "score": round(score, 3),
            "reason": explain_movie(movie, genres),
        })

    result = {
        "status": "ok",
        "algorithm": algorithm,
        "recommendations": items,
    }

    log_event({
        "step": "finish",
        "duration_ms": round(
            (time.perf_counter() - started) * 1000,
            2,
        ),
        "recommendation_count": len(items),
    })

    return result


def precision_recall_at_k(
    ranked_ids: list[int],
    relevant_ids: set[int],
    k: int,
) -> tuple[float, float]:
    top = ranked_ids[:k]
    hits = len(set(top) & relevant_ids)

    precision = hits / k if k else 0.0
    recall = hits / len(relevant_ids) if relevant_ids else 0.0

    return precision, recall


def ndcg_at_k(
    ranked_ids: list[int],
    relevant_ids: set[int],
    k: int,
) -> float:
    dcg = 0.0
    for position, movie_id in enumerate(ranked_ids[:k]):
        if movie_id in relevant_ids:
            dcg += 1.0 / math.log2(position + 2)

    ideal_count = min(len(relevant_ids), k)
    ideal_dcg = sum(
        1.0 / math.log2(position + 2)
        for position in range(ideal_count)
    )

    return dcg / ideal_dcg if ideal_dcg else 0.0


def run_demo_eval() -> None:
    cases = [
        ("фантастика", {1, 3, 9, 11}),
        ("комедия", {3, 4, 11}),
        ("приключения", {1, 5, 7, 9}),
    ]

    totals = [0.0, 0.0, 0.0]

    for genre, relevant in cases:
        ranked = [
            movie_id
            for movie_id, _ in recommend_content(
                [genre],
                limit=len(MOVIES),
            )
        ]
        precision, recall = precision_recall_at_k(ranked, relevant, 5)
        ndcg = ndcg_at_k(ranked, relevant, 5)

        totals[0] += precision
        totals[1] += recall
        totals[2] += ndcg

    count = len(cases)
    print("Демонстрационная оценка на встроенных примерах.")
    print("Она не является оценкой на MovieLens или реальном трафике.")
    print(f"Средний Precision@5: {totals[0] / count:.3f}")
    print(f"Средний Recall@5:    {totals[1] / count:.3f}")
    print(f"Средний NDCG@5:      {totals[2] / count:.3f}")


if __name__ == "__main__":
    text = input("Запрос (или eval для метрик): ").strip()

    if text.casefold() == "eval":
        run_demo_eval()
    else:
        print(
            json.dumps(
                recommend(text, user_id="new"),
                ensure_ascii=False,
                indent=2,
            )
        )
