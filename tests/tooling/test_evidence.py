"""Evidence invariants: truthful outcomes, bounded disclosure and integrity checks."""

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import record_verification
import check_repository


class EvidenceTests(unittest.TestCase):
    def test_failure_and_output_contents_are_not_exported(self):
        class Fixture(unittest.TestCase):
            def runTest(self):
                print("sensitive-marker-that-must-not-persist")
                self.fail("sensitive-marker-that-must-not-persist")
        result = record_verification.run_suite(unittest.TestSuite([Fixture()]))
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["cases"][0]["outcome"], "failure")
        self.assertNotIn("sensitive-marker", json.dumps(result))

    def test_empty_or_skipped_suites_do_not_accredit_success(self):
        class Fixture(unittest.TestCase):
            def runTest(self):
                self.skipTest("synthetic skip")
        self.assertFalse(record_verification.run_suite(unittest.TestSuite())["all_passed"])
        self.assertFalse(record_verification.run_suite(unittest.TestSuite([Fixture()]))["all_passed"])

    def test_unmapped_or_stale_catalog_entries_block_complete_traceability(self):
        tests = {"cases": [{"id": "suite.current"}]}
        self.assertFalse(record_verification.catalog_coverage(tests, {"cases": []})["complete"])
        self.assertFalse(record_verification.catalog_coverage(tests, {"cases": [{"method": "suite.old"}]})["complete"])
        self.assertTrue(record_verification.catalog_coverage(tests, {"cases": [{"method": "suite.current"}]})["complete"])

    def test_source_mutation_changes_aggregate_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "AGENTS.md"
            source.write_text("before")
            before = record_verification.snapshot(root)
            source.write_text("after")
            self.assertNotEqual(before["aggregate_sha256"], record_verification.snapshot(root)["aggregate_sha256"])

    def test_integrity_detects_modified_artifact_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "record"
            result = {"record_id": "EV-TEST-001", "started_at_utc": "2026-10-16T00:00:00+00:00",
                      "accepted": True, "tests": {"count": 1}, "checks": []}
            record_verification.write_record(output, result, {"files": []})
            self.assertTrue(record_verification.verify_record(output))
            (output / "results.json").write_text("{}")
            self.assertFalse(record_verification.verify_record(output))
            with self.assertRaises(FileExistsError):
                record_verification.write_record(output, result, {"files": []})
