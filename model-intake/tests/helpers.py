import json
import struct
from pathlib import Path


def write_safetensors(path: Path, tensors: dict | None = None) -> None:
    header = tensors or {"w": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]}}
    raw = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + b"\x00" * 8)


POLICY = {
    "allowed_origins": ["GB", "FR"],
    "allowed_licences": ["Apache-2.0"],
    "weight_extensions": [".safetensors"],
    "allowed_aux_extensions": [".json", ".txt"],
    "forbidden_extensions": [".bin", ".pt", ".pkl"],
    "signature_command": ["true"],
    "evaluations": [{"name": "garak", "metric": "pass_rate", "minimum": 0.95}],
}

REQUEST = {
    "model_name": "Test-Model",
    "model_version": "1",
    "supplier": "Test Supplier",
    "origin_country": "GB",
    "licence": "Apache-2.0",
    "source": "https://example.invalid/model",
    "intended_use": "unit test",
    "classification": "OFFICIAL",
}
