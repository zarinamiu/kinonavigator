"""Проверяет краткосрочную память сессии и профиль SQLite."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402


SESSION_ID = "check-memory-session"
USER_ID = "check-memory-user"


def main() -> None:
    if not hasattr(app, "SESSION_MEMORY"):
        raise SystemExit("FAIL: в app.py нет SESSION_MEMORY")

    app.SESSION_MEMORY.clear(SESSION_ID)

    answers = [
        {
            "genres": ["фантастика"],
            "exclude_genres": ["ужасы"],
            "need_clarification": False,
            "source_model": "memory-check",
            "fallback_chain": [],
        },
        {
            "genres": [],
            "exclude_genres": [],
            "need_clarification": True,
            "source_model": "memory-check",
            "fallback_chain": [],
        },
    ]

    try:
        with patch(
            "llm_router.parse_with_fallback",
            side_effect=answers,
        ):
            first = app.recommend(
                "фантастика без ужасов",
                session_id=SESSION_ID,
            )
            second = app.recommend(
                "ещё что-нибудь",
                session_id=SESSION_ID,
            )

        memory = app.SESSION_MEMORY.get(SESSION_ID)

        print("Краткосрочная память")
        print("  Первый запрос:", first["status"])
        print("  Второй запрос той же сессии:", second["status"])
        print("  Состояние:", memory)

        assert first["status"] == "ok", first
        assert second["status"] == "ok", second
        assert memory == {
            "genres": ["фантастика"],
            "exclude_genres": ["ужасы"],
        }, memory

        assert app.SESSION_MEMORY.clear(SESSION_ID) is True
        assert app.SESSION_MEMORY.get(SESSION_ID) == {
            "genres": [],
            "exclude_genres": [],
        }
        print("  Очистка краткосрочной памяти: OK")

        print("\nДолгосрочный профиль SQLite")
        app.save_profile(USER_ID, ["фантастика", "комедия"])
        first_profile = app.load_profile(USER_ID)

        app.save_profile(USER_ID, ["драма"])
        updated_profile = app.load_profile(USER_ID)

        print("  После первой записи:", first_profile)
        print("  После обновления:", updated_profile)

        assert first_profile == ["фантастика", "комедия"]
        assert updated_profile == ["драма"]

        assert app.delete_profile(USER_ID) is True
        assert app.load_profile(USER_ID) is None
        print("  Удаление профиля: OK")

        print("\nВсе проверки памяти пройдены.")

    finally:
        app.SESSION_MEMORY.clear(SESSION_ID)
        app.delete_profile(USER_ID)


if __name__ == "__main__":
    main()
