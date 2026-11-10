"""Тесты маршрутизации разбора: основная модель → резервная → локальный разбор.

Сеть не используется: urllib.request.urlopen подменяется заглушкой,
поэтому проверяется порядок вызовов и обработка ошибок.
"""

import json
import os
import unittest
from unittest import mock

import llm_router


def fake_response(payload: dict):
    body = json.dumps(
        {"message": {"content": json.dumps(payload, ensure_ascii=False)}},
        ensure_ascii=False,
    ).encode("utf-8")

    response = mock.MagicMock()
    response.read.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = False

    return response


class AskModelTests(unittest.TestCase):
    def test_valid_answer_is_normalized(self):
        answer = {
            "genres": ["Фантастика", "комедия"],
            "exclude_genres": ["Ужасы"],
            "need_clarification": False,
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            result = llm_router.ask_model("test:1b", "фантастику без ужасов")

        self.assertEqual(result["genres"], ["фантастика", "комедия"])
        self.assertEqual(result["exclude_genres"], ["ужасы"])
        self.assertFalse(result["need_clarification"])
        self.assertEqual(result["source_model"], "test:1b")

    def test_english_genres_are_mapped(self):
        answer = {
            "genres": ["fantasy"],
            "exclude_genres": ["horror"],
            "need_clarification": "yes",
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            result = llm_router.ask_model("test:1b", "фантастику без ужасов")

        self.assertEqual(result["genres"], ["фантастика"])
        self.assertEqual(result["exclude_genres"], ["ужасы"])
        # Строка "yes" не должна превращаться в значение по умолчанию False.
        self.assertTrue(result["need_clarification"])

    def test_unknown_genres_are_dropped(self):
        answer = {
            "genres": ["фантастика", "мистика", "сетевое приключение"],
            "exclude_genres": [],
            "need_clarification": False,
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            result = llm_router.ask_model("test:1b", "запрос")

        self.assertEqual(result["genres"], ["фантастика"])

    def test_genre_both_wanted_and_excluded_is_removed(self):
        answer = {
            "genres": ["ужасы", "фантастика"],
            "exclude_genres": ["ужасы"],
            "need_clarification": False,
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            result = llm_router.ask_model("test:1b", "запрос")

        self.assertEqual(result["genres"], ["фантастика"])
        self.assertEqual(result["exclude_genres"], ["ужасы"])

    def test_empty_genres_force_clarification(self):
        answer = {
            "genres": [],
            "exclude_genres": [],
            "need_clarification": False,
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            result = llm_router.ask_model("test:1b", "посоветуй что-нибудь")

        self.assertTrue(result["need_clarification"])

    def test_genres_must_be_list(self):
        answer = {
            "genres": "фантастика",
            "exclude_genres": [],
            "need_clarification": False,
        }

        with mock.patch(
            "urllib.request.urlopen",
            return_value=fake_response(answer),
        ):
            with self.assertRaises(ValueError):
                llm_router.ask_model("test:1b", "запрос")

    def test_broken_json_raises(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps(
            {"message": {"content": "не json"}}
        ).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with mock.patch("urllib.request.urlopen", return_value=response):
            with self.assertRaises(json.JSONDecodeError):
                llm_router.ask_model("test:1b", "запрос")


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(
            os.environ,
            {"OLLAMA_MODEL": "primary:1b", "OLLAMA_BACKUP_MODEL": "backup:1b"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_primary_answers_backup_is_not_called(self):
        calls = []

        def fake_ask(model, text):
            calls.append(model)
            return {
                "genres": ["фантастика"],
                "exclude_genres": ["ужасы"],
                "need_clarification": False,
                "source_model": model,
            }

        with mock.patch.object(llm_router, "ask_model", side_effect=fake_ask):
            result = llm_router.parse_with_fallback("фантастику без ужасов")

        self.assertEqual(calls, ["primary:1b"])
        self.assertEqual(result["source_model"], "primary:1b")

    def test_backup_answers_when_primary_fails(self):
        calls = []

        def fake_ask(model, text):
            calls.append(model)
            if model == "primary:1b":
                raise ValueError("модель недоступна")
            return {
                "genres": ["фантастика"],
                "exclude_genres": ["ужасы"],
                "need_clarification": False,
                "source_model": model,
            }

        with mock.patch.object(llm_router, "ask_model", side_effect=fake_ask):
            result = llm_router.parse_with_fallback("фантастику без ужасов")

        self.assertEqual(calls, ["primary:1b", "backup:1b"])
        self.assertEqual(result["source_model"], "backup:1b")
        self.assertEqual(len(result["fallback_chain"]), 1)
        self.assertIn("primary:1b", result["fallback_chain"][0])

    def test_local_fallback_when_both_models_fail(self):
        def fake_ask(model, text):
            raise ValueError("сломалось")

        with mock.patch.object(llm_router, "ask_model", side_effect=fake_ask):
            result = llm_router.parse_with_fallback(
                "Посоветуй фантастику без ужасов"
            )

        self.assertEqual(result["source_model"], "local_fallback")
        self.assertIn("фантастика", result["genres"])
        self.assertIn("ужасы", result["exclude_genres"])
        self.assertEqual(len(result["fallback_chain"]), 2)

    def test_local_fallback_when_models_not_configured(self):
        with mock.patch.dict(
            os.environ,
            {"OLLAMA_MODEL": "", "OLLAMA_BACKUP_MODEL": ""},
        ):
            result = llm_router.parse_with_fallback(
                "Посоветуй фантастику без ужасов"
            )

        self.assertEqual(result["source_model"], "local_fallback")
        self.assertIn("фантастика", result["genres"])

    def test_network_error_falls_back_to_backup(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request)
            if len(calls) == 1:
                import urllib.error

                raise urllib.error.URLError("connection refused")

            return fake_response({
                "genres": ["фантастика"],
                "exclude_genres": ["ужасы"],
                "need_clarification": False,
            })

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = llm_router.parse_with_fallback("фантастику без ужасов")

        self.assertEqual(len(calls), 2)
        self.assertEqual(result["source_model"], "backup:1b")

    def test_app_still_works_with_router_attached(self):
        """app.recommend не должен падать, даже если Ollama недоступна."""
        import app

        with mock.patch.dict(
            os.environ,
            {"OLLAMA_MODEL": "down:1b", "OLLAMA_BACKUP_MODEL": ""},
        ), mock.patch(
            "urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            result = app.recommend("Посоветуй фантастику без ужасов")

        self.assertEqual(result["status"], "ok")
        for item in result["recommendations"]:
            self.assertNotIn("ужасы", item["genres"])


if __name__ == "__main__":
    unittest.main()
