"""``python -m urml_conformance.reproduce``: the Licensor's URML-Certified run.

A runtime earns URML-Certified when the Licensor reproduces its self-reported
conformance run from the public package (RFC-0705; the run is a paid service
since RFC-0708). This module is that reproduction, written down as code so
anyone can see, and repeat, exactly what the Licensor does:

    python -m urml_conformance.reproduce registry/entries/acme-rover.yaml
    python -m urml_conformance.reproduce registry/entries/acme-rover.yaml --write

1. **Plan.** Read the submitted entry and refuse early when it cannot be
   certified: not ``tier: certified``, no attestation, a package that is a
   repository path or one of the URML project's own ``urml-*`` distributions,
   a version range instead of one release, the mock adapter, or a self-report
   whose sha256 does not match its pin.
2. **Install.** Create a fresh virtual environment and install exactly
   ``<package>==<version>`` and the matching ``urml-conformance`` into it,
   from the package index (or ``--index-url``).
3. **Run, offline.** Run the suite for the claimed profiles with the entry's
   adapter, in that environment, with networking refused except to loopback
   (a local simulator or broker still works). The guard covers the suite's
   own process; a process the adapter starts is not covered, so pass
   ``--run-prefix`` to run under an OS sandbox as well (for example
   ``--run-prefix "unshare -rn"`` on Linux).
4. **Check.** The reproduction must pass every fixture, name the entry's
   adapter, and run the same fixture set (equal ``fixtures_sha256``) as the
   self-report.
5. **Record.** Add the time each step took to the reproduction report
   (``timing``, wall-clock seconds), so the cost of a run by scope is
   measured rather than guessed (RFC-0708). Then pin the report by sha256
   and print the
   ``certified_on``, ``expires`` and ``reproduction`` fields for the entry;
   ``--write`` puts them into the entry's ``certification`` block and sets
   ``last_verified`` to the reproduction day.

A failed run still writes its report: the run happened, and under RFC-0708 a
failed run grants nothing. The exit code is 0 only when the reproduction
passes every check. Nothing is sent anywhere except the package installs.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import time
import venv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from urml_conformance._version import __version__ as _conformance_version
from urml_conformance.registry import (
    _ADAPTER_SPEC,
    _DISTRIBUTION,
    _EXACT_VERSION,
    BANNED_WORDS,
    FIRST_PARTY_PREFIX,
    MAX_CERTIFICATION_DAYS,
    Entry,
    _is_mock,
    default_root,
)
from urml_conformance.report import ConformanceReport, ReproductionStep, StepTime

__all__ = [
    "LICENSOR",
    "OFFLINE_GUARD",
    "Plan",
    "ReproductionError",
    "certification_fields",
    "check_reproduction",
    "clean_env",
    "create_environment",
    "insert_certification",
    "plan_reproduction",
    "record_timing",
    "run_offline",
    "set_last_verified",
]

#: Who a reproduction names in ``reproduction.by`` (RFC-0704).
LICENSOR = "Yahalomik Ltd. (URML Licensor)"
#: A year: inside the 366-day cap, and easy to read.
DEFAULT_VALIDITY_DAYS = 365
#: The certification fields this tool fills in. The submitter writes
#: ``conformance_spec`` and ``attestation``; the Licensor writes these.
LICENSOR_FIELDS = ("certified_on", "expires", "reproduction")
#: The spec versions a certification can be granted against, newest last.
_SPECS = ("0.2.0", "0.2.1", "0.2.2", "0.2.3")

#: Run as a script by the environment's interpreter: refuse every connection
#: and name lookup that is not loopback, then run the suite. Kept stdlib-only.
OFFLINE_GUARD = '''\
"""URML reproduction run: the network is off except loopback (RFC-0705)."""
import ipaddress
import runpy
import socket
import sys

_LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


def _local(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).split("%")[0]
    if host.lower() in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _refuse(what, host):
    raise OSError(f"network is off for the reproduction run: refused {what} {host!r}")


def _checked(method, what):
    def wrapper(self, *args):
        address = args[-1]
        if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
            if not _local(address[0]):
                _refuse(what, address[0])
        return method(self, *args)
    return wrapper


socket.socket.connect = _checked(socket.socket.connect, "a connection to")
socket.socket.connect_ex = _checked(socket.socket.connect_ex, "a connection to")
socket.socket.sendto = _checked(socket.socket.sendto, "a datagram to")
_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _local(host):
        raise socket.gaierror(f"network is off for the reproduction run: refused a lookup of {host!r}")
    return _getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _guarded_getaddrinfo
sys.argv = ["python -m urml_conformance", *sys.argv[1:]]
runpy.run_module("urml_conformance", run_name="__main__", alter_sys=True)
'''

#: Environment variables a clean run keeps. Everything else, PYTHONPATH and
#: the pip and proxy settings included, is dropped so the host cannot leak in.
_KEEP_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP", "SYSTEMROOT", "WINDIR")


class ReproductionError(Exception):
    """The entry cannot be reproduced, or the reproduction failed a check."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = list(problems)


