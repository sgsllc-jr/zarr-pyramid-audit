import importlib.util
import json
from pathlib import Path
import unittest

from lib.zarrmeta import read_pyramid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repro", ROOT / "bin/reproduce_v3_arrays.py")
repro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repro)


class MetadataStore:
    def __init__(self, documents):
        self.documents = documents
        self.calls = []

    def try_json(self, path):
        self.calls.append(path)
        return self.documents.get(path), None

    def list_dir(self, path):
        raise AssertionError(f"Unexpected listing: {path}")


class ZarrNodeClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = json.loads((ROOT / "artifacts/2026-09-25-v3-arrays/headers.json").read_text())

    def test_real_pherc1667_v3_arrays_are_classified_without_chunk_reads(self):
        for root in repro.ROOTS:
            with self.subTest(root=root):
                pm = read_pyramid(repro.ReplayStore(self.capture["responses"]), root)
                findings, levels, record = repro.audit.audit_one(pm)
                self.assertEqual(pm.node_kind, "array")
                self.assertEqual(pm.zarr_format, 3)
                self.assertEqual(pm.errors, [])
                self.assertFalse(pm.is_group)
                self.assertEqual([f["code"] for f in findings], ["BARE_ARRAY"])
                self.assertEqual(record["kind"], "array")
                self.assertEqual(levels, [])
                self.assertIn("shape=", findings[0]["detail"])
                self.assertIn("channels", pm.attrs_raw)

    def test_array_attributes_do_not_turn_an_array_into_a_group(self):
        response = self.capture["responses"][repro.ROOTS[0] + "/zarr.json"]
        doc = json.loads(response["body"])
        doc["attributes"]["multiscales"] = [{"datasets": [{"path": "0"}]}]
        store = MetadataStore({"root/zarr.json": doc})
        pm = read_pyramid(store, "root")
        self.assertEqual(pm.node_kind, "array")
        self.assertFalse(pm.has_multiscales)
        self.assertEqual(pm.levels, [])
        self.assertEqual(store.calls, ["root/.zgroup", "root/zarr.json"])

    def test_v3_non_multiscale_group_is_still_a_group(self):
        pm = read_pyramid(MetadataStore({"root/zarr.json": {
            "zarr_format": 3, "node_type": "group", "attributes": {}}}), "root")
        self.assertTrue(pm.is_group)
        self.assertEqual(pm.node_kind, "group")
        findings, _, _ = repro.audit.audit_one(pm)
        self.assertEqual([f["code"] for f in findings], ["NOT_MULTISCALE"])

    def test_v3_ome_group_still_reads_its_level(self):
        array = json.loads(self.capture["responses"][repro.ROOTS[0] + "/zarr.json"]["body"])
        group = {"zarr_format": 3, "node_type": "group", "attributes": {"ome": {
            "version": "0.5", "multiscales": [{"datasets": [{"path": "0"}]}]}}}
        pm = read_pyramid(MetadataStore({"root/zarr.json": group, "root/0/zarr.json": array}),
                          "root", probe_extra_levels=0, check_chunks=False)
        self.assertTrue(pm.has_multiscales)
        self.assertEqual(len(pm.levels), 1)
        self.assertTrue(pm.levels[0].present)
        self.assertEqual(pm.levels[0].shape, array["shape"])

    def test_v2_bare_array_classification_is_unchanged(self):
        pm = read_pyramid(MetadataStore({"root/.zarray": {
            "zarr_format": 2, "shape": [10, 20], "chunks": [5, 5], "dtype": "|u1"}}), "root")
        self.assertEqual(pm.node_kind, "array")
        findings, _, _ = repro.audit.audit_one(pm)
        self.assertEqual([f["code"] for f in findings], ["BARE_ARRAY"])

    def test_unknown_node_type_is_not_claimed_as_an_array(self):
        pm = read_pyramid(MetadataStore({"root/zarr.json": {
            "zarr_format": 3, "node_type": "unexpected", "attributes": {}}}), "root")
        self.assertNotEqual(pm.node_kind, "array")
        findings, _, _ = repro.audit.audit_one(pm)
        self.assertEqual([f["code"] for f in findings], ["NOT_A_ZARR_GROUP"])


if __name__ == "__main__":
    unittest.main()
