from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

SCAN_PATHS = [
    REPO_ROOT / "skills",
    REPO_ROOT / "README.md",
    REPO_ROOT / "CITATION.cff",
    REPO_ROOT / ".zenodo.json",
]

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("windows_drive_path", re.compile(r"\b[A-Za-z]:\\")),
    ("windows_slash_path", re.compile(r"\b[A-Za-z]:/(?:APS|Users|MultilayerLab|ResearchProjects|Software)\b")),
    ("unix_user_path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")),
    ("eln_uri", re.compile(r"\beln://", re.IGNORECASE)),
    ("private_lan_ip", re.compile(r"\b10\.109\.")),
    ("private_plc_ip", re.compile(r"\b192\.168\.127\.(?!208\b)\d+")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("vendor_csmic", re.compile(r"\bCSMIC", re.IGNORECASE)),
    ("vendor_svac", re.compile(r"\bSVAC", re.IGNORECASE)),
    ("vendor_t500", re.compile(r"\bT500\b", re.IGNORECASE)),
    ("vendor_cluster_demo", re.compile(r"\bCluster_Demo\b", re.IGNORECASE)),
    ("vendor_penkov_517", re.compile(r"Penkov_517", re.IGNORECASE)),
    ("vendor_wsp", re.compile(r"\bWSP\b")),
    ("vendor_dc4001", re.compile(r"\bDC4001", re.IGNORECASE)),
    ("vendor_g3f", re.compile(r"\b(?:DCPulse)?G3F", re.IGNORECASE)),
    ("vendor_lesker", re.compile(r"\bLesker", re.IGNORECASE)),
    ("vendor_kcm91", re.compile(r"\bKCM91\b", re.IGNORECASE)),
    ("vendor_jyk", re.compile(r"\bJYK", re.IGNORECASE)),
    ("vendor_n6705c", re.compile(r"\bN6705C\b", re.IGNORECASE)),
    ("vendor_g500", re.compile(r"\b(?:Vac)?G500\b", re.IGNORECASE)),
    ("vendor_stepperdrive", re.compile(r"\bStepperDrive\b")),
    ("commercial_plc_policy", re.compile(r"PlcAccessPolicy|PlcSerialCollector")),
    ("commercial_licensing", re.compile(r"LicenseBootstrap|APS\.Licensing|APS\.Accounts\.(?:csproj|dll)|APS\.Production\.(?:csproj|dll)|APS\.SystemControl\.Commercial|CommercialTests|EmulatorAdsTests|BehaviorValidation")),
    ("vendor_buzheng", re.compile(r"\bBuzheng\b", re.IGNORECASE)),
    ("serial_com_port", re.compile(r"\bCOM\d+\b")),
]


def iter_target_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for target in SCAN_PATHS:
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            for p in sorted(target.rglob("*")):
                if p.is_file() and p.suffix.lower() in {".md", ".txt", ".json", ".cff", ".yaml", ".yml", ".xml", ".rcpx", ".py", ".toml", ".ps1", ".ts", ".mjs"}:
                    files.append(p)
    return files


def scan_repository() -> list[str]:
    violations: list[str] = []
    for path in iter_target_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in FORBIDDEN_PATTERNS:
                match = pattern.search(line)
                if match:
                    violations.append(f"{rel}:{line_no}: [{name}] matched {match.group(0)!r}")
    return violations


def main() -> int:
    violations = scan_repository()
    if violations:
        for v in violations:
            print(v, file=sys.stderr)
        return 1
    print(f"OK: scanned {len(iter_target_files())} files with 0 portability/denylist violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
