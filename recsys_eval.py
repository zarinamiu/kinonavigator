"""Простая воспроизводимая offline-оценка MovieLens 100K."""

import math
import random
from collections import defaultdict
from pathlib import Path

DATA = Path("data/ml-100k")
RATINGS_FILE = DATA / "u.data"
ITEMS_FILE = DATA / "u.item"
SEED = 42
K = 10


def load_movies():
    movies = {}
    with ITEMS_FILE.open(encoding="latin-1") as file:
        for line in file:
            parts = line.rstrip("\n").split("|")
            movie_id = int(parts[0])
            title = parts[1]
            genres = [int(value) for value in parts[5:24]]
            movies[movie_id] = {
                "title": title,
                "genres": genres,
            }
    return movies


def load_ratings():
    users = defaultdict(dict)
    with RATINGS_FILE.open(encoding="latin-1") as file:
        for line in file:
            user, movie, rating, _timestamp = line.split()
            users[int(user)][int(movie)] = float(rating)
    return users


def split_by_user(ratings):
    rng = random.Random(SEED)
    train = {}
    test = {}
    for user_id, user_ratings in ratings.items():
        positives = [
            movie_id
            for movie_id, rating in user_ratings.items()
            if rating >= 4
        ]
        if len(user_ratings) < 5 or len(positives) < 2:
            continue
        rng.shuffle(positives)
        test_count = max(1, round(len(positives) * 0.2))
        held_out = set(positives[:test_count])
        train[user_id] = {
            movie_id: rating
            for movie_id, rating in user_ratings.items()
            if movie_id not in held_out
        }
        test[user_id] = held_out
    return train, test


def cosine(first, second):
    common = set(first) & set(second)
    if not common:
        return 0.0
    dot = sum(first[key] * second[key] for key in common)
    first_norm = math.sqrt(sum(value * value for value in first.values()))
    second_norm = math.sqrt(sum(value * value for value in second.values()))
    if not first_norm or not second_norm:
        return 0.0
    return dot / (first_norm * second_norm)


def normalized(scores):
    maximum = max(scores.values(), default=0.0)
    if maximum <= 0:
        return {item: 0.0 for item in scores}
    return {item: score / maximum for item, score in scores.items()}


def popularity_scores(train, candidates):
    totals = defaultdict(float)
    counts = defaultdict(int)
    all_ratings = [
        rating
        for user_ratings in train.values()
        for rating in user_ratings.values()
    ]
    mean = sum(all_ratings) / len(all_ratings) if all_ratings else 0.0
    for user_ratings in train.values():
        for movie_id, rating in user_ratings.items():
            totals[movie_id] += rating
            counts[movie_id] += 1
    result = {}
    for movie_id in candidates:
        count = counts[movie_id]
        result[movie_id] = (
            (totals[movie_id] + 5 * mean) / (count + 5)
            if count
            else 0.0
        )
    return result


def content_scores(user_ratings, movies, candidates):
    profile = [0.0] * 19
    for movie_id, rating in user_ratings.items():
        if rating < 4 or movie_id not in movies:
            continue
        for index, flag in enumerate(movies[movie_id]["genres"]):
            profile[index] += flag * (rating - 3)
    profile_norm = math.sqrt(sum(value * value for value in profile))
    result = {}
    for movie_id in candidates:
        genres = movies[movie_id]["genres"]
        dot = sum(left * right for left, right in zip(profile, genres))
        genre_norm = math.sqrt(sum(value * value for value in genres))
        result[movie_id] = (
            dot / (profile_norm * genre_norm)
            if profile_norm and genre_norm
            else 0.0
        )
    return result


def item_cf_scores(user_id, train, candidates):
    user_ratings = train[user_id]
    item_users = defaultdict(dict)
    for other_user, ratings in train.items():
        for movie_id, rating in ratings.items():
            item_users[movie_id][other_user] = rating
    result = {}
    for candidate in candidates:
        score = 0.0
        candidate_ratings = item_users.get(candidate, {})
        for seen_movie, rating in user_ratings.items():
            similarity = cosine(
                candidate_ratings,
                item_users.get(seen_movie, {}),
            )
            score += max(similarity, 0.0) * max(rating - 3, 0)
        result[candidate] = score
    return result


def rank(scores, k):
    return [
        movie_id
        for movie_id, _score in sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:k]
    ]


def metrics(ranked, relevant):
    top = ranked[:K]
    hits = sum(movie_id in relevant for movie_id in top)
    precision = hits / K
    recall = hits / len(relevant) if relevant else 0.0
    dcg = sum(
        1 / math.log2(position + 2)
        for position, movie_id in enumerate(top)
        if movie_id in relevant
    )
    ideal_count = min(K, len(relevant))
    idcg = sum(
        1 / math.log2(position + 2)
        for position in range(ideal_count)
    )
    ndcg = dcg / idcg if idcg else 0.0
    return precision, recall, ndcg


def main():
    if not RATINGS_FILE.exists() or not ITEMS_FILE.exists():
        raise FileNotFoundError(
            "Проверь, что data/ml-100k/u.data и data/ml-100k/u.item существуют"
        )

    movies = load_movies()
    ratings = load_ratings()
    train, test = split_by_user(ratings)
    catalog = set(movies)

    totals = defaultdict(lambda: [0.0, 0.0, 0.0])
    users_evaluated = 0

    for user_id, relevant in test.items():
        known = set(train[user_id])
        candidates = catalog - known

        pop = popularity_scores(train, candidates)
        content = content_scores(train[user_id], movies, candidates)
        cf = item_cf_scores(user_id, train, candidates)

        content_scaled = normalized(content)
        cf_scaled = normalized(cf)
        pop_scaled = normalized(pop)

        methods = {
            "popularity": pop,
            "content": content,
            "item_cf": cf,
            "hybrid": {
                movie_id: (
                    0.50 * content_scaled.get(movie_id, 0.0)
                    + 0.40 * cf_scaled.get(movie_id, 0.0)
                    + 0.10 * pop_scaled.get(movie_id, 0.0)
                )
                for movie_id in candidates
            },
        }

        for name, scores in methods.items():
            values = metrics(rank(scores, K), relevant)
            for index, value in enumerate(values):
                totals[name][index] += value

        users_evaluated += 1

    if not users_evaluated:
        raise RuntimeError("После разделения не осталось тестовых пользователей")

    print(f"Seed: {SEED}")
    print(f"K: {K}")
    print(f"Пользователей в оценке: {users_evaluated}")
    print("Разбиение: у каждого пользователя удержана часть положительных оценок.")
    print("Это offline-оценка, не бизнес-эксперимент.")

    for name, values in totals.items():
        print(
            f"{name:12s} "
            f"Precision@{K}={values[0] / users_evaluated:.4f} "
            f"Recall@{K}={values[1] / users_evaluated:.4f} "
            f"NDCG@{K}={values[2] / users_evaluated:.4f}"
        )


if __name__ == "__main__":
    main()
