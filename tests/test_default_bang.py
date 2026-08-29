from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import default_bang


class DefaultBangTests(unittest.TestCase):
    registry = {
        "ddg": ["DuckDuckGo", "https://duckduckgo.com/?q={searchTerms}"],
        "gdrive": ["Google Drive", "https://drive.google.com/drive/u/0/search?q={searchTerms}"],
    }

    def test_any_catalog_trigger_can_become_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.json"

            label = default_bang.set_default(
                "GDRIVE", path=path, registry=self.registry
            )

            self.assertEqual(label, "Google Drive")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"version": 1, "defaultBang": "gdrive"},
            )

    def test_unknown_trigger_does_not_change_existing_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.json"
            path.write_text(
                json.dumps({"version": 1, "defaultBang": "ddg"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "not in Helium"):
                default_bang.set_default(
                    "missing", path=path, registry=self.registry
                )

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["defaultBang"],
                "ddg",
            )

    def test_update_keeps_previous_config_as_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.json"
            original = {"version": 1, "defaultBang": "ddg"}
            path.write_text(json.dumps(original), encoding="utf-8")

            default_bang.set_default(
                "gdrive", path=path, registry=self.registry
            )

            backup = path.with_name(path.name + ".bak")
            self.assertEqual(
                json.loads(backup.read_text(encoding="utf-8")), original
            )

    def test_symlink_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            path = root / "search.json"
            path.symlink_to(target)

            with self.assertRaisesRegex(RuntimeError, "non-regular"):
                default_bang.set_default(
                    "ddg", path=path, registry=self.registry
                )


if __name__ == "__main__":
    unittest.main()
