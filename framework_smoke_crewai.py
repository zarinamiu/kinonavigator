"""Тот же сценарий parse → recommend → validate, но оркестратором служит CrewAI.

Сравнение с LangGraph идёт на одинаковых шагах и одинаковых функциях app.py,
чтобы разница была в фреймворке, а не в задаче.

CrewAI Flow не требует вызова LLM: узлы — обычные функции. Это важно здесь,
потому что внешний API-ключ в учебном окружении недоступен.
"""

from typing import Any

from crewai.flow.flow import Flow, listen, start

from app import (
    MOVIE_BY_ID,
    parse_request_locally,
    recommend_hybrid,
    recommend_popular,
    validate_recommendations,
)


class KinoState(dict):
    """Состояние с доступом по ключу: Flow хранит его как словарь."""


class KinoFlow(Flow[KinoState]):
    @start()
    def parse(self):
        preferences = parse_request_locally(self.state["text"])

        self.state["preferences"] = preferences
        self.state["genres"] = preferences["genres"]
        self.state["steps"] = self.state.get("steps", []) + ["parse"]

        return preferences

    @listen(parse)
    def recommend(self, preferences: dict[str, Any]):
        genres = preferences["genres"]
        user_id = self.state.get("user_id", "new")
        numeric_user_id = int(user_id) if user_id.isdigit() else None

        if genres:
            candidates = recommend_hybrid(genres, numeric_user_id)
        else:
            candidates = recommend_popular()

        self.state["candidates"] = candidates
        self.state["steps"] = self.state.get("steps", []) + ["recommend"]

        return candidates

    @listen(recommend)
    def validate(self, candidates: list[tuple[int, float]]):
        preferences = self.state["preferences"]

        checked = validate_recommendations(
            candidates,
            preferences["exclude_genres"],
            self.state["genres"],
        )

        answer = [
            {
                "title": MOVIE_BY_ID[movie_id]["title"],
                "genres": MOVIE_BY_ID[movie_id]["genres"],
                "score": round(score, 3),
            }
            for movie_id, score in checked[:5]
        ]

        self.state["checked"] = checked
        self.state["answer"] = answer
        self.state["steps"] = self.state.get("steps", []) + ["validate"]

        return answer


def main() -> None:
    flow = KinoFlow()
    flow.kickoff(inputs={
        "text": "Посоветуй фантастику без ужасов",
        "user_id": "new",
    })

    state = flow.state

    print("Направление потока:", " -> ".join(state["steps"]))
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
    assert not запрещённые, "поток пропустил запрещённый жанр"
    assert state["steps"] == ["parse", "recommend", "validate"]
    print("Проверка потока пройдена.")


if __name__ == "__main__":
    main()
