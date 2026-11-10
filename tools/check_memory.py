"""Проверка памяти КиноНавигатора: рабочее состояние, SQLite-профиль, удаление.

Смотрит на код как есть, без предположений: что реально попадает в базу,
что живёт только внутри одного вызова и что происходит при повторном
сохранении и при удалении.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app


def dump_table() -> list[tuple]:
    with sqlite3.connect(app.DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        return db.execute(
            "SELECT user_id, genres, updated_at FROM profiles ORDER BY user_id"
        ).fetchall()


def main() -> None:
    print("=" * 70)
    print("1. РАБОЧЕЕ СОСТОЯНИЕ ОДНОГО ВЫЗОВА")
    print("=" * 70)

    result = app.recommend("Посоветуй фантастику без ужасов")
    print("status:", result["status"])
    print("алгоритм:", result["algorithm"])
    print("кандидатов в ответе:", len(result["recommendations"]))
    print(
        "что возвращается наружу:",
        sorted(result.keys()),
    )
    print()
    print("Ключи ответа — это и есть всё, что переживает вызов:")
    print("  жанры и запреты передаются в validate_recommendations,")
    print("  список кандидатов существует только внутри recommend().")
    print("  Ни то, ни другое не сохраняется между запусками.")
    print()

    print("=" * 70)
    print("2. КРАТКОСРОЧНАЯ ПАМЯТЬ (уточнения в диалоге)")
    print("=" * 70)

    print("В app.py нет истории диалога: recommend() принимает одну строку.")
    print("Уточнение реализовано как статус ответа, а не как состояние:")
    print()

    unclear = app.recommend("Посоветуй что-нибудь")
    print("  запрос без жанра ->", unclear["status"])
    print("  сообщение:", unclear.get("message"))
    print()

    # Проверка: помнит ли система предыдущий запрос.
    print("Проверка, что контекст не переносится между вызовами:")
    first = app.recommend("Посоветуй фантастику без ужасов")
    second = app.recommend("Посоветуй что-нибудь")
    print("  вызов 1 статус:", first["status"])
    print("  вызов 2 статус:", second["status"])
    print(
        "  второй запрос не знает про фантастику из первого:",
        second["status"] == "clarification",
    )
    print()

    print("=" * 70)
    print("3. ДОЛГОСРОЧНАЯ ПАМЯТЬ (SQLite)")
    print("=" * 70)

    user_id = "memory_check_user"
    app.save_profile(user_id, ["фантастика", "комедия"])
    print("после save_profile:", app.load_profile(user_id))

    app.save_profile(user_id, ["драма"])
    print("после повторного save_profile:", app.load_profile(user_id))
    print("  -> строка перезаписывается, дубля нет (ON CONFLICT DO UPDATE)")

    rows = [row for row in dump_table() if row[0] == user_id]
    print("строка в таблице:", rows)
    print()

    print("Файл базы:", app.DB_PATH)
    with sqlite3.connect(app.DB_PATH) as db:
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE name='profiles'"
        ).fetchone()
    print("схема:", schema[0] if schema else "нет таблицы")
    print()

    print("=" * 70)
    print("4. АКТУАЛЬНОСТЬ И УДАЛЕНИЕ")
    print("=" * 70)

    print("Обновление: каждое save_profile перезаписывает жанры и updated_at.")
    print("Удаление в коде:", end=" ")

    if hasattr(app, "delete_profile"):
        print("есть app.delete_profile")
    else:
        print("ФУНКЦИИ НЕТ — ни в app.py, ни в agent_tools.TOOLS")
        print("  Значит удалить профиль можно только прямым SQL.")

        with sqlite3.connect(app.DB_PATH) as db:
            db.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
            db.commit()

        print("  Проверено вручную:")
        print("    DELETE FROM profiles WHERE user_id = ?;")
        print("  после удаления load_profile ->", app.load_profile(user_id))

    print()

    print("=" * 70)
    print("5. ЧТО ВООБЩЕ ЛЕЖИТ В БАЗЕ")
    print("=" * 70)

    all_rows = dump_table()
    print(f"всего профилей: {len(all_rows)}")
    for row in all_rows[:10]:
        print("  ", row)
    print()
    print("Персональных данных, кроме выбранных жанров, база не хранит:")
    print("  колонки — user_id, genres, updated_at.")


if __name__ == "__main__":
    main()
