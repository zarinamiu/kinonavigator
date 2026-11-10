"""Разбор запроса через Ollama, резервную модель и локальный fallback.

Порядок: основная модель → резервная модель → локальный разбор из app.py.
Любая ошибка на шаге не прерывает цепочку, а переводит её на следующий.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

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

# Малые модели уверенно отвечают по-английски, поэтому английские
# названия жанров приводим к русским, а не отбрасываем как мусор.
GENRE_ALIASES = {
    "fantasy": "фантастика",
    "sci-fi": "фантастика",
    "science fiction": "фантастика",
    "comedy": "комедия",
    "drama": "драма",
    "horror": "ужасы",
    "thriller": "триллер",
    "adventure": "приключения",
    "adventures": "приключения",
    "romance": "романтика",
    "romantic": "романтика",
    "detective": "детектив",
    "mystery": "детектив",
    "action": "боевик",
}

PROMPT_TEMPLATE = """Разбери запрос пользователя: {request!r}

Верни только JSON с полями:
genres, exclude_genres, need_clarification.

genres и exclude_genres должны быть списками строк.
Используй только явно названные предпочтения.
Не придумывай фильмы и факты.

Допустимые жанры: {genres}
Ответ — русскими словами, только JSON, без пояснений.
"""


def _normalize(genre: Any) -> str | None:
    """Приводит жанр к русскому названию из ALLOWED_GENRES или отбрасывает."""
    if not isinstance(genre, str):
        return None

    normalized = genre.strip().casefold().replace("ё", "е")
    normalized = re.sub(r"\s+", " ", normalized)

    normalized = GENRE_ALIASES.get(normalized, normalized)

    return normalized if normalized in ALLOWED_GENRES else None


def ask_model(model: str, user_text: str) -> dict:
    """Запрашивает у модели строгий JSON и валидирует структуру ответа."""
    prompt = PROMPT_TEMPLATE.format(
        request=user_text,
        genres=", ".join(sorted(ALLOWED_GENRES)),
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        result = json.loads(response.read().decode("utf-8"))

    parsed = json.loads(result["message"]["content"])

    if not isinstance(parsed, dict):
        raise ValueError("Ответ модели — не объект JSON")

    if not isinstance(parsed.get("genres"), list):
        raise ValueError("genres не список")

    if not isinstance(parsed.get("exclude_genres"), list):
        raise ValueError("exclude_genres не список")

    genres = []
    for item in parsed["genres"]:
        genre = _normalize(item)
        if genre and genre not in genres:
            genres.append(genre)

    excluded = []
    for item in parsed["exclude_genres"]:
        genre = _normalize(item)
        if genre and genre not in excluded:
            excluded.append(genre)

    # Запрещённый жанр нельзя одновременно считать предпочтением.
    genres = [genre for genre in genres if genre not in excluded]

    clarification = parsed.get("need_clarification", False)
    if isinstance(clarification, str):
        clarification = clarification.strip().casefold() in {
            "true", "yes", "да", "1"
        }
    else:
        clarification = bool(clarification)

    return {
        "genres": genres,
        "exclude_genres": excluded,
        "need_clarification": clarification or not bool(genres),
        "source_model": model,
    }


def parse_with_fallback(user_text: str) -> dict:
    """Основная модель → резервная → локальный разбор."""
    primary = os.getenv("OLLAMA_MODEL", "").strip()
    backup = os.getenv("OLLAMA_BACKUP_MODEL", "").strip()

    errors = []

    if not primary and not backup:
        errors.append("переменные OLLAMA_MODEL и OLLAMA_BACKUP_MODEL не заданы")

    for model in (primary, backup):
        if not model:
            continue

        try:
            result = ask_model(model, user_text)
        except (urllib.error.URLError, TimeoutError, ValueError,
                KeyError, json.JSONDecodeError) as error:
            errors.append(f"{model}: {error}")
            continue

        result["fallback_chain"] = errors
        return result

    from app import parse_request_locally

    result = parse_request_locally(user_text)
    result["source_model"] = "local_fallback"
    result["fallback_chain"] = errors

    return result
