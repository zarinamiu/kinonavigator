import unittest

from app import (
    MOVIE_BY_ID,
    parse_request_locally,
    recommend_popular,
    recommend_content,
    recommend_item_cf,
    recommend_hybrid,
    validate_recommendations,
    recommend,
    save_profile,
    load_profile,
)


class KinoNavigatorTests(unittest.TestCase):

    def test_parse_fantasy_without_horror(self):
        result = parse_request_locally(
            "Посоветуй фантастику без ужасов"
        )
        self.assertIn("фантастика", result["genres"])
        self.assertIn("ужасы", result["exclude_genres"])
        self.assertFalse(result["need_clarification"])

    def test_unclear_request_needs_clarification(self):
        result = parse_request_locally("Посоветуй что-нибудь")
        self.assertTrue(result["need_clarification"])

    def test_algorithms_return_existing_movie_ids(self):
        results = [
            recommend_popular(),
            recommend_content(["фантастика"]),
            recommend_item_cf(1),
            recommend_hybrid(["фантастика"], 1),
        ]

        for recommendations in results:
            self.assertTrue(recommendations)
            for movie_id, _ in recommendations:
                self.assertIn(movie_id, MOVIE_BY_ID)

    def test_item_cf_does_not_return_movies_user_has_seen(self):
        results = recommend_item_cf(1)
        ids = [movie_id for movie_id, _ in results]
        already_seen = {1, 2, 3, 4, 9, 11}

        self.assertTrue(set(ids).isdisjoint(already_seen))

    def test_validator_removes_forbidden_horror(self):
        candidates = [(6, 1.0), (1, 0.8)]
        checked = validate_recommendations(candidates, ["ужасы"])
        ids = [movie_id for movie_id, _ in checked]

        self.assertNotIn(6, ids)
        self.assertIn(1, ids)

    def test_new_user_can_get_recommendations(self):
        result = recommend("фантастика", user_id="new_user")
        self.assertEqual(result["status"], "ok")

    def test_unclear_new_user_gets_question(self):
        result = recommend(
            "Посоветуй что-нибудь",
            user_id="brand_new_user",
        )
        self.assertEqual(result["status"], "clarification")

    def test_answer_obeys_genre_exclusion(self):
        result = recommend(
            "фантастика без ужасов",
            user_id="new_user",
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["recommendations"])

        for movie in result["recommendations"]:
            self.assertNotIn("ужасы", movie["genres"])

    def test_profile_can_be_saved_and_loaded(self):
        save_profile("test_user", ["фантастика"])
        self.assertEqual(load_profile("test_user"), ["фантастика"])


if __name__ == "__main__":
    unittest.main()
