#!/usr/bin/env python3
"""Reproduce bare-array classification on eight public PHerc1667 v3 stores.

Only fetches .zgroup and zarr.json headers; never lists or downloads chunks.
Use --replay to classify the exact same captured responses after a change.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.httpstore import HttpStore
from lib.zarrmeta import read_pyramid

spec = importlib.util.spec_from_file_location("audit_pyramid", Path(__file__).with_name("audit_pyramid.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

BASE = "https://dl.ash2txt.org/"
PREFIX = "community-uploads/forrest/tsm/PHerc1667/"
ROOTS = [PREFIX + p for p in (
    "labels/coarse.zarr", "labels/fine.zarr", "rectoverso/rectoverso.zarr",
    "teachers/fiber.zarr", "teachers/ink.zarr", "teachers/lasagna.zarr",
    "teachers/m7_l2.zarr", "teachers/recto.zarr",
)]


class ReplayStore:
    def __init__(self, responses):
        self.responses = responses

    def try_json(self, path):
        response = self.responses[path]  # unexpected probes must fail loudly
        if response["status"] != 200:
            return None, f"HTTP {response['status']}"
        return json.loads(response["body"]), None

    def list_dir(self, path):
        raise AssertionError(f"A bare array must not trigger a directory crawl: {path}")

    def head(self, path):
        raise AssertionError(f"A bare array must not trigger a level probe: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if bool(args.capture) == bool(args.replay):
        parser.error("choose exactly one of --capture or --replay")
    if args.capture:
        store = HttpStore(BASE, timeout=20, tries=2, max_rps=3)
        responses = {}
        for root in ROOTS:
            for name in (".zgroup", "zarr.json"):
                path = f"{root}/{name}"
                response = store._request("GET", path)
                if response.status_code not in (200, 404):
                    raise RuntimeError(f"Unexpected HTTP {response.status_code}: {path}")
                responses[path] = {
                    "url": BASE + path, "status": response.status_code,
                    "body": response.content.decode("utf-8"),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
        capture = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "responses": responses}
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        with args.capture.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(capture, handle, indent=2)
            handle.write("\n")
    else:
        capture = json.loads(args.replay.read_text(encoding="utf-8"))
    for response in capture["responses"].values():
        assert hashlib.sha256(response["body"].encode("utf-8")).hexdigest() == response["sha256"]
    store = ReplayStore(capture["responses"])
    for root in ROOTS:
        pm = read_pyramid(store, root)
        findings, levels, record = audit.audit_one(pm)
        print(json.dumps({"root": root, "format": pm.zarr_format,
                          "node_kind": pm.node_kind, "codes": [f["code"] for f in findings],
                          "errors": pm.errors, "levels": len(levels)}, sort_keys=True))


if __name__ == "__main__":
    main()
