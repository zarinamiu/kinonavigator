import time
import unittest

from app import SessionMemory


class SessionMemoryTests(unittest.TestCase):
    def test_resolve_remembers_genres_when_followup_is_unclear(self):
        memory = SessionMemory(ttl_seconds=30)

        first = memory.resolve(
            "session-a",
            {
                "genres": ["фантастика"],
                "exclude_genres": ["ужасы"],
                "need_clarification": False,
            },
        )
        second = memory.resolve(
            "session-a",
            {
                "genres": [],
                "exclude_genres": [],
                "need_clarification": True,
            },
        )

        self.assertEqual(first["genres"], ["фантастика"])
        self.assertEqual(second["genres"], ["фантастика"])
        self.assertEqual(second["exclude_genres"], ["ужасы"])
        self.assertFalse(second["need_clarification"])

    def test_sessions_are_isolated(self):
        memory = SessionMemory(ttl_seconds=30)

        memory.resolve(
            "session-a",
            {
                "genres": ["фантастика"],
                "exclude_genres": [],
                "need_clarification": False,
            },
        )

        self.assertEqual(
            memory.get("session-b"),
            {"genres": [], "exclude_genres": []},
        )

    def test_clear_removes_session(self):
        memory = SessionMemory(ttl_seconds=30)

        memory.resolve(
            "session-clear",
            {
                "genres": ["комедия"],
                "exclude_genres": [],
                "need_clarification": False,
            },
        )

        self.assertTrue(memory.clear("session-clear"))
        self.assertFalse(memory.clear("session-clear"))
        self.assertEqual(
            memory.get("session-clear"),
            {"genres": [], "exclude_genres": []},
        )

    def test_expired_session_is_not_returned(self):
        memory = SessionMemory(ttl_seconds=1)

        memory.resolve(
            "session-expire",
            {
                "genres": ["драма"],
                "exclude_genres": [],
                "need_clarification": False,
            },
        )

        time.sleep(1.1)

        self.assertEqual(
            memory.get("session-expire"),
            {"genres": [], "exclude_genres": []},
        )

    def test_empty_session_id_is_rejected(self):
        memory = SessionMemory(ttl_seconds=30)

        with self.assertRaises(ValueError):
            memory.get(" ")

        with self.assertRaises(ValueError):
            memory.clear(" ")


if __name__ == "__main__":
    unittest.main()
