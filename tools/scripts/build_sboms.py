#!/usr/bin/env python3
"""Write one CycloneDX software bill of materials per URML package.

A robot maker who builds a URML package into a product lists it, and what
it pulls in, in the product's SBOM (EU Cyber Resilience Act, Annex I, Part
II, point (1)). This script gives them one per package, from the same
build the release publishes:

    python tools/scripts/build_sboms.py --out sbom
    python tools/scripts/build_sboms.py --out sbom --only reference/validator

For each package in the release's build list it builds the wheel, installs
it with its dependencies into a fresh virtual environment (the other URML
wheels from the same build, the rest from the index), removes pip, and
records that environment with ``cyclonedx-py environment``. The package
list is read from ``.github/workflows/release.yml``, so the two cannot
drift. Needs ``build`` and ``cyclonedx-bom`` installed; network for the
third-party dependencies. Sends nothing anywhere else.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"


def release_packages(release: Path = RELEASE) -> list[str]:
    """The package directories the release builds, in its order."""
    text = release.read_text(encoding="utf-8")
    match = re.search(r"for p in (.*?); do", text, re.DOTALL)
    if match is None:
        raise SystemExit(f"no `for p in ...; do` build list in {release}")
    return [part for part in match.group(1).replace("\\", " ").split() if part]


def _python(env: Path) -> Path:
    return env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _run(*args: str | Path) -> None:
    subprocess.run([str(a) for a in args], check=True)


def build_wheels(packages: list[str], dist: Path) -> None:
    for package in packages:
        _run(
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            dist,
            REPO_ROOT / package,
        )


def _wheel_for(package: str, dist: Path) -> Path:
    name = re.search(
        r'^name\s*=\s*"([^"]+)"',
        (REPO_ROOT / package / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if name is None:
        raise SystemExit(f"{package}/pyproject.toml has no project name")
    stem = re.sub(r"[-.]+", "_", name.group(1)).lower()
    wheels = sorted(dist.glob(f"{stem}-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"expected one wheel for {name.group(1)} in {dist}, found {len(wheels)}"
        )
    return wheels[0]


def sbom_for(package: str, dist: Path, out: Path, work: Path) -> Path:
    """Install one package's wheel into a fresh environment and record it."""
    wheel = _wheel_for(package, dist)
    env = work / wheel.name.split("-")[0]
    venv.EnvBuilder(with_pip=True, clear=True).create(env)
    python = _python(env)
    _run(
        python,
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        "--find-links",
        dist,
        wheel,
    )
    _run(python, "-m", "pip", "uninstall", "--quiet", "--yes", "pip")
    target = out / f"{wheel.name.split('-')[0]}.cdx.json"
    tool = shutil.which("cyclonedx-py") or "cyclonedx-py"
    _run(
        tool,
        "environment",
        "--of",
        "JSON",
        "--output-reproducible",
        "--pyproject",
        REPO_ROOT / package / "pyproject.toml",
        "--mc-type",
        "library",
        "-o",
        target,
        python,
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory for the <package>.cdx.json files.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="DIR",
        help="Only this package directory (repeatable), e.g. reference/validator.",
    )
    args = parser.parse_args(argv)
    packages = release_packages()
    if args.only:
        unknown = sorted(set(args.only) - set(packages))
        if unknown:
            raise SystemExit(f"not in the release build list: {', '.join(unknown)}")
        wanted = set(args.only)
        # Dependencies between URML packages come from the same build, so build them all.
        selected = [p for p in packages if p in wanted]
    else:
        selected = packages
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="urml-sbom-") as scratch:
        work = Path(scratch)
        dist = work / "dist"
        build_wheels(packages, dist)
        for package in selected:
            print(f"wrote {sbom_for(package, dist, args.out, work)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
