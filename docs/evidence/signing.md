<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  A small, opinionated, human-readable language for describing robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# Signed and redacted evidence reports

An evidence report ([RFC-0707](../rfcs/0707-evidence-report.md)) is trusted by reproduction: anyone holding the same files can run `urml evidence build` with the same `--as-of` date and compare bytes. Two additions make a report easier to pass around: a redacted copy for readers outside the site, and a signature from the Licensor on reports it has reproduced and reviewed.

A signature is not a certification. It says the signer rebuilt the report from inputs with the digests it lists and reviewed it. It does not say the robot is safe or compliant.

## Redacting a report

```bash
urml evidence build --manifest robot.yaml --envelope site.yaml --as-of 2026-11-24 \
  --redact --out report.redacted.json
```

The redacted copy keeps every item, status, rule, cite, declaration and count. It removes site geometry (geofence and zone vertices, altitude bands) and the validator's messages on programs, which can quote coordinates; issue codes stay. Each removed value becomes `[redacted]`, never a hash, because a hash of a guessable coordinate can be reversed. The `redaction` block lists what was removed and the sha256 of the full report, so a recipient later shown the full report can check it is the same one.

## Verifying a signed report

```bash
urml evidence verify report.json            # reads report.json.sig
urml evidence verify report.json other.sig --allowed-signers keys.txt
```

Verification runs offline in the validator, with no OpenSSH install. It accepts a signature only when:

- it is an OpenSSH signature in the namespace `evidence-report@urml.dev`;
- it was made by an Ed25519 key in the allowed-signers file (by default the Licensor's keys shipped in the package); a hardware (FIDO) key must have asserted user presence;
- the key is valid on the report's `as_of` date;
- the signed bytes are exactly the report file's bytes, and the file is an evidence report.

Exit codes: `0` good signature, `1` bad or untrusted, `2` a file cannot be read.

## For the Licensor: signing

The key lives on a hardware token. With a FIDO2 token (for example a YubiKey 5):

```bash
# once: create the key on the token
ssh-keygen -t ed25519-sk -O resident -O application=ssh:urml-evidence -C "URML Licensor evidence key" -f ~/.ssh/urml_evidence

# per report, after rebuilding it and reviewing it
ssh-keygen -Y sign -f ~/.ssh/urml_evidence -n evidence-report@urml.dev report.json
```

Sign the JSON only, never the Markdown or HTML. Sign a redacted copy separately if one is shared; each file carries its own signature.

Publish the public key by adding one line to `reference/validator/src/urml_validator/evidence_keys/allowed_signers`, in a reviewed commit, and on urml.dev:

```text
licensor@urml.dev namespaces="evidence-report@urml.dev",valid-after="20261201" sk-ssh-ed25519@openssh.com AAAA...
```

To retire a key, add `valid-before="YYYYMMDD"` to its line and keep the line, so reports it signed still verify; then add the new key. The file's git history is the key record.

No Licensor key is published yet. Until one is, `urml evidence verify` reports that no key is available.

## What has not been tested

Plain Ed25519 signatures are tested against files made by `ssh-keygen`. The hardware-key path (`sk-ssh-ed25519@openssh.com`) is tested against signatures built from the OpenSSH format description, not yet against a physical token. Check it with the first real Licensor signature before publishing the key.
