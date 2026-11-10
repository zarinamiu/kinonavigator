"""Сквозные сценарии из таблицы инструкции (раздел 13).

Каждый сценарий — это вызов настоящего кода прототипа, а не проверка
отдельной функции. Ожидаемое поведение взято из таблицы инструкции.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_tools
import app
import llm_router

RESULTS = []


def scenario(name, expected):
    def decorator(function):
        def wrapper():
            print(f"\n{'=' * 72}")
            print(f"СЦЕНАРИЙ: {name}")
            print(f"ОЖИДАЕТСЯ: {expected}")
            print("-" * 72)
            try:
                ok, detail = function()
            except Exception as error:  # noqa: BLE001
                ok, detail = False, f"ИСКЛЮЧЕНИЕ {type(error).__name__}: {error}"

            mark = "OK  " if ok else "FAIL"
            print(f"[{mark}] {detail}")
            RESULTS.append((name, ok, detail))
            return ok

        return wrapper

    return decorator


@scenario(
    "«Посоветуй фантастику без ужасов»",
    "есть подходящие фильмы, ужасы исключены",
)
def s1():
    result = app.recommend("Посоветуй фантастику без ужасов")
    items = result.get("recommendations", [])

    if result["status"] != "ok":
        return False, f"статус {result['status']}"

    forbidden = [
        item["title"] for item in items if "ужасы" in item["genres"]
    ]

    if forbidden:
        return False, f"в ответе запрещённый жанр: {forbidden}"

    titles = ", ".join(item["title"] for item in items)
    return True, f"{len(items)} фильмов, ужасов нет: {titles}"


@scenario(
    "Запрос без жанра",
    "уточнение или явно реализованный fallback",
)
def s2():
    result = app.recommend("Посоветуй что-нибудь")

    if result["status"] != "clarification":
        return False, f"статус {result['status']}, ожидался clarification"

    return True, f"уточнение: {result['message']}"


@scenario(
    "Новый пользователь",
    "нет падения и утечки чужого профиля",
)
def s3():
    fresh_user = "brand_new_user_12345"

    with sqlite3.connect(app.DB_PATH) as db:
        db.execute("DELETE FROM profiles WHERE user_id = ?", (fresh_user,))
        db.commit()

    someone_else = "someone_else_user"
    app.save_profile(someone_else, ["ужасы"])

    result = app.recommend("Посоветуй что-нибудь", user_id=fresh_user)

    leaked = app.load_profile(fresh_user)

    if leaked is not None:
        return False, f"у нового пользователя появился профиль: {leaked}"

    if result["status"] != "clarification":
        return False, f"статус {result['status']}"

    # Чужой профиль не должен влиять на нового пользователя.
    other = app.load_profile(someone_else)

    return True, (
        f"профиль нового пуст, чужой профиль ({other}) не подхвачен, "
        f"ответ — {result['status']}"
    )


@scenario(
    "Несуществующий ID фильма",
    "валидатор отклоняет",
)
def s4():
    rows = [(999_999, 1.0), (1, 1.0)]
    checked = app.validate_recommendations(rows, [], [])

    ids = [movie_id for movie_id, _ in checked]

    if 999_999 in ids:
        return False, "несуществующий ID прошёл валидатор"

    if 1 not in ids:
        return False, f"существующий фильм отброшен: {checked}"

    tool_result = agent_tools.get_movie_details(999_999)

    if tool_result is not None:
        return False, "инструмент вернул несуществующий фильм"

    return True, f"валидатор оставил только {ids}, инструмент вернул None"


@scenario(
    "Неизвестный tool",
    "вызов запрещён",
)
def s5():
    blocked = []

    for name in ("run_shell_command", "read_file", "eval", "execute_code"):
        try:
            agent_tools.call_tool(name, {})
        except ValueError:
            blocked.append(name)

    if len(blocked) != 4:
        return False, f"запрещено только {blocked}"

    return True, f"запрещены все 4 имени: {', '.join(blocked)}"


@scenario(
    "Модель недоступна",
    "есть fallback или понятная ошибка",
)
def s6():
    with mock.patch.dict(os.environ, {
        "OLLAMA_MODEL": "нет_такой:1b",
        "OLLAMA_BACKUP_MODEL": "тоже_нет:1b",
    }):
        result = llm_router.parse_with_fallback("фантастику без ужасов")

    if result.get("source_model") != "local_fallback":
        return False, f"источник {result.get('source_model')}"

    return True, (
        f"цепочка отказов: {len(result['fallback_chain'])}, "
        f"итог — локальный разбор, жанры {result['genres']}"
    )


@scenario(
    "Некорректный JSON модели",
    "есть повтор, fallback или уточнение",
)
def s7():
    broken = mock.MagicMock()
    broken.read.return_value = json.dumps(
        {"message": {"content": "{это не json"}}
    ).encode()
    broken.__enter__.return_value = broken
    broken.__exit__.return_value = False

    with mock.patch.dict(os.environ, {
        "OLLAMA_MODEL": "битая:1b",
        "OLLAMA_BACKUP_MODEL": "",
    }), mock.patch("urllib.request.urlopen", return_value=broken):
        result = llm_router.parse_with_fallback("фантастику без ужасов")

    if result.get("source_model") != "local_fallback":
        return False, f"битый JSON не привёл к fallback: {result.get('source_model')}"

    chain = result.get("fallback_chain", [])

    return True, (
        f"битый JSON пойман, откат на локальный разбор; "
        f"ошибка записана: {chain[0][:60] if chain else '—'}"
    )


@scenario(
    "Ошибка инструментов",
    "приложение не падает без объяснения",
)
def s8():
    # Валидатор кормим мусором: NaN, отрицательный score, дубли.
    rows = [(1, float("nan")), (2, -5.0), (1, 0.5), (777_777, 1.0)]
    checked = app.validate_recommendations(rows, ["ужасы"], ["фантастика"])

    ids = [movie_id for movie_id, _ in checked]

    if 777_777 in ids:
        return False, "мусорный ID прошёл"

    # Инструмент с неверным типом аргумента должен давать понятную ошибку.
    try:
        agent_tools.call_tool("get_movie_details", {"movie_id": "один"})
    except ValueError as error:
        message = str(error)
    else:
        return False, "неверный тип не вызвал ошибку"

    return True, (
        f"мусор отфильтрован (осталось {ids}), "
        f"неверный тип аргумента — ValueError: {message}"
    )


@scenario(
    "Запуск в VM",
    "тесты и запрос работают внутри VM",
)
def s9():
    kvm = Path("/dev/kvm").exists()

    if kvm:
        return True, "/dev/kvm найден, VM доступна"

    return False, (
        "НЕ ВЫПОЛНЕНО: /dev/kvm отсутствует, гипервизор недоступен. "
        "Приложение проверено локально в .venv — это не VM."
    )


@scenario(
    "MovieLens",
    "метрики записаны вместе с K, seed и split",
)
def s10():
    path = Path(__file__).resolve().parent.parent / "report" / "recsys_sample_results.json"

    if not path.exists():
        return False, "нет файла с результатами"

    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"seed", "k", "split", "users_evaluated", "metrics"}
    missing = required - set(data)

    if missing:
        return False, f"не хватает полей: {missing}"

    return True, (
        f"seed={data['seed']}, K={data['k']}, "
        f"пользователей={data['users_evaluated']}, "
        f"split={data['split'][:45]}"
    )


def main() -> None:
    print("Сквозные сценарии КиноНавигатора")
    print(f"Файл: {Path(__file__).name}")
    print(f"Рабочая папка: {Path.cwd()}")

    for function in (
        s1, s2, s3, s4, s5, s6, s7, s8, s9, s10,
    ):
        function()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)

    print(f"\n{'=' * 72}")
    print(f"ИТОГО: {passed} из {total} сценариев выполнено")
    print("=" * 72)

    for name, ok, detail in RESULTS:
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name}")

    failed = [name for name, ok, _ in RESULTS if not ok]

    if failed:
        print(f"\nНе выполнено: {', '.join(failed)}")
        print("Причина указана в выводе сценария.")
    else:
        print("\nВсе сценарии выполнены.")

    (Path(__file__).resolve().parent.parent
     / "report" / "e2e_results.json").write_text(
        json.dumps(
            [{"scenario": n, "passed": ok, "detail": d} for n, ok, d in RESULTS],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
