"""Weight-file checks: safetensors only, no pickle payloads, and a SHA-256 manifest of every file."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

# Pickle protocol 2-5 streams start with 0x80 followed by the protocol number.
PICKLE_MAGICS = (b"\x80\x02", b"\x80\x03", b"\x80\x04", b"\x80\x05")
ZIP_MAGIC = b"PK\x03\x04"  # PyTorch .pt/.bin checkpoints are zip archives holding pickles
MAX_SAFETENSORS_HEADER = 100 * 1024 * 1024


@dataclass
class FileRecord:
    path: str
    size: int
    sha256: str
    kind: str  # weights | auxiliary


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_safetensors_header(path: Path) -> str | None:
    """Return a problem description, or None when the file has a well-formed safetensors header."""
    with open(path, "rb") as fh:
        raw = fh.read(8)
        if len(raw) != 8:
            return "too short to be safetensors"
        (header_len,) = struct.unpack("<Q", raw)
        if header_len == 0 or header_len > MAX_SAFETENSORS_HEADER:
            return f"implausible safetensors header length {header_len}"
        header = fh.read(header_len)
    if len(header) != header_len:
        return "truncated safetensors header"
    try:
        meta = json.loads(header.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "safetensors header is not valid JSON"
    if not isinstance(meta, dict):
        return "safetensors header is not a JSON object"
    for name, info in meta.items():
        if name == "__metadata__":
            continue
        if not isinstance(info, dict) or not {"dtype", "shape", "data_offsets"} <= info.keys():
            return f"tensor entry '{name}' is malformed"
    return None


def looks_like_pickle(path: Path) -> bool:
    with open(path, "rb") as fh:
        head = fh.read(4)
    return head[:2] in PICKLE_MAGICS or head == ZIP_MAGIC


def scan_weights(weights_dir: Path, weight_ext: list[str], aux_ext: list[str], forbidden_ext: list[str]):
    """Scan a model directory. Returns (records, problems)."""
    records: list[FileRecord] = []
    problems: list[str] = []
    if not weights_dir.is_dir():
        return records, [f"weights directory {weights_dir} does not exist"]
    files = sorted(p for p in weights_dir.rglob("*") if p.is_file())
    if not files:
        return records, ["weights directory is empty"]
    for path in files:
        rel = path.relative_to(weights_dir).as_posix()
        if path.is_symlink():
            problems.append(f"{rel}: symbolic links are not accepted")
            continue
        ext = path.suffix.lower()
        if ext in forbidden_ext:
            problems.append(f"{rel}: format {ext} can carry executable pickle code and is refused")
            continue
        if ext in weight_ext:
            issue = check_safetensors_header(path)
            if issue:
                problems.append(f"{rel}: {issue}")
                continue
            kind = "weights"
        elif ext in aux_ext:
            if looks_like_pickle(path):
                problems.append(f"{rel}: auxiliary file contains a pickle or zip payload")
                continue
            kind = "auxiliary"
        else:
            problems.append(f"{rel}: extension '{ext or '(none)'}' is not on the policy allowlist")
            continue
        records.append(FileRecord(rel, path.stat().st_size, sha256_file(path), kind))
    if not any(r.kind == "weights" for r in records) and not problems:
        problems.append("no weight files found")
    return records, problems


def write_manifest(records: list[FileRecord], out_path: Path) -> str:
    """Write a sha256sum-style manifest and return its own SHA-256."""
    lines = "".join(f"{r.sha256}  {r.path}\n" for r in sorted(records, key=lambda r: r.path))
    out_path.write_text(lines, encoding="utf-8")
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()
