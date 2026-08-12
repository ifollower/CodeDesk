import tempfile
import unittest
from unittest import mock
from pathlib import Path

import release


class ReleaseScriptTests(unittest.TestCase):
    def test_repository_versions_match(self):
        flutter_version, build_number = release.flutter_version()
        self.assertEqual(release.cargo_version(), flutter_version)
        self.assertTrue(build_number.isdigit())

    def test_normalize_version(self):
        self.assertEqual("1.2.3", release.normalize_version("v1.2.3"))
        with self.assertRaises(release.ReleaseError):
            release.normalize_version("1.2")

    def test_dev_release_check_does_not_require_public_configuration(self):
        with mock.patch.dict(release.os.environ, {}, clear=True):
            release.release_check(release.cargo_version(), profile="dev")

    def test_release_check_requires_public_configuration(self):
        with mock.patch.dict(release.os.environ, {}, clear=True):
            with self.assertRaises(release.ReleaseError):
                release.release_check(release.cargo_version(), profile="release")

    @mock.patch("release.run")
    @mock.patch("release.subprocess.run")
    @mock.patch("release.command_exists", return_value=True)
    def test_release_rust_requires_rustfmt(
        self, _command_exists, subprocess_run, run
    ):
        run.return_value.stdout = "1.87.0-x86_64-pc-windows-msvc\n"
        subprocess_run.return_value.returncode = 1
        with self.assertRaisesRegex(release.ReleaseError, "rustfmt is required"):
            release.ensure_release_rust()

    def test_ios_export_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ExportOptions.plist"
            release._write_export_options(
                destination,
                method="app-store",
                team_id="TEAM123",
                profile_name="codedesk-ios-app-store",
            )
            contents = destination.read_text(encoding="utf-8")
            self.assertIn("<string>app-store</string>", contents)
            self.assertIn("<string>TEAM123</string>", contents)
            self.assertIn("<string>codedesk-ios-app-store</string>", contents)


if __name__ == "__main__":
    unittest.main()
