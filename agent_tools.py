"""Разрешённые инструменты КиноНавигатора.

Агент вызывает только функции из TOOLS. Произвольного доступа к терминалу,
файловой системе и выполнению кода нет.
"""

from typing import Any

from app import (
    MOVIE_BY_ID,
    SESSION_MEMORY,
    delete_profile,
    load_profile,
    recommend,
    save_profile,
)

ALLOWED_GENRES = {
    "фантастика",
    "комедия",
    "драма",
    "ужасы",
    "триллер",
    "приключения",
    "романтика",
    "детектив",
    "боевик",
}

ALLOWED_ALGORITHMS = {"popular", "content", "item_cf", "hybrid"}
MAX_REQUEST_LENGTH = 500


def get_movie_details(movie_id: int) -> dict[str, Any] | None:
    if not isinstance(movie_id, int) or isinstance(movie_id, bool):
        raise ValueError("movie_id должен быть целым числом")

    movie = MOVIE_BY_ID.get(movie_id)
    if movie is None:
        return None

    return {
        "id": movie["id"],
        "title": movie["title"],
        "genres": list(movie["genres"]),
    }


def get_user_profile(user_id: str) -> list[str] | None:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    return load_profile(user_id.strip())


def save_user_preferences(
    user_id: str,
    genres: list[str],
) -> dict[str, str]:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    if not isinstance(genres, list):
        raise ValueError("genres должен быть списком")

    cleaned: list[str] = []

    for genre in genres:
        if not isinstance(genre, str):
            raise ValueError("Каждый жанр должен быть строкой")

        normalized = genre.strip().casefold()
        if normalized not in ALLOWED_GENRES:
            raise ValueError(f"Неизвестный жанр: {genre}")

        if normalized not in cleaned:
            cleaned.append(normalized)

    save_profile(user_id.strip(), cleaned)
    return {"status": "saved"}


def delete_user_profile(user_id: str) -> dict[str, str]:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    deleted = delete_profile(user_id.strip())
    return {"status": "deleted" if deleted else "not_found"}


def clear_session_memory(session_id: str) -> dict[str, bool]:
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Нужен непустой session_id")

    cleared = SESSION_MEMORY.clear(session_id.strip())
    return {"cleared": cleared}


def recommend_movies(
    request_text: str,
    user_id: str = "new",
    algorithm: str = "hybrid",
    session_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(request_text, str):
        raise ValueError("request_text должен быть строкой")

    if len(request_text) > MAX_REQUEST_LENGTH:
        raise ValueError("Запрос слишком длинный")

    if not isinstance(algorithm, str) or algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError("Неизвестный алгоритм")

    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    if session_id is not None and (
        not isinstance(session_id, str) or not session_id.strip()
    ):
        raise ValueError("session_id должен быть непустой строкой")

    return recommend(
        request_text,
        user_id=user_id.strip(),
        algorithm=algorithm,
        session_id=session_id.strip() if session_id is not None else None,
    )


TOOLS = {
    "get_movie_details": get_movie_details,
    "get_user_profile": get_user_profile,
    "save_user_preferences": save_user_preferences,
    "delete_user_profile": delete_user_profile,
    "clear_session_memory": clear_session_memory,
    "recommend_movies": recommend_movies,
}


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    if not isinstance(name, str) or name not in TOOLS:
        raise ValueError(f"Инструмент не разрешён: {name}")

    if not isinstance(arguments, dict):
        raise ValueError("Аргументы должны быть словарём")

    return TOOLS[name](**arguments)
