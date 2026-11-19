"""Comprehensive API and durable-history regression tests.

Run: python -m unittest discover -s tests -v
No external SOAP endpoint or Blob credential is required.
"""
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as backend
import persistent_history


HERE = Path(__file__).resolve().parent.parent
SAMPLES = HERE / "sample_data"


class ModuleIntegrationTests(unittest.TestCase):
    def setUp(self):
        backend.app.testing = True
        self.client = backend.app.test_client()

    def test_valid_and_invalid_xsd_contracts(self):
        xsd = (SAMPLES / "calculator_schema.xsd").read_text()
        good = (SAMPLES / "valid_add_request.xml").read_text()
        bad_type = (SAMPLES / "invalid_type_request.xml").read_text()
        missing = (SAMPLES / "missing_field_request.xml").read_text()
        for xml, expected in [(good, True), (bad_type, False), (missing, False)]:
            result = backend.validate_xml_with_xsd(xml, xsd)
            self.assertEqual(result["is_valid"], expected, result)

    def test_v1_v2_contract_compatibility(self):
        v1 = (SAMPLES / "contract_v1.xsd").read_text()
        compatible = (SAMPLES / "contract_v2_compatible.xsd").read_text()
        incompatible = (SAMPLES / "contract_v2_breaking.xsd").read_text()
        self.assertTrue(backend.diff_schema_compatibility(v1, compatible)["is_compatible"])
        self.assertFalse(backend.diff_schema_compatibility(v1, incompatible)["is_compatible"])

    def test_soap_fault_for_division_by_zero(self):
        envelope = """<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:tns="http://example.com/calculator"><soap:Body>
        <tns:Divide><tns:intA>8</tns:intA><tns:intB>0</tns:intB></tns:Divide>
        </soap:Body></soap:Envelope>"""
        response = self.client.post("/soap/calculator", data=envelope, content_type="text/xml")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Division by zero", response.data)

    def test_soap_12_envelope_generation(self):
        response = self.client.post("/api/v1/wsdl/generate-envelope", json={
            "operation_name": "Add",
            "target_namespace": "http://example.com/calculator",
            "soap_version": "1.2",
            "parameters": {"intA": "4", "intB": "9"},
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("http://www.w3.org/2003/05/soap-envelope", response.get_json()["request_envelope"])

    def test_pdf_escapes_untrusted_service_text(self):
        record = {
            "id": 123, "service_name": "A&B <C>",
            "operation_name": "Add", "endpoint_url": "https://example.com/?a=1&b=2",
            "status": "FAILED", "test_type": "CONTRACT_VALIDATION",
            "summary": "bad <markup> & text",
            "validation_errors_list": [{"category": "Bad <field>", "message": "hello <world> & error"}],
        }
        destination = io.BytesIO()
        backend.build_pdf_document(record, destination)
        self.assertTrue(destination.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(destination.getvalue()), 800)


class DurableBlobHistoryTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        self.put = patch.object(persistent_history, "put_blob", side_effect=self.fake_put).start()
        self.list = patch.object(persistent_history, "query_blobs", side_effect=self.fake_list).start()
        self.get = patch.object(persistent_history, "get_blob", side_effect=self.fake_get).start()
        self.addCleanup(patch.stopall)

    def fake_put(self, pathname, data, **kwargs):
        self.saved[pathname] = data
        self.assertEqual(kwargs["access"], "private")
        return SimpleNamespace(pathname=pathname)

    def fake_list(self, prefix="", **kwargs):
        items = [SimpleNamespace(pathname=key) for key in self.saved if key.startswith(prefix)]
        return iter(items)

    def fake_get(self, pathname, **kwargs):
        data = self.saved.get(pathname)
        if not data:
            return None
        return SimpleNamespace(body=data)

    def test_record_round_trip_and_unique_ids(self):
        ids = [
            persistent_history.create_record({
                "service_name": "Test", "status": "PASSED", "validation_errors_list": []
            })
            for _ in range(4)
        ]
        self.assertEqual(len(ids), len(set(ids)))
        listed = persistent_history.list_records()
        self.assertEqual(len(listed), 4)
        self.assertEqual({r["id"] for r in listed}, set(ids))
        self.assertEqual(persistent_history.get_record(ids[0])["service_name"], "Test")

    def test_api_uses_durable_storage_in_vercel_mode(self):
        with patch.object(backend, "HAS_PERSISTENT_STORAGE", True):
            record_id = backend.db_save_test_record(
                "Calculator", "Add", "https://example.com/soap", "SOAP_COMMUNICATION",
                "PASSED", 18.0, 200, "<request/>", "<response/>", [], "", "ok"
            )
            self.assertIsInstance(record_id, int)
            history = backend.db_get_test_records(limit=100)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["id"], record_id)
            self.assertEqual(backend.db_get_record_by_id(record_id)["operation_name"], "Add")
            response = backend.app.test_client().get(f"/reports/{record_id}/pdf")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
