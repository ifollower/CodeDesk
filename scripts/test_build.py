import unittest
from unittest import mock

import build


class BuildScriptTests(unittest.TestCase):
    @mock.patch("build.shutil.which")
    def test_resolve_flutter_command_preserves_windows_batch_path(self, which):
        which.return_value = r"C:\hostedtoolcache\flutter\bin\flutter.bat"

        resolved = build.resolve_flutter_command("flutter")

        self.assertEqual(
            resolved, r"C:\hostedtoolcache\flutter\bin\flutter.bat"
        )
        which.assert_called_once_with("flutter")


if __name__ == "__main__":
    unittest.main()
