import unittest

from agent_tools import call_tool


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

    def test_profile_can_be_saved_and_read(self):
        call_tool(
            "save_user_preferences",
            {"user_id": "tool_test_user", "genres": ["фантастика"]},
        )
        result = call_tool(
            "get_user_profile",
            {"user_id": "tool_test_user"},
        )
        self.assertEqual(result, ["фантастика"])

    # --- дополнительные проверки границ, сверх минимального набора ---

    def test_file_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("read_file", {"path": "/etc/passwd"})

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

    def test_long_request_is_rejected(self):
        with self.assertRaises(ValueError):
            call_tool("recommend_movies", {"request_text": "а" * 501})

    def test_recommend_movies_respects_exclusion(self):
        result = call_tool(
            "recommend_movies",
            {"request_text": "Посоветуй фантастику без ужасов"},
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["recommendations"])
        for item in result["recommendations"]:
            self.assertNotIn("ужасы", item["genres"])

    def test_movie_id_must_be_integer(self):
        with self.assertRaises(ValueError):
            call_tool("get_movie_details", {"movie_id": "1"})


if __name__ == "__main__":
    unittest.main()
