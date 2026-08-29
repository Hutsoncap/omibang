from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bangs


class BangRegistryTests(unittest.TestCase):
    def test_jsonc_registry_parses_comments_and_trailing_commas(self) -> None:
        raw = """
        // generated registry
        [
          {
            "s": "YouTube",
            "ts": ["yt", "youtube",],
            "u": "https://youtube.com/results?search_query={searchTerms}",
          },
        ]
        """

        compact = bangs.compact_registry(bangs.parse_jsonc(raw))

        expected = [
            "YouTube",
            "https://youtube.com/results?search_query={searchTerms}",
        ]
        self.assertEqual(compact["yt"], expected)
        self.assertEqual(compact["youtube"], expected)

    def test_registry_accepts_primary_and_alias_triggers(self) -> None:
        compact = bangs.compact_registry(
            [
                {
                    "s": "GitHub",
                    "t": "gh",
                    "ts": ["github", "bad trigger"],
                    "u": "https://github.com/search?q={searchTerms}",
                },
                {
                    "s": "Unsafe",
                    "t": "unsafe",
                    "u": "javascript:alert(1)",
                },
            ]
        )
        self.assertEqual(set(compact), {"gh", "github"})

    def test_menu_query_resolves_exact_bang_and_encoded_terms(self) -> None:
        registry = {
            "yt": [
                "YouTube",
                "https://youtube.com/results?search_query={searchTerms}",
            ]
        }

        result = bangs.resolve_query(" !YT two words & more ", registry)

        self.assertEqual(
            result,
            {
                "query": "!YT two words & more",
                "trigger": "yt",
                "label": "YouTube",
                "template": "https://youtube.com/results?search_query={searchTerms}",
                "terms": "two words & more",
                "url": "https://youtube.com/results?search_query=two%20words%20%26%20more",
            },
        )

    def test_menu_query_without_terms_selects_bang_without_url(self) -> None:
        registry = {
            "yt": [
                "YouTube",
                "https://youtube.com/results?search_query={searchTerms}",
            ]
        }

        result = bangs.resolve_query("!yt", registry)

        self.assertEqual(result["trigger"], "yt")
        self.assertEqual(result["terms"], "")
        self.assertEqual(result["url"], "")

    def test_menu_query_rejects_unknown_or_non_bang_input(self) -> None:
        registry = {
            "yt": [
                "YouTube",
                "https://youtube.com/results?search_query={searchTerms}",
            ]
        }

        self.assertIsNone(bangs.resolve_query("yt cats", registry))
        self.assertIsNone(bangs.resolve_query("!unknown cats", registry))

    def test_fresh_cache_avoids_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bangs.json"
            payload = {
                "version": 1,
                "updatedAt": 1000,
                "bangs": {"yt": ["YouTube", "https://youtube.com?q={searchTerms}"]},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch.object(bangs, "fetch_registry") as fetch:
                result = bangs.load_registry(path=path, now=1001)

            fetch.assert_not_called()
            self.assertEqual(result, payload["bangs"])

    def test_stale_cache_survives_refresh_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bangs.json"
            payload = {
                "version": 1,
                "updatedAt": 1,
                "bangs": {"yt": ["YouTube", "https://youtube.com?q={searchTerms}"]},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch.object(
                bangs, "fetch_registry", side_effect=OSError("offline")
            ):
                result = bangs.load_registry(
                    path=path, now=bangs.CACHE_TTL_SECONDS + 2
                )

            self.assertEqual(result, payload["bangs"])


if __name__ == "__main__":
    unittest.main()
