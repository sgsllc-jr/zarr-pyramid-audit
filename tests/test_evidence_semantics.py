import importlib.util
import io
import json
from pathlib import Path
import unittest

from lib.httpstore import HttpStore, S3Store, StoreError
from lib.zarrmeta import read_pyramid


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audit_pyramid", ROOT / "bin" / "audit_pyramid.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


GROUP = {"zarr_format": 2}
ATTRS = {"multiscales": [{"datasets": [{"path": "0"}]}]}
ARRAY = {
    "zarr_format": 2,
    "shape": [4, 4],
    "chunks": [2, 2],
    "dtype": "<u2",
    "fill_value": 0,
    "compressor": None,
    "order": "C",
    "dimension_separator": ".",
}


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


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


def routed_store(routes):
    store = HttpStore("https://fixture.invalid/", tries=1)
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        outcome = routes.get(path, (404, b""))
        if isinstance(outcome, Exception):
            raise outcome
        status, body = outcome
        return Response(status, body)

    store._request = request
    return store, calls


def audit_routes(routes, *, check_chunks=True):
    store, calls = routed_store(routes)
    pm = read_pyramid(store, "root", probe_extra_levels=0,
                      check_chunks=check_chunks)
    findings, levels, record = audit.audit_one(pm)
    return pm, findings, levels, record, calls


