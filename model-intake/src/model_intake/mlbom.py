"""CycloneDX 1.6 machine-learning bill of materials (ML-BOM) for an intake candidate."""

from __future__ import annotations

import datetime as dt
import uuid

from .files import FileRecord


def build_mlbom(request: dict, records: list[FileRecord], manifest_sha256: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    model_ref = f"model:{request['model_name']}@{request['model_version']}"
    file_components = [
        {
            "type": "data" if r.kind == "weights" else "file",
            "bom-ref": f"file:{r.path}",
            "name": r.path,
            "hashes": [{"alg": "SHA-256", "content": r.sha256}],
            "properties": [
                {"name": "innovox:file-kind", "value": r.kind},
                {"name": "innovox:size-bytes", "value": str(r.size)},
            ],
        }
        for r in records
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": now,
            "tools": {"components": [{"type": "application", "name": "model-intake", "version": "0.1.0"}]},
            "component": {"type": "machine-learning-model", "bom-ref": model_ref,
                          "name": request["model_name"], "version": request["model_version"]},
        },
        "components": [
            {
                "type": "machine-learning-model",
                "bom-ref": model_ref,
                "name": request["model_name"],
                "version": request["model_version"],
                "supplier": {"name": request["supplier"]},
                "licenses": [{"license": {"id": request["licence"]}}],
                "externalReferences": [{"type": "distribution", "url": request["source"]}],
                "hashes": [{"alg": "SHA-256", "content": manifest_sha256}],
                "properties": [
                    {"name": "innovox:origin-country", "value": request["origin_country"].upper()},
                    {"name": "innovox:classification", "value": request["classification"]},
                    {"name": "innovox:intended-use", "value": request["intended_use"]},
                    {"name": "innovox:manifest-sha256", "value": manifest_sha256},
                ],
                "components": file_components,
            }
        ],
    }
