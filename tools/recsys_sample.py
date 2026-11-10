"""Оценка RecSys на MovieLens 100K по небольшой выборке пользователей.

Полный прогон эталонного recsys_eval.py идёт ~15+ минут: для каждого из 942
пользователей матрица item→{user: rating} собирается заново. Для проверки
методики достаточно нескольких пользователей — но выборка маленькая,
поэтому метрики здесь нельзя сравнивать с публикациями по MovieLens.

Используются функции из recsys_eval.py: тот же split, тот же seed,
те же формулы и тот же порядок суммирования.
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recsys_eval as R

RESULTS_PATH = Path("report/recsys_sample_results.json")


def evaluate_users(users, movies, train, test):
    catalog = set(movies)
    totals = defaultdict(lambda: [0.0, 0.0, 0.0])
    per_user = []

    for user_id in users:
        relevant = test[user_id]
        candidates = catalog - set(train[user_id])

        pop = R.popularity_scores(train, candidates)
        content = R.content_scores(train[user_id], movies, candidates)
        cf = R.item_cf_scores(user_id, train, candidates)

        content_scaled = R.normalized(content)
        cf_scaled = R.normalized(cf)
        pop_scaled = R.normalized(pop)

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

        row = {
            "user_id": user_id,
            "seen_in_train": len(train[user_id]),
            "held_out": len(relevant),
        }

        for name, scores in methods.items():
            precision, recall, ndcg = R.metrics(R.rank(scores, R.K), relevant)
            totals[name][0] += precision
            totals[name][1] += recall
            totals[name][2] += ndcg
            row[name] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "ndcg": round(ndcg, 4),
            }

        per_user.append(row)

    count = len(users)
    summary = {
        name: {
            "precision": values[0] / count,
            "recall": values[1] / count,
            "ndcg": values[2] / count,
        }
        for name, values in totals.items()
    }

    return summary, per_user


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=5)
    arguments = parser.parse_args()

    if not R.RATINGS_FILE.exists() or not R.ITEMS_FILE.exists():
        raise FileNotFoundError(
            "Проверь, что data/ml-100k/u.data и data/ml-100k/u.item существуют"
        )

    movies = R.load_movies()
    ratings = R.load_ratings()
    train, test = R.split_by_user(ratings)

    users = list(test)[: arguments.users]

    started = time.perf_counter()
    summary, per_user = evaluate_users(users, movies, train, test)
    elapsed = time.perf_counter() - started

    print(f"Датасет: MovieLens 100K (u.data, u.item)")
    print(f"Seed: {R.SEED}, K: {R.K}")
    print("Разбиение: по пользователю, удержаны 20% положительных оценок (>=4)")
    print(f"Выборка: {len(users)} пользователей из {len(test)} в тесте")
    print("Это проверка методики, а не сравнение с публикациями.")
    print(f"Время: {elapsed:.1f} c")
    print()

    header = f"{'метод':12s} {'Precision@' + str(R.K):>13s} {'Recall@' + str(R.K):>11s} {'NDCG@' + str(R.K):>9s}"
    print(header)
    print("-" * len(header))

    for name, values in summary.items():
        print(
            f"{name:12s} {values['precision']:13.4f} "
            f"{values['recall']:11.4f} {values['ndcg']:9.4f}"
        )

    print()
    print("По пользователям:")
    for row in per_user:
        print(
            f"  user {row['user_id']:>3}: в train {row['seen_in_train']:>2}, "
            f"удержано {row['held_out']:>2}, "
            f"hybrid P={row['hybrid']['precision']:.4f} "
            f"R={row['hybrid']['recall']:.4f} "
            f"N={row['hybrid']['ndcg']:.4f}"
        )

    ndcgs = [row["hybrid"]["ndcg"] for row in per_user]
    if len(ndcgs) > 1:
        print()
        print(
            f"Разброс NDCG гибрида по пользователям: "
            f"min {min(ndcgs):.4f}, max {max(ndcgs):.4f}, "
            f"σ {statistics.pstdev(ndcgs):.4f}"
        )

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "dataset": "MovieLens 100K",
                "seed": R.SEED,
                "k": R.K,
                "split": "per-user, 20% of positives (>=4) held out",
                "users_evaluated": len(users),
                "total_users_in_test": len(test),
                "seconds": round(elapsed, 1),
                "sample_note": (
                    "Метрики на маленькой выборке. Не сопоставимы с полным "
                    "прогоном и с публикациями по MovieLens."
                ),
                "metrics": summary,
                "per_user": per_user,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nСохранено: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