class EvidenceSemanticsTests(unittest.TestCase):
    def test_successful_json_read_is_present(self):
        store, _ = routed_store({"root/.zgroup": (200, encoded(GROUP))})
        result = store.json_evidence("root/.zgroup")
        self.assertEqual((result.state, result.reason), ("PRESENT", None))

    def test_confirmed_404_is_absent(self):
        store, _ = routed_store({"root/.zgroup": (404, b"")})
        result = store.json_evidence("root/.zgroup")
        self.assertEqual((result.state, result.reason), ("ABSENT", "NOT_FOUND"))

    def test_http_403_is_unknown_not_absent(self):
        store, _ = routed_store({"root/.zgroup": (403, b"")})
        result = store.json_evidence("root/.zgroup")
        self.assertEqual((result.state, result.reason), ("UNKNOWN", "FORBIDDEN"))

    def test_http_503_is_unknown_not_empty(self):
        _, findings, _, record, _ = audit_routes({
            "root/.zgroup": (503, b""),
            "root/zarr.json": (503, b""),
            "root/.zarray": (503, b""),
            "root/": (503, b""),
        })
        self.assertEqual([f["code"] for f in findings], ["ACCESS_UNKNOWN"])
        self.assertEqual((record["evidence_state"], record["evidence_reason"]),
                         ("UNKNOWN", "SERVER_ERROR"))

    def test_transport_exceptions_are_unknown(self):
        cases = {
            "timeout": (StoreError("GET failed: timeout"), "TIMEOUT"),
            "connection": (StoreError("GET failed: connection refused"),
                           "CONNECTION_ERROR"),
        }
        for name, (error, reason) in cases.items():
            with self.subTest(name=name):
                store, _ = routed_store({"root/.zgroup": error})
                result = store.json_evidence("root/.zgroup")
                self.assertEqual((result.state, result.reason),
                                 ("UNKNOWN", reason))

    def test_empty_listing_is_distinct_from_listing_failure(self):
        empty, _ = routed_store({"root/": (200, b"<html></html>")})
        failed, _ = routed_store({"root/": (503, b"")})
        empty_result = empty.list_dir_evidence("root")
        failed_result = failed.list_dir_evidence("root")
        self.assertEqual((empty_result.state, empty_result.dirs, empty_result.files),
                         ("PRESENT", [], []))
        self.assertEqual((failed_result.state, failed_result.reason),
                         ("UNKNOWN", "SERVER_ERROR"))

    def test_unknown_header_is_not_overridden_by_empty_listing(self):
        _, findings, _, record, _ = audit_routes({
            "root/.zgroup": (503, b""),
            "root/zarr.json": (404, b""),
            "root/.zarray": (404, b""),
            "root/": (200, b"<html></html>"),
        })
        self.assertEqual([f["code"] for f in findings], ["ACCESS_UNKNOWN"])
        self.assertEqual(record["evidence_state"], "UNKNOWN")

    def test_confirmed_missing_level_remains_level_missing(self):
        pm, findings, levels, _, _ = audit_routes({
            "root/.zgroup": (200, encoded(GROUP)),
            "root/.zattrs": (200, encoded(ATTRS)),
            "root/0/.zarray": (404, b""),
            "root/0/zarr.json": (404, b""),
        }, check_chunks=False)
        self.assertEqual([f["code"] for f in findings], ["LEVEL_MISSING"])
        self.assertEqual(pm.levels[0].evidence_state, "ABSENT")
        self.assertEqual(levels, [])

    def test_confirmed_empty_structure_remains_empty_zarr_dir(self):
        _, findings, _, record, _ = audit_routes({
            "root/.zgroup": (404, b""),
            "root/zarr.json": (404, b""),
            "root/.zarray": (404, b""),
            "root/": (200, b"<html></html>"),
        })
        self.assertEqual([f["code"] for f in findings], ["EMPTY_ZARR_DIR"])
        self.assertEqual((record["evidence_state"], record["evidence_reason"]),
                         ("ABSENT", "EMPTY_STRUCTURE"))

    def test_confirmed_root_404_is_absent_not_empty(self):
        _, findings, _, record, _ = audit_routes({
            "root/.zgroup": (404, b""),
            "root/zarr.json": (404, b""),
            "root/.zarray": (404, b""),
            "root/": (404, b""),
        })
        self.assertEqual([f["code"] for f in findings], ["ROOT_ABSENT"])
        self.assertEqual((record["evidence_state"], record["kind"]),
                         ("ABSENT", "absent"))

    def test_unsupported_listing_keeps_chunk_inventory_unknown(self):
        pm, findings, levels, _, _ = audit_routes({
            "root/.zgroup": (200, encoded(GROUP)),
            "root/.zattrs": (200, encoded(ATTRS)),
            "root/0/.zarray": (200, encoded(ARRAY)),
            "root/0/": (405, b""),
        })
        self.assertNotIn("LEVEL_NO_CHUNKS", [f["code"] for f in findings])
        self.assertEqual((pm.levels[0].chunk_evidence_state,
                          pm.levels[0].chunk_evidence_reason),
                         ("UNKNOWN", "LISTING_UNSUPPORTED"))
        self.assertEqual(levels[0]["chunk_evidence_state"], "UNKNOWN")

    def test_malformed_metadata_is_unreadable_not_missing(self):
        _, findings, _, record, _ = audit_routes({
            "root/.zgroup": (200, b"{not-json"),
            "root/zarr.json": (404, b""),
            "root/.zarray": (404, b""),
        })
        self.assertEqual([f["code"] for f in findings], ["METADATA_UNREADABLE"])
        self.assertEqual(record["evidence_reason"], "METADATA_UNREADABLE")

    def test_legacy_store_adapter_remains_supported(self):
        class LegacyStore:
            def try_json(self, path):
                if path == "root/.zarray":
                    return ARRAY, None
                return None, f"404 Not Found: {path}"

            def list_dir(self, _path):
                return [], [".zarray", "0.0"]

            def head(self, path):
                return type("Info", (), {"path": path, "exists": False})()

        pm = read_pyramid(LegacyStore(), "root", probe_extra_levels=0)
        findings, _, _ = audit.audit_one(pm)
        self.assertEqual(pm.node_kind, "array")
        self.assertEqual([f["code"] for f in findings], ["BARE_ARRAY"])

    def test_legacy_wrapper_signatures_remain_tuples(self):
        store, _ = routed_store({
            "root/.zgroup": (200, encoded(GROUP)),
            "root/": (200, b"<html></html>"),
        })
        json_result = store.try_json("root/.zgroup")
        listing_result = store.list_dir("root")
        self.assertIsInstance(json_result, tuple)
        self.assertEqual(len(json_result), 2)
        self.assertIsInstance(listing_result, tuple)
        self.assertEqual(len(listing_result), 2)

    def test_s3_store_preserves_object_evidence(self):
        class FakeFS:
            def __init__(self, outcome):
                self.outcome = outcome

            def open(self, *_args, **_kwargs):
                if isinstance(self.outcome, Exception):
                    raise self.outcome
                return io.BytesIO(self.outcome)

        cases = {
            "present": (encoded(GROUP), "PRESENT", None),
            "absent": (FileNotFoundError("missing"), "ABSENT", "NOT_FOUND"),
            "permission": (PermissionError("access denied"), "UNKNOWN", "FORBIDDEN"),
            "service": (OSError("HTTP 503 service unavailable"),
                        "UNKNOWN", "SERVER_ERROR"),
            "timeout": (TimeoutError("timed out"), "UNKNOWN", "TIMEOUT"),
        }
        for name, (outcome, state, reason) in cases.items():
            with self.subTest(name=name):
                store = S3Store.__new__(S3Store)
                store.fs = FakeFS(outcome)
                store.base_url = "s3://fixture/"
                result = store.json_evidence("root/.zgroup")
                self.assertEqual((result.state, result.reason), (state, reason))

    def test_header_audit_does_not_fetch_chunks(self):
        _, findings, _, _, calls = audit_routes({
            "root/.zgroup": (200, encoded(GROUP)),
            "root/.zattrs": (200, encoded(ATTRS)),
            "root/0/.zarray": (200, encoded(ARRAY)),
            "root/0/": (200, b'<a href=".zarray">h</a><a href="0.0">c</a>'),
        })
        self.assertEqual(findings, [])
        requested = [path for _, path, _ in calls]
        self.assertEqual(requested,
                         ["root/.zgroup", "root/.zattrs",
                          "root/0/.zarray", "root/0/"])

    def test_confirmed_zero_chunk_inventory_remains_visible(self):
        _, findings, levels, _, _ = audit_routes({
            "root/.zgroup": (200, encoded(GROUP)),
            "root/.zattrs": (200, encoded(ATTRS)),
            "root/0/.zarray": (200, encoded(ARRAY)),
            "root/0/": (200, b'<a href=".zarray">header</a>'),
        })
        self.assertEqual([f["code"] for f in findings], ["LEVEL_NO_CHUNKS"])
        self.assertEqual((levels[0]["has_chunks"],
                          levels[0]["chunk_evidence_state"],
                          levels[0]["chunk_evidence_reason"]),
                         (False, "ABSENT", "NO_CHUNK_KEYS"))


if __name__ == "__main__":
    unittest.main()
