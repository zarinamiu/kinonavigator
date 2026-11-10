"""Сверка быстрой реализации с эталоном из инструкции.

Сравниваются не только итоговые метрики, но и сами топ-K списки:
если ранжирование совпало, метрики совпадут по построению.
Проверяется подвыборка пользователей (эталон на всех идёт ~15 минут).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recsys_eval as slow
import recsys_eval_fast as fast

SAMPLE_USERS = 8


def main() -> None:
    movies = slow.load_movies()
    ratings = slow.load_ratings()
    train, test = slow.split_by_user(ratings)

    catalog = set(movies)

    # Общие для быстрой версии структуры: считаются один раз.
    item_users = fast.build_item_vectors(train)
    item_norms = fast.build_item_norms(item_users)
    neighbors = fast.build_similarity_neighbors(train, item_users, item_norms)
    tables = fast.popularity_tables(train)

    users = list(test)[:SAMPLE_USERS]

    same_lists = 0
    different = []
    max_score_diff = 0.0

    for user_id in users:
        candidates = catalog - set(train[user_id])

        # --- эталон ---
        slow_pop = slow.popularity_scores(train, candidates)
        slow_content = slow.content_scores(train[user_id], movies, candidates)
        slow_cf = slow.item_cf_scores(user_id, train, candidates)

        # --- быстрая версия ---
        fast_pop = fast.popularity_scores(tables, candidates)
        fast_content = fast.content_scores(train[user_id], movies, candidates)
        fast_cf = fast.item_cf_scores(train[user_id], candidates, neighbors)

        diffs = {
            "popularity": max(
                abs(slow_pop[m] - fast_pop[m]) for m in candidates
            ),
            "content": max(
                abs(slow_content[m] - fast_content[m]) for m in candidates
            ),
            "item_cf": max(
                abs(slow_cf[m] - fast_cf[m]) for m in candidates
            ),
        }

        max_score_diff = max(max_score_diff, *diffs.values())

        # --- гибрид как в эталоне ---
        def hybrid(pop, content, cf):
            content_scaled = slow.normalized(content)
            cf_scaled = slow.normalized(cf)
            pop_scaled = slow.normalized(pop)
            return {
                movie_id: (
                    0.50 * content_scaled.get(movie_id, 0.0)
                    + 0.40 * cf_scaled.get(movie_id, 0.0)
                    + 0.10 * pop_scaled.get(movie_id, 0.0)
                )
                for movie_id in candidates
            }

        slow_methods = {
            "popularity": slow_pop,
            "content": slow_content,
            "item_cf": slow_cf,
            "hybrid": hybrid(slow_pop, slow_content, slow_cf),
        }
        fast_methods = {
            "popularity": fast_pop,
            "content": fast_content,
            "item_cf": fast_cf,
            "hybrid": hybrid(fast_pop, fast_content, fast_cf),
        }

        for name in slow_methods:
            slow_rank = slow.rank(slow_methods[name], slow.K)
            fast_rank = fast.rank(fast_methods[name], fast.K)

            if slow_rank == fast_rank:
                same_lists += 1
            else:
                different.append((user_id, name, slow_rank[:5], fast_rank[:5]))

    total = len(users) * 4

    print(f"Пользователей в сверке: {len(users)}")
    print(f"Сравнений топ-{slow.K} (4 метода): {total}")
    print(f"Совпало: {same_lists}")
    print(f"Расхождений: {len(different)}")
    print(f"Максимальное расхождение в score: {max_score_diff:.3e}")

    if different:
        print("\nПримеры расхождений:")
        for row in different[:5]:
            print("  ", row)

    # Сверка метрик на подвыборке: считаем только по этим пользователям.
    slow_totals = {name: [0.0, 0.0, 0.0] for name in ("popularity", "content", "item_cf", "hybrid")}
    fast_totals = {name: [0.0, 0.0, 0.0] for name in slow_totals}

    for user_id in users:
        relevant = test[user_id]
        candidates = catalog - set(train[user_id])

        slow_pop = slow.popularity_scores(train, candidates)
        slow_content = slow.content_scores(train[user_id], movies, candidates)
        slow_cf = slow.item_cf_scores(user_id, train, candidates)

        fast_pop = fast.popularity_scores(tables, candidates)
        fast_content = fast.content_scores(train[user_id], movies, candidates)
        fast_cf = fast.item_cf_scores(train[user_id], candidates, neighbors)

        content_scaled = slow.normalized(slow_content)
        cf_scaled = slow.normalized(slow_cf)
        pop_scaled = slow.normalized(slow_pop)
        slow_hybrid = {
            m: 0.5 * content_scaled.get(m, 0.0)
            + 0.4 * cf_scaled.get(m, 0.0)
            + 0.1 * pop_scaled.get(m, 0.0)
            for m in candidates
        }

        f_content_scaled = slow.normalized(fast_content)
        f_cf_scaled = slow.normalized(fast_cf)
        f_pop_scaled = slow.normalized(fast_pop)
        fast_hybrid = {
            m: 0.5 * f_content_scaled.get(m, 0.0)
            + 0.4 * f_cf_scaled.get(m, 0.0)
            + 0.1 * f_pop_scaled.get(m, 0.0)
            for m in candidates
        }

        for name, scores in (
            ("popularity", slow_pop), ("content", slow_content),
            ("item_cf", slow_cf), ("hybrid", slow_hybrid),
        ):
            values = slow.metrics(slow.rank(scores, slow.K), relevant)
            for index, value in enumerate(values):
                slow_totals[name][index] += value

        for name, scores in (
            ("popularity", fast_pop), ("content", fast_content),
            ("item_cf", fast_cf), ("hybrid", fast_hybrid),
        ):
            values = fast.metrics(fast.rank(scores, fast.K), relevant)
            for index, value in enumerate(values):
                fast_totals[name][index] += value

    print(f"\nМетрики на подвыборке ({len(users)} польз.):")
    print(f"{'метод':12s} {'эталон P/R/N':32s} {'быстрая P/R/N':32s} совпало")

    for name in slow_totals:
        slow_values = [v / len(users) for v in slow_totals[name]]
        fast_values = [v / len(users) for v in fast_totals[name]]
        equal = all(
            abs(a - b) < 1e-12 for a, b in zip(slow_values, fast_values)
        )
        print(
            f"{name:12s} "
            f"{slow_values[0]:.6f}/{slow_values[1]:.6f}/{slow_values[2]:.6f}   "
            f"{fast_values[0]:.6f}/{fast_values[1]:.6f}/{fast_values[2]:.6f}   "
            f"{'да' if equal else 'НЕТ'}"
        )
        assert equal, f"метрики расходятся: {name}"

    assert not different, "ранжирование расходится с эталоном"
    print("\nБыстрая версия эквивалентна эталону на проверенной подвыборке.")


if __name__ == "__main__":
    main()
