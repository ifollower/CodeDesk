import tempfile
from pathlib import Path
import unittest

from codedesk_env import load_env_file, validate_release_config


class CodeDeskEnvTests(unittest.TestCase):
    def test_loader_preserves_url_fragments_and_base64_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "CODEDESK_DOCS_X11_URL=https://example.com/docs#x11\n"
                "CODEDESK_RENDEZVOUS_PUBLIC_KEY=YWJjZA==\n",
                encoding="utf-8",
            )
            values = load_env_file(path, missing_ok=False)
        self.assertEqual(values["CODEDESK_DOCS_X11_URL"], "https://example.com/docs#x11")
        self.assertEqual(values["CODEDESK_RENDEZVOUS_PUBLIC_KEY"], "YWJjZA==")

    def test_release_validation_rejects_rustdesk_and_invalid_key(self):
        errors = validate_release_config(
            {
                "CODEDESK_SOURCE_URL": "https://github.com/rustdesk/rustdesk",
                "CODEDESK_RENDEZVOUS_SERVERS": "rs-ny.rustdesk.com",
                "CODEDESK_RENDEZVOUS_PUBLIC_KEY": "invalid",
            }
        )
        self.assertTrue(any("RustDesk infrastructure" in error for error in errors))
        self.assertTrue(any("valid base64" in error for error in errors))

    def test_release_validation_rejects_empty_and_invalid_urls(self):
        errors = validate_release_config(
            {
                "CODEDESK_SOURCE_URL": "not-a-url",
                "CODEDESK_RENDEZVOUS_SERVERS": "id.example.com",
                "CODEDESK_RENDEZVOUS_PUBLIC_KEY": (
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
                ),
            }
        )
        self.assertTrue(any("CODEDESK_WEBSITE_URL is required" in error for error in errors))
        self.assertTrue(any("CODEDESK_SOURCE_URL must be" in error for error in errors))

    def test_release_validation_accepts_multiple_servers(self):
        values = {
            "CODEDESK_RENDEZVOUS_SERVERS": "id1.example.com,id2.example.com:21116",
            "CODEDESK_RENDEZVOUS_PUBLIC_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        }
        for key in (
            "CODEDESK_SOURCE_URL",
            "CODEDESK_ISSUES_URL",
            "CODEDESK_WEBSITE_URL",
            "CODEDESK_DOWNLOAD_URL",
            "CODEDESK_PRIVACY_URL",
            "CODEDESK_DOCS_URL",
            "CODEDESK_DOCS_MOBILE_URL",
            "CODEDESK_DOCS_LINUX_PERMISSIONS_URL",
            "CODEDESK_DOCS_X11_URL",
            "CODEDESK_DOCS_LINUX_LOGIN_URL",
            "CODEDESK_DOCS_HEADLESS_URL",
            "CODEDESK_DOCS_WHITELIST_URL",
        ):
            values[key] = "https://example.com/path"
        self.assertEqual(validate_release_config(values), [])


if __name__ == "__main__":
    unittest.main()
