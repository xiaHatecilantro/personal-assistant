import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.chat import validate_base_url


class ChatSecurityTests(unittest.TestCase):
    def test_validate_base_url_accepts_configured_cloud_endpoint(self):
        allowed = ("https://api.deepseek.com/v1",)

        self.assertEqual(
            validate_base_url("https://api.deepseek.com/v1/", allowed),
            "https://api.deepseek.com/v1",
        )

    def test_validate_base_url_rejects_private_network_target(self):
        with self.assertRaisesRegex(ValueError, "不允许访问"):
            validate_base_url("http://169.254.169.254/latest/meta-data", ())

    def test_validate_base_url_rejects_prefix_lookalike(self):
        allowed = ("https://api.openai.com/v1",)

        with self.assertRaisesRegex(ValueError, "不允许访问"):
            validate_base_url("https://api.openai.com.evil.test/v1", allowed)


if __name__ == "__main__":
    unittest.main()
