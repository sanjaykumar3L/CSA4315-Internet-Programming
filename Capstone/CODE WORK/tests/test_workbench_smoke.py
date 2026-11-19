"""Smoke and regression checks for the capstone workbench foundation.

Run from Capstone/CODE WORK:
    python -m unittest discover -s tests -v

These tests use the Flask test client and do not require an external SOAP service.
"""
import unittest

from app import app, check_soap_endpoint, parse_wsdl_stream, CALCULATOR_WSDL


class CapstoneWorkbenchSmokeTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_main_interface_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("workbench-sidebar", text)
        self.assertIn("workbench.css", text)
        self.assertIn(
            "Integrated Web Service Interoperability and Data Contract Validation for Reliable System Communication",
            text,
        )
        for title in (
            "Web Service Configuration and Integration",
            "Data Contract Validation and Compatibility Testing",
            "Communication Monitoring and Validation Report Generation",
        ):
            self.assertIn(title, text)

    def test_workbench_stylesheet_is_served(self):
        response = self.client.get("/static/css/workbench.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"workbench-sidebar", response.data)

    def test_real_audit_api_has_records_array(self):
        response = self.client.get("/api/v1/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json()["records"], list)

    def test_builtin_wsdl_discovery(self):
        parsed = parse_wsdl_stream(CALCULATOR_WSDL.encode("utf-8"))
        self.assertTrue(parsed["success"])
        names = [op["operation_name"] for op in parsed["operations"]]
        self.assertIn("Add", names)
        self.assertIn("Divide", names)

    def test_soap_envelope_escapes_untrusted_values(self):
        response = self.client.post("/api/v1/wsdl/generate-envelope", json={
            "operation_name": "Add",
            "target_namespace": "http://example.com/calculator",
            "parameters": {"intA": "<not-an-xml-element>&", "intB": "5"}
        })
        self.assertEqual(response.status_code, 200)
        envelope = response.get_json()["request_envelope"]
        self.assertIn("&lt;not-an-xml-element&gt;&amp;", envelope)

    def test_invalid_operation_name_returns_400(self):
        response = self.client.post("/api/v1/wsdl/generate-envelope", json={
            "operation_name": "not valid",
            "target_namespace": "http://example.com/calculator",
            "parameters": {}
        })
        self.assertEqual(response.status_code, 400)

    def test_private_destination_rejected(self):
        self.assertIsNotNone(check_soap_endpoint("http://192.168.0.10:8080/api"))
        self.assertIsNotNone(check_soap_endpoint("file:///etc/passwd"))
        self.assertIsNone(check_soap_endpoint("http://127.0.0.1:5000/soap/calculator"))

    def test_invalid_timeout_rejected_before_network_call(self):
        response = self.client.post("/api/v1/soap/execute", json={
            "endpoint_url": "https://example.com/api",
            "request_xml": "<Envelope/>",
            "timeout": "infinite"
        })
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
