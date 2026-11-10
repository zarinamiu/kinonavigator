"""Разрешённые инструменты КиноНавигатора.

Агент вызывает только эти функции. Произвольного доступа к терминалу,
файловой системе и выполнению кода нет: всё, что не перечислено в TOOLS,
блокируется в call_tool.
"""

from typing import Any

from app import MOVIE_BY_ID, load_profile, recommend, save_profile

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
    """Возвращает сведения только о фильме из каталога."""
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
    """Читает профиль пользователя."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    return load_profile(user_id.strip())


def save_user_preferences(user_id: str, genres: list[str]) -> dict[str, str]:
    """Сохраняет только разрешённые жанры."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Нужен непустой user_id")

    if not isinstance(genres, list):
        raise ValueError("genres должен быть списком")

    cleaned = []

    for genre in genres:
        if not isinstance(genre, str):
            raise ValueError("Каждый жанр должен быть строкой")

        normalized = genre.strip().casefold()

        if normalized not in ALLOWED_GENRES:
            raise ValueError(f"Неизвестный жанр: {genre}")

        cleaned.append(normalized)

    save_profile(user_id.strip(), cleaned)

    return {"status": "saved"}


def recommend_movies(
    request_text: str,
    user_id: str = "new",
    algorithm: str = "hybrid",
) -> dict[str, Any]:
    """Вызывает только разрешённый алгоритм рекомендаций."""
    if not isinstance(request_text, str):
        raise ValueError("request_text должен быть строкой")

    if len(request_text) > MAX_REQUEST_LENGTH:
        raise ValueError("Запрос слишком длинный")

    if algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError("Неизвестный алгоритм")

    return recommend(
        request_text,
        user_id=user_id,
        algorithm=algorithm,
    )


TOOLS = {
    "get_movie_details": get_movie_details,
    "get_user_profile": get_user_profile,
    "save_user_preferences": save_user_preferences,
    "recommend_movies": recommend_movies,
}


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Запускает только явно разрешённую функцию."""
    if name not in TOOLS:
        raise ValueError(f"Инструмент не разрешён: {name}")

    if not isinstance(arguments, dict):
        raise ValueError("Аргументы должны быть словарём")

    return TOOLS[name](**arguments)
