"""Redacted and signed evidence reports (RFC-0707, step 4).

The signature fixtures under `tests/fixtures/evidence/signing/` were made with
`ssh-keygen -Y sign` and throwaway keys whose private halves were deleted; the
allowed-signers file there trusts those test keys only. A FIDO
(`sk-ssh-ed25519@openssh.com`) signature is built in the test from the RFC 8032
signing equations, since no hardware token is attached to CI.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.test_evidence_report import FIXTURES, _build, _cli_args, _golden_form
from urml_validator import evidence_sign as es
from urml_validator.cli import main
from urml_validator.evidence_render import render_html, render_markdown
from urml_validator.evidence_report import REDACTED, EvidenceReport, redact_report, render_json

SIGNING = FIXTURES / "signing"
SIGNERS = es.parse_allowed_signers((SIGNING / "allowed_signers").read_text(encoding="utf-8"))


def _verify(report: str, sig: str | None = None, signers: list[es.AllowedSigner] = SIGNERS) -> es.Verification:
    sig_path = SIGNING / (sig or f"{report}.sig")
    return es.verify_report((SIGNING / report).read_bytes(), sig_path.read_text(encoding="utf-8"), signers)


# ----- Ed25519 -----


def test_ed25519_verifies_the_rfc_8032_test_vector() -> None:
    public = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    assert es.ed25519_verify(public, b"", signature)
    assert not es.ed25519_verify(public, b"x", signature)
    assert not es.ed25519_verify(public, b"", signature[:-1] + bytes([signature[-1] ^ 1]))


# ----- signatures made by ssh-keygen -----


def test_a_good_signature_verifies() -> None:
    result = _verify("report.json")
    assert result.good
    assert result.principal == "current@test.invalid"
    assert result.robot_id == "warehouse_amr_1"
    assert result.as_of == "2026-11-24"


def test_one_changed_byte_breaks_the_signature() -> None:
    data = (SIGNING / "report.json").read_bytes()
    changed = data.replace(b'"warehouse"', b'"Warehouse"', 1)
    assert changed != data
    result = es.verify_report(changed, (SIGNING / "report.json.sig").read_text(encoding="utf-8"), SIGNERS)
    assert not result.good
    assert "does not match these bytes" in result.reason


def test_a_signature_in_another_namespace_is_refused() -> None:
    result = _verify("report-file-namespace.json")
    assert not result.good
    assert "namespace 'file'" in result.reason


def test_a_retired_key_does_not_verify_a_later_report() -> None:
    result = _verify("report-retired.json")
    assert not result.good
    assert "not valid for evidence reports dated 2026-11-24" in result.reason


def test_a_key_outside_the_allowed_signers_is_refused() -> None:
    only_retired = [s for s in SIGNERS if s.principal == "retired@test.invalid"]
    result = _verify("report.json", signers=only_retired)
    assert not result.good
    assert "not in the allowed signers" in result.reason


def test_a_signed_file_that_is_not_a_report_is_refused() -> None:
    result = _verify("not-a-report.txt")
    assert not result.good
    assert "not JSON" in result.reason


def test_no_licensor_key_is_published_yet() -> None:
    assert es.bundled_allowed_signers() == []
    result = _verify("report.json", signers=es.bundled_allowed_signers())
    assert not result.good
    assert result.reason == "no Licensor key is published in this package yet"


@pytest.mark.parametrize(
    "text",
    ["", "hello", "-----BEGIN SSH SIGNATURE-----\n!!!\n-----END SSH SIGNATURE-----\n"],
)
def test_a_malformed_signature_is_an_error(text: str) -> None:
    with pytest.raises(es.SignatureError):
        es.verify_report((SIGNING / "report.json").read_bytes(), text, SIGNERS)


def test_allowed_signers_refuse_unknown_options_and_other_key_types() -> None:
    line = (SIGNING / "allowed_signers").read_text(encoding="utf-8").splitlines()[2]
    with pytest.raises(es.SignatureError):
        es.parse_allowed_signers(line.replace("namespaces=", "cert-authority,namespaces="))
    rsa = "someone ssh-rsa " + base64.b64encode(b"\x00\x00\x00\x07ssh-rsa").decode()
    with pytest.raises(es.SignatureError):
        es.parse_allowed_signers(rsa)


# ----- a FIDO (sk-ssh-ed25519) signature, built in the test -----


def _compress(point: tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = point
    zinv = pow(z, es._P - 2, es._P)
    x, y = x * zinv % es._P, y * zinv % es._P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _sign(seed: bytes, message: bytes) -> tuple[bytes, bytes]:
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    public = _compress(es._mul(a, es._BASE))
    r = int.from_bytes(hashlib.sha512(h[32:] + message).digest(), "little") % es._L
    big_r = _compress(es._mul(r, es._BASE))
    k = int.from_bytes(hashlib.sha512(big_r + public + message).digest(), "little") % es._L
    s = (r + k * a) % es._L
    return public, big_r + s.to_bytes(32, "little")


def _sk_signature(report: bytes, *, flags: int) -> tuple[str, list[es.AllowedSigner]]:
    seed = hashlib.sha256(b"urml evidence test sk key").digest()
    application = b"ssh:"
    public, _ = _sign(seed, b"")
    key = es.PublicKey("sk-ssh-ed25519@openssh.com", public, application)
    data = es._signed_data(es.NAMESPACE, "sha512", report)
    counter = (7).to_bytes(4, "big")
    to_sign = hashlib.sha256(application).digest() + bytes([flags]) + counter + hashlib.sha256(data).digest()
    _, raw = _sign(seed, to_sign)
    sig_blob = es._ssh_string(key.key_type.encode()) + es._ssh_string(raw) + bytes([flags]) + counter
    blob = (
        b"SSHSIG"
        + (1).to_bytes(4, "big")
        + es._ssh_string(key.blob)
        + es._ssh_string(es.NAMESPACE.encode())
        + es._ssh_string(b"")
        + es._ssh_string(b"sha512")
        + es._ssh_string(sig_blob)
    )
    armored = "-----BEGIN SSH SIGNATURE-----\n" + base64.b64encode(blob).decode() + "\n-----END SSH SIGNATURE-----\n"
    signers = es.parse_allowed_signers(
        f'token@test.invalid namespaces="{es.NAMESPACE}" {key.key_type} {base64.b64encode(key.blob).decode()}'
    )
    return armored, signers


def test_a_hardware_key_signature_with_user_presence_verifies() -> None:
    report = (SIGNING / "report.json").read_bytes()
    armored, signers = _sk_signature(report, flags=0x01)
    assert es.verify_report(report, armored, signers).good


def test_a_hardware_key_signature_without_user_presence_is_refused() -> None:
    report = (SIGNING / "report.json").read_bytes()
    armored, signers = _sk_signature(report, flags=0x00)
    assert not es.verify_report(report, armored, signers).good


# ----- the verify command -----


def test_cli_verify_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    allowed = str(SIGNING / "allowed_signers")
    assert main(["evidence", "verify", str(SIGNING / "report.json"), "--allowed-signers", allowed]) == 0
    assert "not a certification" in capsys.readouterr().out
    assert main(["evidence", "verify", str(SIGNING / "report-retired.json"), "--allowed-signers", allowed]) == 1
    assert main(["evidence", "verify", str(SIGNING / "report.json")]) == 1
    assert main(["evidence", "verify", str(tmp_path / "none.json")]) == 2
    bad = tmp_path / "r.json"
    bad.write_bytes((SIGNING / "report.json").read_bytes())
    (tmp_path / "r.json.sig").write_text("garbage", encoding="utf-8")
    assert main(["evidence", "verify", str(bad), "--allowed-signers", allowed]) == 2


# ----- redaction -----


def _redacted(name: str) -> tuple[EvidenceReport, EvidenceReport]:
    full = _build(name)
    return full, redact_report(full)


@pytest.mark.parametrize("name", ["amr-warehouse", "drone-vendor", "drone-parcel"])
def test_redaction_keeps_every_status_and_count(name: str) -> None:
    full, red = _redacted(name)
    assert red.counts == full.counts
    assert red.by_standard == full.by_standard
    for a, b in zip(full.sections, red.sections, strict=True):
        assert [(i.id, i.status, i.result) for i in a.items] == [(i.id, i.status, i.result) for i in b.items]


@pytest.mark.parametrize("name", ["amr-warehouse", "drone-vendor", "drone-parcel"])
def test_redaction_removes_site_geometry_and_program_messages(name: str) -> None:
    _full, red = _redacted(name)
    for section in red.sections:
        for item in section.items:
            for key in ("vertices", "min_altitude", "max_altitude"):
                assert item.detail.get(key) in (None, REDACTED), (item.id, key)
            for issue in item.detail.get("issues", []) if section.id == "programs" else []:
                assert issue["message"] == REDACTED
    assert red.redaction is not None and red.redaction.removed
    text = render_json(red)
    assert "alt=80.0" not in text and "(50.0, 40.0" not in text


def test_redaction_records_the_full_reports_hash_and_refuses_twice() -> None:
    full, red = _redacted("drone-vendor")
    assert red.redaction is not None
    assert red.redaction.full_report_sha256 == hashlib.sha256(render_json(full).encode()).hexdigest()
    assert full.redaction is None
    with pytest.raises(ValueError):
        redact_report(red)


def test_a_redacted_report_follows_the_schema_and_is_deterministic() -> None:
    _, red = _redacted("drone-vendor")
    text = render_json(red)
    assert render_json(EvidenceReport.model_validate_json(text)) == text
    assert render_json(redact_report(_build("drone-vendor"))) == text


def test_the_redacted_golden_file_and_the_cli_agree(tmp_path: Path) -> None:
    golden = FIXTURES / "drone-vendor" / "expected.redacted.json"
    _, red = _redacted("drone-vendor")
    text = _golden_form(render_json(red))
    if os.environ.get("URML_REGEN_EVIDENCE") == "1":
        golden.write_text(text, encoding="utf-8")
    assert golden.read_text(encoding="utf-8") == text
    out = tmp_path / "red.json"
    assert main([*_cli_args("drone-vendor"), "--redact", "--out", str(out)]) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["redaction"]["removed"] == json.loads(text)["redaction"]["removed"]


def test_the_human_forms_say_a_copy_is_redacted() -> None:
    _, red = _redacted("drone-vendor")
    assert "Redacted copy:" in render_markdown(red)
    assert "Redacted copy:" in render_html(red)
