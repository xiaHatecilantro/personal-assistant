import sys
import unittest
import io
import zipfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_parser import parse_document, parse_document_isolated


class DocumentParserTests(unittest.TestCase):
    def test_parse_document_decodes_markdown(self):
        self.assertEqual(parse_document("readme.md", "你好".encode()), "你好")

    def test_parse_document_strips_html_navigation_and_scripts(self):
        html = b"<nav>menu</nav><main><h1>Title</h1><p>Body</p></main><script>bad()</script>"

        content = parse_document("page.html", html)

        self.assertIn("Title", content)
        self.assertIn("Body", content)
        self.assertNotIn("menu", content)
        self.assertNotIn("bad", content)

    def test_parse_document_rejects_unsupported_extension(self):
        with self.assertRaisesRegex(ValueError, "不支持的格式"):
            parse_document("archive.zip", b"data")

    def test_parse_document_rejects_suspicious_ooxml_compression_ratio(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b"0" * (2 * 1024 * 1024))

        with self.assertRaisesRegex(ValueError, "压缩资源限制"):
            parse_document("bomb.docx", buffer.getvalue())

    def test_isolated_parser_enforces_hard_timeout(self):
        with self.assertRaises(TimeoutError):
            parse_document_isolated("readme.md", b"hello", timeout=0)

    def test_isolated_parser_returns_successful_result(self):
        self.assertEqual(
            parse_document_isolated("readme.md", "你好".encode(), timeout=5),
            "你好",
        )


if __name__ == "__main__":
    unittest.main()
