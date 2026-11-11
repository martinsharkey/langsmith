import tempfile
import unittest
from pathlib import Path

from helpers import write_safetensors
from model_intake.files import check_safetensors_header, scan_weights, write_manifest

W, AUX, BAD = [".safetensors"], [".json"], [".bin", ".pt", ".pkl"]


class FileChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_safetensors_accepted(self):
        write_safetensors(self.dir / "model.safetensors")
        (self.dir / "config.json").write_text("{}")
        records, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertEqual(problems, [])
        self.assertEqual({r.kind for r in records}, {"weights", "auxiliary"})

    def test_pickle_formats_refused(self):
        write_safetensors(self.dir / "model.safetensors")
        (self.dir / "pytorch_model.bin").write_bytes(b"PK\x03\x04rest")
        _, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertTrue(any("pytorch_model.bin" in p and "pickle" in p for p in problems))

    def test_pickle_payload_hidden_in_aux_file_refused(self):
        write_safetensors(self.dir / "model.safetensors")
        (self.dir / "tokenizer.json").write_bytes(b"\x80\x04\x95payload")
        _, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertTrue(any("tokenizer.json" in p for p in problems))

    def test_corrupt_safetensors_refused(self):
        (self.dir / "model.safetensors").write_bytes(b"\xff" * 16)
        self.assertIsNotNone(check_safetensors_header(self.dir / "model.safetensors"))
        _, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertTrue(problems)

    def test_unknown_extension_refused(self):
        write_safetensors(self.dir / "model.safetensors")
        (self.dir / "run.sh").write_text("echo hi")
        _, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertTrue(any("run.sh" in p for p in problems))

    def test_symlink_refused(self):
        write_safetensors(self.dir / "model.safetensors")
        (self.dir / "link.json").symlink_to(self.dir / "model.safetensors")
        _, problems = scan_weights(self.dir, W, AUX, BAD)
        self.assertTrue(any("symbolic" in p for p in problems))

    def test_manifest_is_stable(self):
        write_safetensors(self.dir / "a.safetensors")
        records, _ = scan_weights(self.dir, W, AUX, BAD)
        h1 = write_manifest(records, self.dir.parent / "m1")
        h2 = write_manifest(list(reversed(records)), self.dir.parent / "m2")
        self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
