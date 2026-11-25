"""V50 public-catalog visibility regression tests (run during Docker build)."""
import json
import unittest
from app.cms_routes import published_overrides


def entry(status, published_json=None, kind="article", slug="original-article"):
    return {"status": status, "published_json": published_json, "kind": kind, "slug": slug}


class ContentVisibilityTests(unittest.TestCase):
    def test_archived_original_does_not_reappear_while_drafting(self):
        key = ("article", "original-article")
        self.assertEqual(published_overrides([entry("archived")], {key}), {key: None})
        self.assertEqual(published_overrides([entry("draft")], {key}), {key: None})
        self.assertEqual(published_overrides([entry("review")], {key}), {key: None})

    def test_republishing_archived_record_replaces_tombstone(self):
        key = ("article", "original-article")
        snapshot = {"id": "original-article", "title": "Restored publicly"}
        self.assertEqual(
            published_overrides([entry("published", json.dumps(snapshot))], {key}),
            {key: snapshot},
        )

    def test_draft_never_leaks_new_resource(self):
        self.assertEqual(published_overrides([entry("draft", slug="new")], set()), {})

    def test_published_snapshot_stays_visible_during_subsequent_edit(self):
        key = ("article", "original-article")
        snapshot = {"id": "original-article", "title": "Previously published"}
        self.assertEqual(
            published_overrides([entry("draft", json.dumps(snapshot))], set()),
            {key: snapshot},
        )


if __name__ == "__main__":
    unittest.main()
