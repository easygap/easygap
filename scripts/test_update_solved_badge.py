from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

import update_solved_badge as badge


class CardUpdateTest(unittest.TestCase):
    def setUp(self):
        self.valid = badge.TARGET.read_bytes()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / "solved-ac.svg"
        self.target.write_bytes(self.valid)

    def test_unchanged_card_is_not_rewritten(self):
        before = self.target.stat().st_mtime_ns
        with patch.object(badge, "fetch_card", return_value=self.valid):
            self.assertFalse(badge.update_card(self.target))
        self.assertEqual(self.target.stat().st_mtime_ns, before)

    def test_updated_card_is_saved(self):
        updated = re.sub(
            rb'(class="rate value">)([0-9]+)',
            lambda match: match[1] + str(int(match[2]) + 1).encode(),
            self.valid,
        )
        self.assertNotEqual(updated, self.valid)
        with patch.object(badge, "fetch_card", return_value=updated):
            self.assertTrue(badge.update_card(self.target))
        self.assertEqual(self.target.read_bytes(), updated)
        self.assertFalse(self.target.with_suffix(".svg.tmp").exists())

    def test_bad_responses_preserve_existing_card(self):
        invalid = (
            b"<html>Service unavailable</html>",
            b"<svg>",
            self.valid.replace(badge.HANDLE.encode(), b"another-user"),
            self.valid.replace(b'class="solved value"', b'class="missing"'),
            self.valid.replace(b"</svg>", b'<script>alert(1)</script></svg>'),
            self.valid.replace(b"</svg>", b'<image href="https://example.com/image.png"/></svg>'),
            b"x" * (badge.MAX_BYTES + 1),
        )
        for response in invalid:
            with self.subTest(response=response[:50]):
                with patch.object(badge, "fetch_card", return_value=response):
                    with self.assertRaises((ValueError, badge.ET.ParseError)):
                        badge.update_card(self.target)
                self.assertEqual(self.target.read_bytes(), self.valid)

    def test_network_failure_preserves_existing_card(self):
        with patch.object(badge, "urlopen", side_effect=URLError("unavailable")) as request:
            with patch.object(badge.time, "sleep"):
                with self.assertRaises(URLError):
                    badge.update_card(self.target)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(self.target.read_bytes(), self.valid)


if __name__ == "__main__":
    unittest.main()