@dataclasses.dataclass(frozen=True)
class Plan:
    """What one reproduction installs and runs, read from a submitted entry."""

    entry_path: Path
    entry_id: str
    package: str
    version: str
    adapter: str
    profiles: tuple[str, ...]
    self_report_path: str
    self_report: ConformanceReport
    conformance_spec: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def plan_reproduction(entry_path: Path, root: Path) -> Plan:
    """Read a submitted entry and say what to run, or raise with every reason it cannot be."""
    try:
        data = yaml.safe_load(entry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ReproductionError([f"{entry_path}: cannot read the entry: {exc}"]) from exc
    entry = _mapping(data)
    runtime = _mapping(entry.get("runtime"))
    claim = _mapping(entry.get("compatibility"))
    cert = _mapping(claim.get("certification"))
    problems: list[str] = []

    entry_id = str(entry.get("id") or "")
    if not entry_id:
        problems.append("the entry has no id")

    package = str(runtime.get("package") or "")
    if not re.match(_DISTRIBUTION, package):
        problems.append(
            f"runtime.package {package!r} is not a distribution name: a certified runtime is a "
            "public package anyone can install, not a repository path"
        )
    elif package.lower().replace("_", "-").startswith(FIRST_PARTY_PREFIX):
        problems.append(
            f"runtime.package {package!r} is published by the URML project; the Licensor does not "
            "certify its own runtimes (RFC-0705)"
        )
    version = str(runtime.get("version") or "")
    if not re.match(_EXACT_VERSION, version):
        problems.append(f"runtime.version {version!r} is not one exact release")
    adapter = str(runtime.get("adapter") or "")
    if not re.match(_ADAPTER_SPEC, adapter):
        problems.append("runtime.adapter must name the runtime's adapter as module:attribute")
    elif _is_mock(adapter):
        problems.append("runtime.adapter is the hermetic mock; a reproduction runs the runtime's own adapter")

    if claim.get("tier") != "certified":
        problems.append("compatibility.tier is not certified: the entry does not apply for URML-Certified")
    profiles = claim.get("profiles")
    if not isinstance(profiles, list) or not profiles or not all(isinstance(p, str) for p in profiles):
        problems.append("compatibility.profiles must list the profiles the claim covers")
        profiles = []
    spec = str(cert.get("conformance_spec") or "")
    if spec not in _SPECS:
        problems.append(f"certification.conformance_spec must be one of {', '.join(_SPECS)}")
    attestation = cert.get("attestation")
    if not isinstance(attestation, str) or not attestation.strip():
        problems.append(
            "certification.attestation is missing: the submitter states that the runtime meets the six "
            "clauses of the conformance contract"
        )

    report_ref = _mapping(claim.get("report"))
    report_path = str(report_ref.get("path") or "")
    self_report: ConformanceReport | None = None
    target = root / report_path
    if not report_path or not target.is_file():
        problems.append(f"compatibility.report.path {report_path!r} is not a file in the repository")
    elif _sha256(target) != report_ref.get("sha256"):
        problems.append("compatibility.report.sha256 does not match the self-report file")
    else:
        try:
            self_report = ConformanceReport.model_validate_json(target.read_bytes())
        except PydanticValidationError as exc:
            problems.append(f"the self-report is not a urml.conformance-report/1 report: {exc.errors()[0]['msg']}")

    if problems or self_report is None:
        raise ReproductionError(problems or ["the self-report could not be read"])
    return Plan(
        entry_path=entry_path,
        entry_id=entry_id,
        package=package,
        version=version,
        adapter=adapter,
        profiles=tuple(sorted(set(profiles))),
        self_report_path=report_path,
        self_report=self_report,
        conformance_spec=spec,
    )


def clean_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment a reproduction runs in: the host's basics, nothing that redirects Python or pip."""
    env = {key: os.environ[key] for key in _KEEP_ENV if key in os.environ}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def _environment_python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def create_environment(
    plan: Plan,
    env_dir: Path,
    *,
    index_url: str | None = None,
    conformance_source: str | None = None,
) -> Path:
    """Create a fresh virtual environment with exactly the runtime and the suite. Returns its python."""
    venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
    python = _environment_python(env_dir)
    command = [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-input",
        "--disable-pip-version-check",
        "--no-cache-dir",
    ]
    if index_url:
        command += ["--index-url", index_url]
    command += [f"{plan.package}=={plan.version}", conformance_source or f"urml-conformance=={_conformance_version}"]
    completed = subprocess.run(command, env=clean_env(), check=False)
    if completed.returncode != 0:
        raise ReproductionError([f"installing {plan.package}=={plan.version} failed (pip exit {completed.returncode})"])
    return python


def run_offline(
    plan: Plan,
    python: Path,
    report_path: Path,
    workdir: Path,
    *,
    run_prefix: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> int:
    """Run the suite for the plan's profiles with the network off except loopback. Returns the exit code."""
    guard = workdir / "urml_offline_run.py"
    guard.write_text(OFFLINE_GUARD, encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [*run_prefix, str(python), str(guard), "--adapter", plan.adapter, "--report", str(report_path)]
    for profile in plan.profiles:
        command += ["--profile", profile]
    # Run from the scratch directory, so nothing in the checkout can be imported.
    completed = subprocess.run(command, cwd=workdir, env=dict(env) if env is not None else clean_env(), check=False)
    return completed.returncode


def check_reproduction(plan: Plan, reproduction: ConformanceReport) -> list[str]:
    """Everything the reproduction must show before the Licensor can grant the mark (RFC-0705)."""
    problems: list[str] = []
    if not reproduction.results:
        problems.append("the reproduction ran no fixtures")
    elif not reproduction.all_passed:
        failed = ", ".join(case.name for case in reproduction.failed_cases()[:5])
        problems.append(f"{reproduction.failed} of {len(reproduction.results)} fixtures failed: {failed}")
    if reproduction.adapter != plan.adapter:
        problems.append(f"the reproduction ran {reproduction.adapter!r}, not the entry's adapter {plan.adapter!r}")
    if reproduction.fixtures_sha256 != plan.self_report.fixtures_sha256:
        problems.append(
            "the reproduction ran a different fixture set from the self-report (fixtures_sha256 differs): "
            "both must come from the same urml-conformance release"
        )
    if reproduction.urml_conformance_version != plan.self_report.urml_conformance_version:
        problems.append(
            f"the reproduction used urml-conformance {reproduction.urml_conformance_version}, the self-report "
            f"{plan.self_report.urml_conformance_version}"
        )
    if set(reproduction.profiles or ()) != set(plan.profiles):
        problems.append("the reproduction did not run exactly the claimed profiles")
    return problems


class StepClock:
    """Wall-clock seconds for each step of a run, in the order the steps ran."""

    def __init__(self) -> None:
        self.steps: list[StepTime] = []
        self._step: ReproductionStep | None = None
        self._started = 0.0

    def start(self, step: ReproductionStep) -> None:
        self.stop()
        self._step = step
        self._started = time.perf_counter()

    def stop(self) -> None:
        if self._step is not None:
            seconds = round(time.perf_counter() - self._started, 2)
            self.steps.append(StepTime(step=self._step, seconds=seconds))
            self._step = None


def record_timing(report_path: Path, steps: Sequence[StepTime]) -> ConformanceReport:
    """Write the step times into the reproduction report, replacing any already there. Returns the report."""
    report = ConformanceReport.model_validate_json(report_path.read_bytes())
    report = report.model_copy(update={"timing": list(steps)})
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def _render_timing(steps: Sequence[StepTime]) -> str:
    parts = [f"{step.step} {step.seconds:.2f}s" for step in steps]
    return f"timing: {', '.join(parts)}; total {sum(step.seconds for step in steps):.2f}s"


def certification_fields(
    *,
    report_path: str,
    report_sha256: str,
    reproduced_on: dt.date,
    environment: str,
    validity_days: int = DEFAULT_VALIDITY_DAYS,
) -> dict[str, Any]:
    """The ``certified_on``, ``expires`` and ``reproduction`` fields for the entry's certification block."""
    if not 1 <= validity_days <= MAX_CERTIFICATION_DAYS:
        raise ValueError(f"validity must be 1 to {MAX_CERTIFICATION_DAYS} days")
    if BANNED_WORDS.search(environment):
        raise ValueError("the environment text is free text and must not use the words the registry bans")
    day = reproduced_on.isoformat()
    return {
        "certified_on": day,
        "expires": (reproduced_on + dt.timedelta(days=validity_days)).isoformat(),
        "reproduction": {
            "report": {"path": report_path, "sha256": report_sha256},
            "by": LICENSOR,
            "date": day,
            "environment": environment,
        },
    }


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def insert_certification(text: str, fields: Mapping[str, Any]) -> str:
    """Put the Licensor's fields into the entry's ``certification:`` block, replacing older ones.

    Edits the text rather than re-dumping the YAML, so the submitter's comments
    and folded paragraphs stay as they wrote them.
    """
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if re.match(r"^\s*certification:\s*(#.*)?$", line)), None)
    if start is None:
        raise ReproductionError(["the entry has no certification: block to fill in"])
    parent = _indent(lines[start])
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > parent):
        end += 1
    body = [i for i in range(start + 1, end) if lines[i].strip()]
    if not body:
        raise ReproductionError(["the certification: block is empty: it needs conformance_spec and attestation"])
    child = _indent(lines[body[0]])
    block = lines[start + 1 : end]
    gap: list[str] = []
    while block and not block[-1].strip():
        gap.insert(0, block.pop())
    kept: list[str] = []
    skipping = False
    for line in block:
        if line.strip() and _indent(line) == child:
            skipping = line.strip().split(":", 1)[0] in LICENSOR_FIELDS
        if not skipping:
            kept.append(line)
    if kept and not kept[-1].endswith("\n"):
        kept[-1] += "\n"
    pad = " " * child
    return "".join(lines[: start + 1] + kept + [pad + line + "\n" for line in _field_lines(fields)] + gap + lines[end:])


