"""Проверка разбиения train/test в recsys_eval.py (зона ответственности Милы).

Проверяет, что:
1. ни один удержанный фильм не остался в train;
2. удержаны только положительные оценки (>= 4);
3. доля удержанного соответствует заявленным 20%;
4. пользователи с <5 оценками или <2 положительными исключены;
5. разбиение воспроизводимо при том же seed.
"""

import math
import random
from collections import Counter
from pathlib import Path

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import recsys_eval as R


def main() -> None:
    ratings = R.load_ratings()
    train, test = R.split_by_user(ratings)

    print(f"Исходных пользователей: {len(ratings)}")
    print(f"Пользователей после разбиения: {len(train)}")
    print(f"Исключено: {len(ratings) - len(train)}")
    print()

    total_train = sum(len(item) for item in train.values())
    total_test = sum(len(item) for item in test.values())
    print(f"Оценок в train: {total_train}")
    print(f"Удержано в test: {total_test}")
    print(f"Доля удержанного: {total_test / (total_train + total_test):.4f}")
    print()

    # 1. Пересечение train/test должно быть пустым.
    overlaps = []
    for user_id, held in test.items():
        common = set(train[user_id]) & held
        if common:
            overlaps.append((user_id, sorted(common)[:5]))

    print(f"Пользователей с утечкой test→train: {len(overlaps)}")
    if overlaps:
        print("  примеры:", overlaps[:5])

    # 2. В test только положительные оценки.
    bad_ratings = []
    for user_id, held in test.items():
        for movie_id in held:
            if ratings[user_id][movie_id] < 4:
                bad_ratings.append((user_id, movie_id, ratings[user_id][movie_id]))

    print(f"Удержанных оценок ниже 4: {len(bad_ratings)}")

    # 3. Размер удержания на пользователя.
    sizes = Counter(len(held) for held in test.values())
    print(f"Размер удержания (фильмов на пользователя): {dict(sorted(sizes.items()))}")

    expected = sum(
        max(1, round(
            sum(1 for value in ratings[uid].values() if value >= 4) * 0.2
        ))
        for uid in train
    )
    print(f"Ожидаемое суммарное удержание по формуле: {expected}")
    print(f"Совпадает: {expected == total_test}")

    # 4. Отсечённые пользователи не проходят порог.
    excluded = [uid for uid in ratings if uid not in train]
    details = [
        (uid, len(ratings[uid]), sum(1 for v in ratings[uid].values() if v >= 4))
        for uid in excluded
    ]
    print(f"\nОтсечённые пользователи (всего {len(details)}):")
    for uid, count, positives in details[:5]:
        print(f"  user {uid}: оценок {count}, положительных {positives}")
    all_below = all(c < 5 or p < 2 for _, c, p in details)
    print(f"Все отсечённые ниже порога (<5 оценок или <2 положительных): {all_below}")

    # 5. Воспроизводимость: повторный вызов даёт то же разбиение.
    train2, test2 = R.split_by_user(ratings)
    same = (
        all(train[uid] == train2[uid] for uid in train)
        and all(test[uid] == test2[uid] for uid in test)
    )
    print(f"\nРазбиение воспроизводимо при seed={R.SEED}: {same}")

    # 6. Контроль: другой seed даёт другое разбиение (значит, seed работает).
    rng = random.Random(R.SEED + 1)
    different = 0
    for user_id, user_ratings in ratings.items():
        positives = [m for m, r in user_ratings.items() if r >= 4]
        if len(user_ratings) < 5 or len(positives) < 2:
            continue
        rng.shuffle(positives)
        held = set(positives[:max(1, round(len(positives) * 0.2))])
        if held != test[user_id]:
            different += 1
    print(f"При seed={R.SEED + 1} разбиение отличается у {different} пользователей")

    # 7. Каталог.
    movies = R.load_movies()
    print(f"\nФильмов в каталоге: {len(movies)}")
    test_items = {m for held in test.values() for m in held}
    print(f"Уникальных удерживаемых фильмов: {len(test_items)}")

    assert not overlaps, "утечка test в train"
    assert not bad_ratings, "в test попали оценки ниже 4"
    assert all_below, "порог отсечения нарушен"
    assert same, "разбиение нестабильно"
    print("\nВсе проверки разделения пройдены.")


if __name__ == "__main__":
    main()
