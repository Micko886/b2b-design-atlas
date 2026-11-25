"""Safety gate for V50 backup restoration (stdlib only)."""
import unittest
from scripts.guard_restore import validate_restore_target

class RestoreSafetyTests(unittest.TestCase):
    def test_known_production_name_rejected(self):
        with self.assertRaises(ValueError):
            validate_restore_target("postgresql://host.example/b2b_atlas_users")

    def test_explicit_disposable_database_allowed(self):
        self.assertTrue(validate_restore_target("postgresql://host.example/atlas_restore_v50"))

    def test_source_target_equality_rejected(self):
        url = "postgresql://host.example/atlas_restore_v50"
        with self.assertRaises(ValueError):
            validate_restore_target(url, url)

    def test_source_target_with_other_credentials_rejected(self):
        a = "postgresql://bob:one@host.example:5432/atlas_restore_v50"
        b = "postgresql://alice:two@host.example:5432/atlas_restore_v50"
        with self.assertRaises(ValueError):
            validate_restore_target(a, b)

    def test_missing_target_rejected(self):
        with self.assertRaises(ValueError):
            validate_restore_target("")

    def test_non_postgres_urls_rejected(self):
        with self.assertRaises(ValueError):
            validate_restore_target("sqlite:///atlas_restore_v50")

if __name__ == "__main__":
    unittest.main()
