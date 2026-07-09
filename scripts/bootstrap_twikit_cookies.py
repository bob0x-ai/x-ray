#!/usr/bin/env python3
"""Build Twikit runtime cookies and expiry metadata from env or browser export."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_ENV_FILE = Path.home() / ".hermes" / ".env"
DEFAULT_BROWSER_EXPORT_FILE = Path.home() / ".hermes" / "x_browser_cookies.json"
DEFAULT_OUTPUT_FILE = Path.home() / ".hermes" / "x_cookies.json"
DEFAULT_META_FILE = Path.home() / ".hermes" / "x_cookies.meta.json"
DEFAULT_WARNING_DAYS = 7
REQUIRED_COOKIE_NAMES = ("auth_token", "ct0")


@dataclass
class DerivedCookies:
    runtime: dict[str, str]
    metadata: dict[str, Any]


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _iso_utc_from_epoch(value: float | int | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return None


def _days_remaining(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value) - datetime.now(tz=UTC).timestamp()
    except (TypeError, ValueError):
        return None
    return round(seconds / 86400, 2)


def derive_from_env(env: dict[str, str], *, warning_days: int) -> DerivedCookies:
    auth_token = env.get("XACTIONS_SESSION_COOKIE", "").strip()
    if not auth_token:
        raise ValueError("XACTIONS_SESSION_COOKIE is missing")

    ct0 = (env.get("X_CT0") or env.get("X_CSRF_TOKEN") or env.get("TWIKIT_CT0") or "").strip()
    if not ct0:
        raise ValueError("ct0 is missing in env source; expected X_CT0, X_CSRF_TOKEN, or TWIKIT_CT0")

    runtime = {"auth_token": auth_token, "ct0": ct0}
    metadata = {
        "source": "env",
        "warning_window_days": warning_days,
        "cookies": {
            "auth_token": {"present": True, "expires_at": None, "days_remaining": None},
            "ct0": {"present": True, "expires_at": None, "days_remaining": None},
        },
        "missing_required": [],
        "warnings": ["expiry_unknown_from_env_source"],
        "derived_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
    }
    return DerivedCookies(runtime=runtime, metadata=metadata)


def derive_from_browser_export(records: list[dict[str, Any]], *, warning_days: int) -> DerivedCookies:
    by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        name = str(record.get("name") or "").strip()
        if name:
            by_name[name] = record

    runtime: dict[str, str] = {}
    cookie_meta: dict[str, Any] = {}
    missing_required: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_COOKIE_NAMES:
        record = by_name.get(name)
        if not record:
            missing_required.append(name)
            cookie_meta[name] = {"present": False, "expires_at": None, "days_remaining": None}
            continue
        value = str(record.get("value") or "").strip()
        if not value:
            missing_required.append(name)
            cookie_meta[name] = {"present": False, "expires_at": None, "days_remaining": None}
            continue
        runtime[name] = value
        expires_raw = record.get("expirationDate")
        expires_at = _iso_utc_from_epoch(expires_raw)
        days_remaining = _days_remaining(expires_raw)
        cookie_meta[name] = {
            "present": True,
            "domain": record.get("domain"),
            "path": record.get("path"),
            "secure": record.get("secure"),
            "http_only": record.get("httpOnly"),
            "same_site": record.get("sameSite"),
            "session": record.get("session"),
            "expires_at": expires_at,
            "days_remaining": days_remaining,
        }
        if days_remaining is not None and days_remaining <= warning_days:
            warnings.append(f"{name}_expiring_soon")

    if missing_required:
        missing_text = ", ".join(missing_required)
        raise ValueError(f"browser export missing required cookies: {missing_text}")

    earliest_days = None
    earliest_name = None
    for name in REQUIRED_COOKIE_NAMES:
        days = cookie_meta[name]["days_remaining"]
        if days is None:
            continue
        if earliest_days is None or days < earliest_days:
            earliest_days = days
            earliest_name = name

    metadata = {
        "source": "browser_export",
        "warning_window_days": warning_days,
        "cookies": cookie_meta,
        "missing_required": [],
        "warnings": warnings,
        "earliest_expiring_cookie": earliest_name,
        "earliest_days_remaining": earliest_days,
        "derived_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
    }
    return DerivedCookies(runtime=runtime, metadata=metadata)


def write_json_file(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def write_runtime_file(path: Path, payload: dict[str, str], *, force: bool) -> None:
    write_json_file(path, payload, force=force)


def load_browser_export(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("browser export must be a JSON array")
    records: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            records.append(item)
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Twikit runtime cookies and metadata from browser export or env."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--browser-export",
        default=str(DEFAULT_BROWSER_EXPORT_FILE),
        help="Path to the richer browser-export JSON file (default: ~/.hermes/x_browser_cookies.json).",
    )
    source.add_argument(
        "--env-file",
        default=None,
        help="Fallback env source file; expects XACTIONS_SESSION_COOKIE and ct0 env vars.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_FILE),
        help="Path to the Twikit runtime cookies JSON file (default: ~/.hermes/x_cookies.json).",
    )
    parser.add_argument(
        "--meta-output",
        default=str(DEFAULT_META_FILE),
        help="Path to the metadata sidecar JSON file (default: ~/.hermes/x_cookies.meta.json).",
    )
    parser.add_argument(
        "--warning-days",
        type=int,
        default=DEFAULT_WARNING_DAYS,
        help="Emit expiring-soon warnings when cookies are within this many days of expiry.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output files if they already exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_file = Path(args.output).expanduser()
    meta_output_file = Path(args.meta_output).expanduser()

    try:
        if args.env_file:
            env_file = Path(args.env_file).expanduser()
            if not env_file.exists():
                print(f"env file not found: {env_file}", file=sys.stderr)
                return 1
            derived = derive_from_env(parse_env_file(env_file), warning_days=args.warning_days)
        else:
            browser_export_file = Path(args.browser_export).expanduser()
            if not browser_export_file.exists():
                print(f"browser export file not found: {browser_export_file}", file=sys.stderr)
                return 1
            derived = derive_from_browser_export(
                load_browser_export(browser_export_file), warning_days=args.warning_days
            )
        write_runtime_file(output_file, derived.runtime, force=args.force)
        write_json_file(meta_output_file, derived.metadata, force=args.force)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    keys = ", ".join(sorted(derived.runtime))
    warnings = ", ".join(derived.metadata.get("warnings") or []) or "none"
    print(f"wrote {output_file} with cookie keys: {keys}")
    print(f"wrote {meta_output_file} warnings={warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
