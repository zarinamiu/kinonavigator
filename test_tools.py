import unittest
from unittest.mock import patch

import app
from agent_tools import TOOLS, call_tool


class ToolTests(unittest.TestCase):
    def test_reads_existing_movie(self):
        movie = call_tool("get_movie_details", {"movie_id": 1})
        self.assertIsNotNone(movie)
        self.assertIn("title", movie)

    def test_unknown_movie_is_not_returned(self):
        movie = call_tool("get_movie_details", {"movie_id": 999999})
        self.assertIsNone(movie)

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("run_shell_command", {"command": "whoami"})

    def test_file_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("read_file", {"path": "/etc/passwd"})

    def test_profile_can_be_saved_and_read(self):
        user_id = "tool_test_user"

        result = call_tool(
            "save_user_preferences",
            {"user_id": user_id, "genres": ["фантастика"]},
        )
        self.assertEqual(result, {"status": "saved"})

        profile = call_tool(
            "get_user_profile",
            {"user_id": user_id},
        )
        self.assertEqual(profile, ["фантастика"])

    def test_unknown_genre_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool(
                "save_user_preferences",
                {"user_id": "tool_test_user", "genres": ["хоррор"]},
            )

    def test_genre_must_be_string(self):
        with self.assertRaises(ValueError):
            call_tool(
                "save_user_preferences",
                {"user_id": "tool_test_user", "genres": [1, 2]},
            )

    def test_empty_user_id_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("get_user_profile", {"user_id": "   "})

    def test_non_dict_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("get_movie_details", ["movie_id"])

    def test_unknown_algorithm_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool(
                "recommend_movies",
                {"request_text": "фантастика", "algorithm": "magic"},
            )

    def test_non_string_algorithm_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool(
                "recommend_movies",
                {"request_text": "фантастика", "algorithm": []},
            )

    def test_long_request_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool(
                "recommend_movies",
                {"request_text": "а" * 501},
            )

    def test_movie_id_must_be_integer(self):
        with self.assertRaises(ValueError):
            call_tool("get_movie_details", {"movie_id": "1"})

    def test_profile_can_be_deleted(self):
        user_id = "delete_tool_test_user"

        try:
            call_tool(
                "save_user_preferences",
                {"user_id": user_id, "genres": ["фантастика"]},
            )

            result = call_tool(
                "delete_user_profile",
                {"user_id": user_id},
            )

            self.assertEqual(result, {"status": "deleted"})
            self.assertIsNone(
                call_tool("get_user_profile", {"user_id": user_id})
            )
        finally:


            app.delete_profile(user_id)

    def test_deleting_missing_profile_returns_not_found(self):
        result = call_tool(
            "delete_user_profile",
            {"user_id": "profile_that_does_not_exist_987654"},
        )
        self.assertEqual(result, {"status": "not_found"})

    def test_delete_profile_rejects_empty_user_id(self):
        with self.assertRaises(ValueError):
            call_tool(
                "delete_user_profile",
                {"user_id": "   "},
            )

    def test_delete_and_clear_tools_are_allowlisted(self):
        self.assertIn("delete_user_profile", TOOLS)
        self.assertIn("clear_session_memory", TOOLS)

    def test_session_memory_can_be_cleared_through_tool(self):
        session_id = "tool_clear_session_test"

        app.SESSION_MEMORY.clear(session_id)
        app.SESSION_MEMORY.resolve(
            session_id,
            {
                "genres": ["фантастика"],
                "exclude_genres": ["ужасы"],
                "need_clarification": False,
            },
        )

        result = call_tool(
            "clear_session_memory",
            {"session_id": session_id},
        )

        self.assertEqual(result, {"cleared": True})
        self.assertEqual(
            app.SESSION_MEMORY.get(session_id),
            {"genres": [], "exclude_genres": []},
        )

    def test_clear_session_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            call_tool(
                "clear_session_memory",
                {"session_id": "  "},
            )

    def test_recommend_movies_respects_exclusion(self):
        parsed = {
            "genres": ["фантастика"],
            "exclude_genres": ["ужасы"],
            "need_clarification": False,
            "source_model": "test",
            "fallback_chain": [],
        }

        with patch("llm_router.parse_with_fallback", return_value=parsed):
            result = call_tool(
                "recommend_movies",
                {
                    "request_text": "Посоветуй фантастику без ужасов",
                    "session_id": "tool_recommend_exclusion_test",
                },
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["recommendations"])

        for item in result["recommendations"]:
            self.assertNotIn("ужасы", item["genres"])


if __name__ == "__main__":
    unittest.main()
