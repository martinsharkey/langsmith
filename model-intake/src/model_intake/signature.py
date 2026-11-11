"""Signature verification by an external, offline verifier (cosign or OpenSSF model signing).

The policy supplies the command as a list with placeholders {manifest}, {signature}, {public_key} and
{weights_dir}. Verification fails closed: a missing tool, a non-zero exit or a timeout all mean "not verified".
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class SignatureResult:
    verified: bool
    detail: str


def verify(command: list[str], *, manifest: str, signature: str, public_key: str, weights_dir: str,
           timeout: int = 300) -> SignatureResult:
    if not command:
        return SignatureResult(False, "policy defines no signature_command")
    values = {"manifest": manifest, "signature": signature, "public_key": public_key, "weights_dir": weights_dir}
    try:
        argv = [part.format(**values) for part in command]
    except KeyError as exc:
        return SignatureResult(False, f"unknown placeholder {exc} in signature_command")
    if shutil.which(argv[0]) is None:
        return SignatureResult(False, f"verifier '{argv[0]}' is not installed")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return SignatureResult(False, "verifier timed out")
    output = (proc.stdout + proc.stderr).strip().splitlines()
    tail = output[-1] if output else ""
    if proc.returncode != 0:
        return SignatureResult(False, f"verifier exited {proc.returncode}: {tail}")
    return SignatureResult(True, tail or "verified")
