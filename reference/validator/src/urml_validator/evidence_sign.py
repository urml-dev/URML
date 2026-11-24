"""Signed evidence reports: verify an OpenSSH signature offline (RFC-0707, step 4).

The Licensor signs a report it has reproduced and reviewed with the standard
OpenSSH tool, so the private key can live on a hardware token:

    ssh-keygen -Y sign -f <key> -n evidence-report@urml.dev report.json

That writes `report.json.sig` (the SSHSIG format, PROTOCOL.sshsig in the
OpenSSH sources). This module verifies such a signature with nothing but the
Python standard library: no OpenSSH install, no network, no account. It
accepts Ed25519 keys, plain (`ssh-ed25519`) and FIDO hardware-backed
(`sk-ssh-ed25519@openssh.com`, which must assert user presence).

Trusted keys come from an allowed-signers file in the OpenSSH format, one
key per line:

    <principal> namespaces="evidence-report@urml.dev"[,valid-after="YYYYMMDD"][,valid-before="YYYYMMDD"] <type> <base64>

The validator package ships the Licensor's file
(`urml_validator/evidence_keys/allowed_signers`). A retired key stays in the
file with a `valid-before` date, so reports it signed still verify. The
validity window is judged against the report's own `as_of` date.

A good signature means one thing: the holder of that key signed exactly these
bytes. For the Licensor that is a statement that it rebuilt the report from
inputs with these digests and reviewed it. It is not a certification and not a
statement that the robot is safe or compliant.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

#: The namespace every evidence-report signature is made in.
NAMESPACE = "evidence-report@urml.dev"

_MAGIC = b"SSHSIG"
_ARMOR_BEGIN = "-----BEGIN SSH SIGNATURE-----"
_ARMOR_END = "-----END SSH SIGNATURE-----"
_ED25519 = "ssh-ed25519"
_SK_ED25519 = "sk-ssh-ed25519@openssh.com"
_SK_USER_PRESENT = 0x01


class SignatureError(ValueError):
    """A signature, a key or an allowed-signers file could not be read."""


# ---------------------------------------------------------------------------
# Ed25519 verification (RFC 8032), on the curve's extended coordinates
# ---------------------------------------------------------------------------

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)

_Point = tuple[int, int, int, int]


def _add(a: _Point, b: _Point) -> _Point:
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    pa = (y1 - x1) * (y2 - x2) % _P
    pb = (y1 + x1) * (y2 + x2) % _P
    pc = 2 * t1 * t2 * _D % _P
    pd = 2 * z1 * z2 % _P
    e, f, g, h = pb - pa, pd - pc, pd + pc, pb + pa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(scalar: int, point: _Point) -> _Point:
    result: _Point = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(a: _Point, b: _Point) -> bool:
    x1, y1, z1, _ = a
    x2, y2, z2, _ = b
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decompress(data: bytes) -> _Point | None:
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0)
assert _GX is not None
_BASE: _Point = (_GX, _GY, 1, _GX * _GY % _P)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True when `signature` is a valid Ed25519 signature of `message` by `public_key`."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _decompress(public_key)
    r = _decompress(signature[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
    return _equal(_mul(s, _BASE), _add(r, _mul(k, a)))


# ---------------------------------------------------------------------------
# SSH wire format
# ---------------------------------------------------------------------------


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise SignatureError("the signature data ends early")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "big")

    def string(self) -> bytes:
        return self.take(self.u32())

    def done(self) -> bool:
        return self.pos == len(self.data)


def _ssh_string(data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + data


@dataclass(frozen=True)
class PublicKey:
    """An Ed25519 public key as OpenSSH writes it."""

    key_type: str
    key: bytes
    application: bytes | None = None

    @classmethod
    def from_blob(cls, blob: bytes) -> PublicKey:
        r = _Reader(blob)
        key_type = r.string().decode("ascii", "replace")
        if key_type == _ED25519:
            key = r.string()
            application = None
        elif key_type == _SK_ED25519:
            key = r.string()
            application = r.string()
        else:
            raise SignatureError(f"key type {key_type} is not accepted; evidence reports use Ed25519 keys")
        if not r.done() or len(key) != 32:
            raise SignatureError("the public key is malformed")
        return cls(key_type, key, application)

    @property
    def blob(self) -> bytes:
        out = _ssh_string(self.key_type.encode()) + _ssh_string(self.key)
        if self.application is not None:
            out += _ssh_string(self.application)
        return out

    def fingerprint(self) -> str:
        digest = base64.b64encode(hashlib.sha256(self.blob).digest()).decode().rstrip("=")
        return f"SHA256:{digest}"


@dataclass(frozen=True)
class _Sshsig:
    public_key: PublicKey
    namespace: str
    hash_algorithm: str
    signature: bytes


def _parse_sshsig(text: str) -> _Sshsig:
    lines = [line.strip() for line in text.strip().splitlines()]
    if not lines or lines[0] != _ARMOR_BEGIN or lines[-1] != _ARMOR_END:
        raise SignatureError("not an SSH signature: the armor lines are missing")
    try:
        blob = base64.b64decode("".join(lines[1:-1]), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("the signature's base64 is malformed") from exc
    r = _Reader(blob)
    if r.take(6) != _MAGIC:
        raise SignatureError("not an SSHSIG signature")
    if r.u32() != 1:
        raise SignatureError("unsupported SSHSIG version")
    public_key = PublicKey.from_blob(r.string())
    namespace = r.string().decode("utf-8", "replace")
    r.string()  # reserved
    hash_algorithm = r.string().decode("ascii", "replace")
    signature = r.string()
    if not r.done():
        raise SignatureError("trailing data after the signature")
    return _Sshsig(public_key, namespace, hash_algorithm, signature)


def _signed_data(namespace: str, hash_algorithm: str, message: bytes) -> bytes:
    digest = hashlib.sha512(message).digest() if hash_algorithm == "sha512" else hashlib.sha256(message).digest()
    return (
        _MAGIC
        + _ssh_string(namespace.encode())
        + _ssh_string(b"")
        + _ssh_string(hash_algorithm.encode())
        + _ssh_string(digest)
    )


def _verify_blob(public_key: PublicKey, data: bytes, sig_blob: bytes) -> bool:
    r = _Reader(sig_blob)
    sig_type = r.string().decode("ascii", "replace")
    if sig_type != public_key.key_type:
        return False
    raw = r.string()
    if public_key.key_type == _ED25519:
        return r.done() and ed25519_verify(public_key.key, data, raw)
    flags = r.take(1)[0]
    counter = r.take(4)
    if not r.done() or not flags & _SK_USER_PRESENT:
        return False
    assert public_key.application is not None
    signed = hashlib.sha256(public_key.application).digest() + bytes([flags]) + counter + hashlib.sha256(data).digest()
    return ed25519_verify(public_key.key, signed, raw)


# ---------------------------------------------------------------------------
# Allowed signers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllowedSigner:
    principal: str
    public_key: PublicKey
    namespaces: tuple[str, ...]
    valid_after: date | None
    valid_before: date | None


def _yyyymmdd(value: str) -> date:
    value = value.strip('"')
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError) as exc:
        raise SignatureError(f"{value!r} is not a YYYYMMDD date") from exc


def parse_allowed_signers(text: str) -> list[AllowedSigner]:
    """Read an allowed-signers file: the OpenSSH format, Ed25519 keys only."""
    out: list[AllowedSigner] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 3:
            raise SignatureError(f"allowed signers line {number}: expected principal, options, type and key")
        principal = fields[0]
        rest = fields[1:]
        options = ""
        if rest[0] not in (_ED25519, _SK_ED25519):
            options = rest[0]
            rest = rest[1:]
        if len(rest) < 2:
            raise SignatureError(f"allowed signers line {number}: missing key")
        try:
            blob = base64.b64decode(rest[1], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SignatureError(f"allowed signers line {number}: the key's base64 is malformed") from exc
        key = PublicKey.from_blob(blob)
        if key.key_type != rest[0]:
            raise SignatureError(f"allowed signers line {number}: the key type does not match the key")
        namespaces: tuple[str, ...] = ()
        valid_after = valid_before = None
        for option in [o for o in options.split(",") if o]:
            name, _, value = option.partition("=")
            if name == "namespaces":
                namespaces = tuple(n for n in value.strip('"').split(",") if n)
            elif name == "valid-after":
                valid_after = _yyyymmdd(value)
            elif name == "valid-before":
                valid_before = _yyyymmdd(value)
            else:
                raise SignatureError(f"allowed signers line {number}: option {name} is not supported")
        out.append(AllowedSigner(principal, key, namespaces, valid_after, valid_before))
    return out


def bundled_allowed_signers() -> list[AllowedSigner]:
    """The Licensor's keys, as shipped in the validator package."""
    text = resources.files("urml_validator.evidence_keys").joinpath("allowed_signers").read_text(encoding="utf-8")
    return parse_allowed_signers(text)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verification:
    """The outcome of verifying one signed report."""

    good: bool
    reason: str
    principal: str | None = None
    fingerprint: str | None = None
    robot_id: str | None = None
    as_of: str | None = None


