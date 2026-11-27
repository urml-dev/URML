"""Vendor manifest demo runner: one entry point, fourteen vendor-shaped manifests.

The conformance suite carries manifests shaped like real industrial
products: eight robot arms and six parts (grippers, lidars, a 3D camera).
The URML project wrote each one from the vendor's public documentation.
No vendor named here has reviewed, supplied or endorsed its manifest.

Each entry below has:

  * A brand-named manifest fixture in
    ``reference/validator/tests/fixtures/manifests/<vendor>_cell.yaml``
    (or its parts equivalent).
  * A positive conformance fixture in
    ``conformance/fixtures/industrial/<NN>_<vendor>_cell_positive.yaml``
    (or its parts equivalent).

This script lets a reader pick one entry, run its conformance fixture
**hermetically** against ``MockROSAdapter``, and see the audit trace.
No ROS, no hardware, no network.

Usage::

    PYTHONPATH=reference/validator/src;reference/ros2-runtime/src;conformance/src \\
        python examples/vendor-manifests/demo.py --vendor yaskawa
    python examples/vendor-manifests/demo.py --vendor ouster
    python examples/vendor-manifests/demo.py --list
"""

from __future__ import annotations

import argparse
import sys

# slug -> (display name, conformance fixture name, kind)
# kind in {"arm", "part"}
VENDORS: dict[str, tuple[str, str, str]] = {
    "yaskawa": ("Yaskawa / MotoROS2", "industrial/yaskawa_cell_positive", "arm"),
    "ur": ("Universal Robots", "industrial/ur_cell_positive", "arm"),
    "kuka": ("KUKA (via kroshu/kuka_drivers)", "industrial/kuka_cell_positive", "arm"),
    "staubli": ("Staubli (via ros-industrial)", "industrial/staubli_cell_positive", "arm"),
    "mitsubishi": ("Mitsubishi MELFA", "industrial/mitsubishi_cell_positive", "arm"),
    "fanuc": ("FANUC", "industrial/fanuc_cell_positive", "arm"),
    "kawasaki": ("Kawasaki", "industrial/kawasaki_cell_positive", "arm"),
    "denso": ("Denso", "industrial/denso_cell_positive", "arm"),
    "schunk": ("SCHUNK", "industrial/schunk_gripper_positive", "part"),
    "ouster": ("Ouster", "industrial/ouster_3d_lidar_cell_positive", "part"),
    "sick": ("SICK", "industrial/sick_safety_lidar_positive", "part"),
    "festo": ("Festo", "industrial/festo_dhep_cell_positive", "part"),
    "zivid": ("Zivid", "industrial/zivid_two_cell_positive", "part"),
    "hokuyo": ("Hokuyo", "industrial/hokuyo_lidar_cell_positive", "part"),
}


def _list() -> None:
    """Print the vendor-shaped manifests this runner can exercise."""
    print(f"Vendor-shaped manifests ({len(VENDORS)}), written by the URML project")
    print("from public documentation. Not reviewed or endorsed by the vendors.")
    print()
    print(f"  {'Slug':12} {'Kind':6} {'Conformance fixture':42} Vendor product")
    print(f"  {'-' * 86}")
    for slug, (display, fixture, kind) in VENDORS.items():
        print(f"  {slug:12} {kind:6} {fixture:42} {display}")
    print()
    print("Run `python examples/vendor-manifests/demo.py --vendor <slug>` to exercise")
    print("the conformance fixture for one entry.")


def _run(slug: str) -> int:
    """Run the conformance fixture for the named vendor-shaped manifest."""
    if slug not in VENDORS:
        print(f"unknown vendor: {slug}")
        print("use --list to see the available entries.")
        return 2

    display, fixture, kind = VENDORS[slug]

    print("----------------------------------------------------------------")
    print(f"Vendor-shaped manifest: {display}")
    print(f"Fixture:                {fixture}")
    print(f"Kind:                   {kind}")
    print("----------------------------------------------------------------")
    print()

    # Run the named conformance fixture against MockROSAdapter, hermetically.
    try:
        from urml_conformance import ConformanceRunner
        from urml_conformance.fixtures import discover_fixtures
    except ImportError as exc:
        print(f"could not import urml_conformance: {exc}", file=sys.stderr)
        print()
        print("Did you set PYTHONPATH? Try:")
        print('  $env:PYTHONPATH = "reference/validator/src;reference/ros2-runtime/src;conformance/src"')
        return 2

    cases = [c for c in discover_fixtures() if c.name == fixture]
    if not cases:
        print(f"fixture not found by name: {fixture!r}", file=sys.stderr)
        return 2
    runner = ConformanceRunner(cases=cases)
    report = runner.run()

    print(report.render())
    print()
    if report.all_passed:
        print(f"[PASS] {display} - fixture passed hermetically against MockROSAdapter.")
        print("       The substrate-neutral Protocol survives this manifest.")
        return 0
    print(f"[FAIL] {display} - fixture failed. See above.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vendor manifest demo runner: runs the conformance fixture for one "
        "of the vendor-shaped manifests in the suite, hermetically, on the mock adapter."
    )
    parser.add_argument("--vendor", help="Vendor slug (use --list to see them all).")
    parser.add_argument("--list", action="store_true", help="List the vendor-shaped manifests.")
    args = parser.parse_args()

    if args.list:
        _list()
        return 0
    if not args.vendor:
        parser.print_help()
        return 2
    return _run(args.vendor)


if __name__ == "__main__":
    sys.exit(main())
