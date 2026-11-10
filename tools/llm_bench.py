"""Одинаковая проверка доступных моделей Ollama (раздел 6).

Каждая модель получает один и тот же запрос и оценивается по одним критериям.
Результат — report/llm_runs.json, из него строится таблица в отчёте.

num_ctx задан маленьким: окружение — 2 vCPU и 1,9 ГБ RAM без swap,
модели с большим буфером весов выгружаются OOM.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
TAGS_URL = OLLAMA_URL.replace("/api/chat", "/api/tags")
RUNS_PATH = Path(__file__).resolve().parent.parent / "report" / "llm_runs.json"
ATTEMPTS = 2
NUM_CTX = 1024

USER_REQUEST = "Посоветуй лёгкую фантастику, но без ужасов"

PROMPT = (
    "Разбери запрос: «Посоветуй лёгкую фантастику, но без ужасов».\n"
    "Верни только JSON с ключами genres, exclude_genres и need_clarification.\n"
    "Не придумывай названия фильмов."
)

EXPECTED_GENRES = {"фантастика"}
EXPECTED_EXCLUDED = {"ужасы"}
ALLOWED_GENRES = {
    "фантастика", "комедия", "драма", "ужасы", "триллер",
    "приключения", "романтика", "детектив", "боевик",
}
ALIASES = {
    "fantasy": "фантастика", "sci-fi": "фантастика",
    "science fiction": "фантастика", "comedy": "комедия",
    "drama": "драма", "horror": "ужасы", "thriller": "триллер",
    "adventure": "приключения", "romance": "романтика",
    "romantic": "романтика", "detective": "детектив",
    "mystery": "детектив", "action": "боевик",
}

TITLE_PATTERN = re.compile(r"«[^»]+»|\[[^\]]+\]")


def list_models() -> list[str]:
    with urllib.request.urlopen(TAGS_URL, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    return [item["name"] for item in data.get("models", [])]


def ask(model: str, prompt: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42, "num_ctx": NUM_CTX},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    started = time.perf_counter()

    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.loads(response.read().decode("utf-8"))

    if "error" in raw:
        raise RuntimeError(raw["error"])

    return {
        "content": raw["message"]["content"],
        "seconds": round(time.perf_counter() - started, 2),
        "eval_count": raw.get("eval_count"),
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "total_duration_s": round(raw.get("total_duration", 0) / 1e9, 2),
    }


def _normalize(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value.strip().casefold().replace("ё", "е"))
    text = ALIASES.get(text, text)
    return text if text in ALLOWED_GENRES else None


def assess(content: str) -> dict:
    """Проверяет ответ по тем же критериям, что и в таблице отчёта."""
    try:
        parsed = json.loads(content)
        json_valid = isinstance(parsed, dict)
    except json.JSONDecodeError:
        parsed, json_valid = {}, False

    if not json_valid:
        parsed = {}

    raw_genres = parsed.get("genres") if isinstance(parsed.get("genres"), list) else []
    raw_excluded = (
        parsed.get("exclude_genres")
        if isinstance(parsed.get("exclude_genres"), list)
        else []
    )

    genres = [g for g in (_normalize(x) for x in raw_genres) if g]
    excluded = [g for g in (_normalize(x) for x in raw_excluded) if g]

    raw_normalized = {
        (str(x).strip().casefold().replace("ё", "е") if isinstance(x, str) else str(x))
        for x in raw_genres + raw_excluded
    }

    keys = set(parsed)
    extra_fields = sorted(keys - {"genres", "exclude_genres", "need_clarification"})

    return {
        "json_valid": json_valid,
        "genres": genres,
        "exclude_genres": excluded,
        "need_clarification": parsed.get("need_clarification"),
        "genre_ok": EXPECTED_GENRES.issubset(set(genres)),
        "exclusion_ok": EXPECTED_EXCLUDED.issubset(set(excluded)),
        "unknown_genres": sorted(
            g for g in raw_normalized
            if g not in ALLOWED_GENRES and g not in ALIASES
        ),
        "extra_fields": extra_fields,
        "invented_titles": bool(TITLE_PATTERN.search(content)),
    }


def main() -> None:
    try:
        models = list_models()
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Ollama недоступна: {error}")
        return

    if not models:
        print("Ollama запущена, но моделей нет: ollama list пуст.")
        return

    print(f"Доступные модели: {', '.join(models)}")
    print(f"Запрос: {USER_REQUEST}")
    print(f"num_ctx={NUM_CTX}, temperature=0, seed=42, попыток на модель: {ATTEMPTS}\n")

    runs = []

    for model in models:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                result = ask(model, PROMPT)
            except Exception as error:
                runs.append({
                    "model": model,
                    "attempt": attempt,
                    "ok": False,
                    "error": f"{type(error).__name__}: {error}",
                })
                print(f"{model} попытка {attempt}: ОШИБКА — {error}\n")
                continue

            record = {"model": model, "attempt": attempt, "ok": True, **result}
            record.update(assess(result["content"]))
            runs.append(record)

            tokens_per_second = (
                round(result["eval_count"] / result["total_duration_s"], 2)
                if result["total_duration_s"] and result.get("eval_count")
                else None
            )
            record["tokens_per_second"] = tokens_per_second

            print(
                f"{model} попытка {attempt}: {result['seconds']} c, "
                f"JSON={record['json_valid']}, "
                f"жанр={record['genre_ok']}, "
                f"запрет={record['exclusion_ok']}, "
                f"ток/с={tokens_per_second}"
            )
            print(f"  ответ: {result['content'][:300]!r}\n")

    RUNS_PATH.parent.mkdir(exist_ok=True)
    RUNS_PATH.write_text(
        json.dumps(runs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Сохранено: {RUNS_PATH} ({len(runs)} записей)")


if __name__ == "__main__":
    main()
