import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from mining.native_lib import (
    build_hint,
    cuda_lib_basename,
    default_cuda_lib_relative,
    lane_lib_name,
    resolve_cuda_lib_path,
)


class NativeLibTests(unittest.TestCase):
    def test_basename_matches_platform(self) -> None:
        name = cuda_lib_basename()
        if sys.platform == "win32":
            self.assertTrue(name.endswith(".dll"))
        else:
            self.assertTrue(name.endswith(".so") or name.endswith(".dylib"))

    def test_default_relative_path(self) -> None:
        rel = default_cuda_lib_relative()
        self.assertTrue(rel.startswith("native/build/bin/"))
        self.assertIn(cuda_lib_basename(), rel)

    def test_lane_lib_extension(self) -> None:
        name = lane_lib_name(1)
        self.assertTrue(name.startswith("lane1."))
        if sys.platform == "win32":
            self.assertTrue(name.endswith(".dll"))
        else:
            self.assertTrue(name.endswith(".so"))

    def test_resolve_prefers_existing_file(self) -> None:
        # Use this test file as a stand-in "library" path
        existing = Path(__file__).resolve()
        resolved = resolve_cuda_lib_path(existing)
        self.assertEqual(resolved.resolve(), existing)

    def test_resolve_falls_back_when_missing(self) -> None:
        missing = Path("native/build/bin/does_not_exist_xyz.dll")
        resolved = resolve_cuda_lib_path(missing)
        # Returns a Path even when missing (for clear FileNotFoundError later)
        self.assertIsInstance(resolved, Path)

    def test_build_hint_mentions_script(self) -> None:
        hint = build_hint()
        self.assertIn("build", hint.lower())


if __name__ == "__main__":
    unittest.main()