def verify_report(report_bytes: bytes, signature_text: str, signers: list[AllowedSigner]) -> Verification:
    """Verify `signature_text` over the exact bytes of an evidence report.

    The report must be an evidence report, the signature must be made in the
    evidence-report namespace by a key in `signers`, and that key must be valid
    on the report's `as_of` date.
    """
    sig = _parse_sshsig(signature_text)
    fingerprint = sig.public_key.fingerprint()
    try:
        report = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Verification(
            False, "the signed file is not JSON, so it is not an evidence report", fingerprint=fingerprint
        )
    if not isinstance(report, dict) or report.get("format") != "urml.evidence-report/0.1":
        return Verification(False, "the signed file is not an evidence report", fingerprint=fingerprint)
    robot_id = (report.get("subject") or {}).get("robot_id")
    as_of_text = report.get("as_of")
    try:
        as_of = date.fromisoformat(str(as_of_text))
    except ValueError:
        return Verification(False, "the report has no valid as_of date", fingerprint=fingerprint)
    if sig.namespace != NAMESPACE:
        return Verification(
            False,
            f"the signature was made in namespace {sig.namespace!r}, not {NAMESPACE!r}",
            fingerprint=fingerprint,
        )
    if sig.hash_algorithm not in ("sha256", "sha512"):
        return Verification(False, f"hash algorithm {sig.hash_algorithm} is not accepted", fingerprint=fingerprint)
    matching = [s for s in signers if s.public_key == sig.public_key]
    if not matching:
        reason = (
            "no Licensor key is published in this package yet"
            if not signers
            else "the signing key is not in the allowed signers"
        )
        return Verification(False, reason, fingerprint=fingerprint, robot_id=robot_id, as_of=as_of_text)
    data = _signed_data(sig.namespace, sig.hash_algorithm, report_bytes)
    if not _verify_blob(sig.public_key, data, sig.signature):
        return Verification(
            False,
            "the signature does not match these bytes: the report was changed after signing, or the signature "
            "belongs to another file",
            fingerprint=fingerprint,
            robot_id=robot_id,
            as_of=as_of_text,
        )
    for signer in matching:
        if signer.namespaces and NAMESPACE not in signer.namespaces:
            continue
        if signer.valid_after is not None and as_of < signer.valid_after:
            continue
        if signer.valid_before is not None and as_of >= signer.valid_before:
            continue
        return Verification(
            True,
            "good signature",
            principal=signer.principal,
            fingerprint=fingerprint,
            robot_id=robot_id,
            as_of=as_of_text,
        )
    return Verification(
        False,
        f"the key is known but not valid for evidence reports dated {as_of_text}",
        fingerprint=fingerprint,
        robot_id=robot_id,
        as_of=as_of_text,
    )


def verify_report_file(report_path: Path, signature_path: Path, allowed_signers: Path | None = None) -> Verification:
    """Verify a report file and its signature file, against the bundled keys or `allowed_signers`."""
    signers = (
        parse_allowed_signers(allowed_signers.read_text(encoding="utf-8"))
        if allowed_signers is not None
        else bundled_allowed_signers()
    )
    return verify_report(report_path.read_bytes(), signature_path.read_text(encoding="utf-8"), signers)


__all__ = [
    "NAMESPACE",
    "AllowedSigner",
    "PublicKey",
    "SignatureError",
    "Verification",
    "bundled_allowed_signers",
    "ed25519_verify",
    "parse_allowed_signers",
    "verify_report",
    "verify_report_file",
]