def set_last_verified(text: str, day: str) -> str:
    """Set the entry's top-level ``last_verified`` to the reproduction day: the Licensor verified it then."""
    pattern = re.compile(r"^last_verified:.*$", re.MULTILINE)
    if not pattern.search(text):
        raise ReproductionError(["the entry has no top-level last_verified field"])
    return pattern.sub(f"last_verified: {json.dumps(day)}", text, count=1)


def _field_lines(fields: Mapping[str, Any], depth: int = 0) -> list[str]:
    """The fields as YAML block lines. Strings are JSON-quoted, which YAML reads as plain strings."""
    out: list[str] = []
    for key, value in fields.items():
        if isinstance(value, Mapping):
            out.append(f"{'  ' * depth}{key}:")
            out.extend(_field_lines(value, depth + 1))
        else:
            out.append(f"{'  ' * depth}{key}: {json.dumps(str(value), ensure_ascii=False)}")
    return out


def _environment_text(
    plan: Plan, index_url: str | None, conformance_source: str | None, run_prefix: Sequence[str]
) -> str:
    source = "a private index" if index_url else "PyPI"
    suite = "a local build" if conformance_source else source
    text = (
        f"{plan.package} {plan.version} from {source}, urml-conformance {_conformance_version} from {suite}, "
        f"Python {platform.python_version()} on {platform.system()}, network off after install except loopback"
    )
    if run_prefix:
        text += f", run under {shlex.join(run_prefix)}"
    return text + "."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m urml_conformance.reproduce",
        description="Reproduce a registry entry's conformance run from its public package (URML-Certified, RFC-0705).",
    )
    parser.add_argument("entry", type=Path, help="The submitted registry entry (registry/entries/<id>.yaml).")
    parser.add_argument("--root", type=Path, default=None, help="The repository root (default: this checkout).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the reproduction report (default: registry/evidence/<id>/reproduction-report.json).",
    )
    parser.add_argument("--index-url", default=None, help="Install from this package index instead of PyPI.")
    parser.add_argument(
        "--conformance-source",
        default=None,
        help="Install urml-conformance from this path or requirement instead of the matching release.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=None,
        help="Use this interpreter, from an environment you prepared, instead of creating one.",
    )
    parser.add_argument(
        "--run-prefix",
        default="",
        help='Run the suite under this command, such as an OS sandbox: --run-prefix "unshare -rn".',
    )
    parser.add_argument(
        "--date", type=dt.date.fromisoformat, default=None, help="The reproduction date (default: today)."
    )
    parser.add_argument(
        "--validity-days",
        type=int,
        default=DEFAULT_VALIDITY_DAYS,
        help=f"Days until the certification expires (at most {MAX_CERTIFICATION_DAYS}).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the fields into the entry's certification block and set last_verified.",
    )
    args = parser.parse_args(argv)

    root = (args.root or default_root()).resolve()
    clock = StepClock()
    clock.start("plan")
    try:
        plan = plan_reproduction(args.entry, root)
    except ReproductionError as exc:
        for problem in exc.problems:
            print(f"  {problem}", file=sys.stderr)
        print("not reproduced: the entry cannot be certified as submitted", file=sys.stderr)
        return 2
    output = (args.output or root / "registry" / "evidence" / plan.entry_id / "reproduction-report.json").resolve()
    run_prefix = shlex.split(args.run_prefix)
    print(
        f"reproducing {plan.entry_id}: {plan.package}=={plan.version}, adapter {plan.adapter}, "
        f"profiles {', '.join(plan.profiles)}"
    )

    with tempfile.TemporaryDirectory(prefix="urml-reproduce-") as scratch:
        workdir = Path(scratch)
        python = args.python
        if python is None:
            clock.start("install")
            try:
                python = create_environment(
                    plan, workdir / "env", index_url=args.index_url, conformance_source=args.conformance_source
                )
            except ReproductionError as exc:
                print(f"  {exc}", file=sys.stderr)
                return 1
        clock.start("run")
        code = run_offline(plan, python, output, workdir, run_prefix=run_prefix)

    if not output.is_file():
        print(f"the suite wrote no report (exit {code}); nothing to record", file=sys.stderr)
        return 1
    clock.start("check")
    reproduction = ConformanceReport.model_validate_json(output.read_bytes())
    problems = check_reproduction(plan, reproduction)
    clock.stop()
    record_timing(output, clock.steps)
    print(f"wrote {output}")
    print(_render_timing(clock.steps))
    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "not reproduced: the mark cannot be granted. The report is kept as the record of the run.", file=sys.stderr
        )
        return 1

    try:
        rel = output.relative_to(root).as_posix()
    except ValueError:
        rel = output.as_posix()
    fields = certification_fields(
        report_path=rel,
        report_sha256=_sha256(output),
        reproduced_on=args.date or dt.date.today(),
        environment=_environment_text(plan, args.index_url, args.conformance_source, run_prefix),
        validity_days=args.validity_days,
    )
    if args.write:
        text = insert_certification(plan.entry_path.read_text(encoding="utf-8"), fields)
        text = set_last_verified(text, fields["certified_on"])
        try:
            Entry.model_validate(yaml.safe_load(text))
        except PydanticValidationError as exc:
            print(f"  the filled entry does not parse: {exc.errors()[0]['msg']}", file=sys.stderr)
            return 1
        plan.entry_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote the certification fields into {plan.entry_path}")
    else:
        print("add these fields to the entry's certification block (or re-run with --write):")
        for line in _field_lines(fields):
            print("    " + line)
    print("reproduced: run `python -m urml_conformance.registry check` before merging the grant")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
