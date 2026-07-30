import unittest

from networking.difficulty import accept_network_difficulty, parse_difficulty_payload


class DifficultyTests(unittest.TestCase):
    def test_accepts_lower_live_difficulty(self) -> None:
        self.assertEqual(accept_network_difficulty(100, fallback=1100), 100)

    def test_accepts_higher_live_difficulty(self) -> None:
        self.assertEqual(accept_network_difficulty(1200, fallback=1100), 1200)

    def test_invalid_value_uses_fallback(self) -> None:
        self.assertEqual(accept_network_difficulty(0, fallback=1100), 1100)
        self.assertEqual(accept_network_difficulty(-5, fallback=100), 100)

    def test_parse_json_object(self) -> None:
        self.assertEqual(parse_difficulty_payload('{"difficulty": 3100}'), 3100)
        self.assertEqual(parse_difficulty_payload('{"diff": 1100}'), 1100)
        self.assertEqual(parse_difficulty_payload('{"memory_cost": 2100}'), 2100)

    def test_parse_bare_number(self) -> None:
        self.assertEqual(parse_difficulty_payload("3100"), 3100)
        self.assertEqual(parse_difficulty_payload("  900\n"), 900)

    def test_parse_nested(self) -> None:
        self.assertEqual(
            parse_difficulty_payload('{"data":{"difficulty": 2750}}'),
            2750,
        )

    def test_parse_rejects_garbage(self) -> None:
        self.assertIsNone(parse_difficulty_payload(""))
        self.assertIsNone(parse_difficulty_payload("{}"))
        self.assertIsNone(parse_difficulty_payload('{"difficulty": 0}'))


if __name__ == "__main__":
    unittest.main()
