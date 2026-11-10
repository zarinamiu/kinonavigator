"""Тот же граф из трёх узлов, но на настоящих функциях КиноНавигатора.

framework_smoke.py проверяет только, что LangGraph проводит состояние
по цепочке узлов. Здесь те же узлы вызывают parse / recommend / validate
из app.py, поэтому видно, что фреймворк реально управляет прототипом.
"""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app import (
    MOVIE_BY_ID,
    parse_request_locally,
    recommend_content,
    recommend_hybrid,
    recommend_popular,
    validate_recommendations,
)


class State(TypedDict):
    text: str
    user_id: str
    preferences: dict[str, Any]
    genres: list[str]
    candidates: list[tuple[int, float]]
    checked: list[tuple[int, float]]
    answer: list[dict[str, Any]]
    steps: list[str]


def parse_node(state: State) -> dict[str, Any]:
    preferences = parse_request_locally(state["text"])

    return {
        "preferences": preferences,
        "genres": preferences["genres"],
        "steps": state.get("steps", []) + ["parse"],
    }


def recommend_node(state: State) -> dict[str, Any]:
    genres = state["genres"]
    user_id = state["user_id"]
    numeric_user_id = (
        int(user_id) if user_id.isdigit() else None
    )

    if genres:
        candidates = recommend_hybrid(genres, numeric_user_id)
    else:
        candidates = recommend_popular()

    return {
        "candidates": candidates,
        "steps": state.get("steps", []) + ["recommend"],
    }


def validate_node(state: State) -> dict[str, Any]:
    checked = validate_recommendations(
        state["candidates"],
        state["preferences"]["exclude_genres"],
        state["genres"],
    )

    answer = [
        {
            "title": MOVIE_BY_ID[movie_id]["title"],
            "genres": MOVIE_BY_ID[movie_id]["genres"],
            "score": round(score, 3),
        }
        for movie_id, score in checked[:5]
    ]

    return {
        "checked": checked,
        "answer": answer,
        "steps": state.get("steps", []) + ["validate"],
    }


def build_graph():
    graph = StateGraph(State)

    graph.add_node("parse", parse_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("validate", validate_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "recommend")
    graph.add_edge("recommend", "validate")
    graph.add_edge("validate", END)

    return graph.compile()


def main() -> None:
    application = build_graph()

    state = application.invoke({
        "text": "Посоветуй фантастику без ужасов",
        "user_id": "new",
    })

    print("Направление графа:", " -> ".join(state["steps"]))
    print("Разобранные жанры:", state["preferences"]["genres"])
    print("Исключённые жанры:", state["preferences"]["exclude_genres"])
    print("Кандидатов до проверки:", len(state["candidates"]))
    print("Прошли проверку:", len(state["checked"]))
    print()

    for item in state["answer"]:
        print(f"  {item['title']:22s} {item['score']:<6} {', '.join(item['genres'])}")

    запрещённые = [
        item for item in state["answer"]
        if set(item["genres"]) & set(state["preferences"]["exclude_genres"])
    ]

    print()
    print("Фильмов с запрещённым жанром в ответе:", len(запрещённые))
    assert not запрещённые, "граф пропустил запрещённый жанр"
    assert state["steps"] == ["parse", "recommend", "validate"]
    print("Проверка графа пройдена.")


if __name__ == "__main__":
    main()
