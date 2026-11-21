import unittest

from model_intake.decision import decide

MANIFEST = "a" * 64
WEIGHTS = "registry.example.invalid/models/test-model@sha256:" + "b" * 64


def check_report(manifest=MANIFEST, passed=True):
    return {"passed": passed, "manifest_sha256": manifest,
            "request": {"model_name": "Test-Model", "model_version": "1", "origin_country": "GB"}}


def evaluation_report(manifest=MANIFEST, name="Test-Model", version="1", passed=True):
    return {"passed": passed, "results": [],
            "subject": {"model_name": name, "model_version": version, "manifest_sha256": manifest}}


def approve(check, evaluation, weights_image=WEIGHTS):
    return decide(check, evaluation, decision="approve", approver="A. Owner", role="SRO", reason="test",
                  weights_image=weights_image)


class Decide(unittest.TestCase):
    def test_approval_binds_the_weights_artefact_digest(self):
        record = approve(check_report(), evaluation_report())
        self.assertEqual(record["weights_image"], WEIGHTS)
        self.assertEqual(record["weights_digest"], "sha256:" + "b" * 64)
        self.assertEqual(record["admission"], {"configmap": "kyverno/model-intake-decisions",
                                               "key": record["id"], "value": WEIGHTS})

    def test_evaluation_of_other_weights_is_refused(self):
        with self.assertRaisesRegex(ValueError, "manifest"):
            approve(check_report(), evaluation_report(manifest="c" * 64))

    def test_evaluation_of_other_model_is_refused(self):
        with self.assertRaisesRegex(ValueError, "model"):
            approve(check_report(), evaluation_report(name="Other-Model"))
        with self.assertRaisesRegex(ValueError, "model"):
            approve(check_report(), evaluation_report(version="2"))

    def test_evaluation_without_subject_is_refused(self):
        with self.assertRaisesRegex(ValueError, "subject"):
            approve(check_report(), {"passed": True, "results": []})

    def test_weights_image_must_be_pinned_by_digest(self):
        for ref in ("", "registry.example.invalid/models/test-model:1",
                    "registry.example.invalid/models/test-model@sha256:short"):
            with self.assertRaisesRegex(ValueError, "digest"):
                approve(check_report(), evaluation_report(), weights_image=ref)

    def test_reject_needs_no_weights_image(self):
        record = decide(check_report(passed=False), None, decision="reject", approver="A. Owner", role="SRO",
                        reason="test")
        self.assertNotIn("id", record)
        self.assertNotIn("admission", record)


if __name__ == "__main__":
    unittest.main()
