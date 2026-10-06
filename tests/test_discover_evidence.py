import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from lib.httpstore import HttpStore


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "discover_zarr", ROOT / "bin" / "discover_zarr.py")
discover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discover)


class Response:
    def __init__(self, status, body=b""):
        self.status_code = status
        self.content = body
        self.headers = {"Content-Length": str(len(body))}

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def close(self):
        pass


def index(*names):
    links = "".join(f'<a href="{n}">{n}</a>' for n in names)
    return (200, f"<html><body>{links}</body></html>".encode())


def run_discover(routes):
    store = HttpStore("https://fixture.invalid/", tries=1)

    def request(method, path, **kwargs):
        outcome = routes.get(path, (404, b""))
        if isinstance(outcome, Exception):
            raise outcome
        return Response(*outcome)

    store._request = request
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as out:
        argv = ["discover_zarr.py", "--base", "https://fixture.invalid/",
                "--workers", "2", "--out-dir", out]
        saved_argv, saved_open = sys.argv, discover.open_store
        sys.argv, discover.open_store = argv, lambda *a, **k: store
        err = io.StringIO()
        try:
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(err):
                rc = discover.main()
        finally:
            sys.argv, discover.open_store = saved_argv, saved_open
        out = Path(out)
        roots = [json.loads(l) for l in
                 (out / "discover_zarr.roots.jsonl").read_text().splitlines()]
        dirs = [json.loads(l) for l in
                (out / "discover_zarr.dirs.jsonl").read_text().splitlines()]
        manifest = json.loads((out / "discover_zarr.manifest.json").read_text())
    return rc, roots, dirs, manifest, err.getvalue()


class DiscoverEvidenceTests(unittest.TestCase):
    def test_unknown_listing_is_counted_and_not_treated_as_empty(self):
        rc, roots, dirs, man, err = run_discover({
            "/": index("good/", "throttled/", "denied/"),
            "good/": index("a.zarr/"),
            "throttled/": (503, b""),
            "denied/": (403, b""),
        })
        self.assertEqual(rc, 0)
        self.assertEqual([r["root"] for r in roots], ["good/a.zarr"])
        c = man["counters"]
        self.assertEqual(c.get("list_errors"), 2)
        self.assertEqual(c.get("list_unknown_server_error"), 1)
        self.assertEqual(c.get("list_unknown_forbidden"), 1)
        self.assertFalse(man["listing_complete"])
        self.assertEqual(man["unverified_dirs"], ["denied", "throttled"])
        bad = {d["path"]: d for d in dirs if d["evidence_state"] != "PRESENT"}
        self.assertEqual(bad["throttled"]["evidence_reason"], "SERVER_ERROR")
        self.assertEqual(bad["denied"]["evidence_reason"], "FORBIDDEN")
        self.assertNotIn("n_subdirs", bad["throttled"])
        self.assertIn("UNVERIFIED", err)

    def test_confirmed_404_is_absent_not_an_error(self):
        rc, roots, dirs, man, err = run_discover({
            "/": index("gone/", "ok/"),
            "ok/": index(),
        })
        c = man["counters"]
        self.assertEqual(c.get("list_absent"), 1)
        self.assertEqual(c.get("list_errors", 0), 0)
        self.assertTrue(man["listing_complete"])
        self.assertEqual(man["unverified_dirs"], [])
        self.assertEqual(err, "")

    def test_empty_listing_is_present_and_complete(self):
        rc, roots, dirs, man, err = run_discover({"/": index()})
        self.assertEqual(roots, [])
        self.assertEqual(man["counters"].get("dirs_listed"), 1)
        self.assertEqual(man["counters"].get("list_errors", 0), 0)
        self.assertTrue(man["listing_complete"])
        self.assertEqual(dirs[0]["evidence_state"], "PRESENT")


if __name__ == "__main__":
    unittest.main()
