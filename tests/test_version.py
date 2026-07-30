import unittest
from pathlib import Path

from core.version import USER_AGENT, __version__, banner_line, version_string


class VersionTests(unittest.TestCase):
    def test_semver_not_stuck_at_3_0_0(self) -> None:
        self.assertNotEqual(__version__, "3.0.0")
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(p.isdigit() for p in parts))

    def test_version_file_matches(self) -> None:
        root = Path(__file__).resolve().parents[1]
        file_ver = (root / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(file_ver, __version__)

    def test_banner_and_ua(self) -> None:
        self.assertIn(__version__, banner_line())
        self.assertIn(__version__, USER_AGENT)
        self.assertIn("lowdif", version_string())


if __name__ == "__main__":
    unittest.main()
