import json
import re
import tempfile
import unittest
from pathlib import Path

from helpers import POLICY, REQUEST, write_safetensors
from model_intake.cli import main
from model_intake.decision import DECISION_ID

KYVERNO_PATTERN = re.compile(r"^INT-.{8}-.{8}$")  # policies/kyverno/policies/require-model-intake-record.yaml


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.weights = root / "weights"
        self.weights.mkdir()
        write_safetensors(self.weights / "model.safetensors")
        self.out = root / "out"
        self.policy = root / "policy.json"
        self.request = root / "request.json"
        self.request.write_text(json.dumps(REQUEST))
        self.write_policy(POLICY)

    def tearDown(self):
        self.tmp.cleanup()

    def write_policy(self, policy):
        self.policy.write_text(json.dumps(policy))

    def check(self):
        return main(["check", "--request", str(self.request), "--policy", str(self.policy),
                     "--weights", str(self.weights), "--signature", "sig", "--public-key", "key",
                     "--out", str(self.out)])

    def evaluate(self, score):
        results = self.out / "results.json"
        results.write_text(json.dumps({"garak": {"pass_rate": score}}))
        return main(["evaluate", "--policy", str(self.policy), "--results", str(results), "--out", str(self.out)])

    def decide(self, decision="approve"):
        return main(["decide", "--check-report", str(self.out / "check-report.json"),
                     "--evaluation-report", str(self.out / "evaluation-report.json"),
                     "--decision", decision, "--approver", "A. Owner", "--role", "SRO",
                     "--reason", "test", "--out", str(self.out)])

    def test_happy_path_issues_kyverno_compatible_id(self):
        self.assertEqual(self.check(), 0)
        bom = json.loads((self.out / "ml-bom.cdx.json").read_text())
        self.assertEqual(bom["specVersion"], "1.6")
        self.assertEqual(bom["components"][0]["type"], "machine-learning-model")
        self.assertEqual(self.evaluate(0.97), 0)
        self.assertEqual(self.decide(), 0)
        record = json.loads((self.out / "decision.json").read_text())
        self.assertRegex(record["id"], DECISION_ID)
        self.assertRegex(record["id"], KYVERNO_PATTERN)

    def test_origin_not_approved_fails(self):
        policy = dict(POLICY, allowed_origins=["US"])
        self.write_policy(policy)
        self.assertEqual(self.check(), 1)
        report = json.loads((self.out / "check-report.json").read_text())
        self.assertTrue(any("origin GB" in p for p in report["problems"]))

    def test_signature_failure_fails_closed(self):
        self.write_policy(dict(POLICY, signature_command=["false"]))
        self.assertEqual(self.check(), 1)

    def test_missing_verifier_fails_closed(self):
        self.write_policy(dict(POLICY, signature_command=["no-such-verifier-binary"]))
        self.assertEqual(self.check(), 1)
        report = json.loads((self.out / "check-report.json").read_text())
        self.assertFalse(report["signature"]["verified"])

    def test_cannot_approve_below_threshold(self):
        self.assertEqual(self.check(), 0)
        self.assertEqual(self.evaluate(0.50), 1)
        self.assertEqual(self.decide("approve"), 2)
        self.assertFalse((self.out / "decision.json").exists())

    def test_reject_is_always_recordable_and_has_no_id(self):
        self.write_policy(dict(POLICY, signature_command=["false"]))
        self.check()
        self.evaluate(0.10)
        self.assertEqual(self.decide("reject"), 0)
        record = json.loads((self.out / "decision.json").read_text())
        self.assertNotIn("id", record)


if __name__ == "__main__":
    unittest.main()
