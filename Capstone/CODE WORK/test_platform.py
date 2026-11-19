import unittest
import os
import json
from app import app
from database import init_db, get_dashboard_metrics, get_test_records
from modules.module1_config import parse_wsdl_content, generate_soap_request_template
from modules.module2_validation import validate_xml_against_xsd, assess_contract_compatibility
from modules.mock_services import CALCULATOR_WSDL

class TestWebServicePlatform(unittest.TestCase):
    def setUp(self):
        init_db()
        self.client = app.test_client()

    def test_module1_wsdl_parser(self):
        result = parse_wsdl_content(CALCULATOR_WSDL)
        self.assertTrue(result["success"])
        self.assertEqual(result["target_namespace"], "http://example.com/calculator")
        self.assertGreater(len(result["operations"]), 0)
        
        # Test request template generator
        template = generate_soap_request_template(result["target_namespace"], "Add", {"intA": "10", "intB": "20"})
        self.assertIn("<tns:Add>", template)
        self.assertIn("<intA>10</intA>", template)

    def test_module2_contract_validation(self):
        with open("sample_data/calculator_schema.xsd", "r") as f:
            xsd = f.read()
        with open("sample_data/valid_add_request.xml", "r") as f:
            valid_xml = f.read()
        with open("sample_data/invalid_type_request.xml", "r") as f:
            invalid_xml = f.read()
        with open("sample_data/missing_field_request.xml", "r") as f:
            missing_xml = f.read()

        # 1. Valid test
        res_valid = validate_xml_against_xsd(valid_xml, xsd)
        self.assertTrue(res_valid["valid"])

        # 2. Invalid data type
        res_invalid = validate_xml_against_xsd(invalid_xml, xsd)
        self.assertFalse(res_valid["valid"] == False)
        self.assertFalse(res_invalid["valid"])
        self.assertGreater(len(res_invalid["errors"]), 0)

        # 3. Missing required field
        res_missing = validate_xml_against_xsd(missing_xml, xsd)
        self.assertFalse(res_missing["valid"])
        self.assertGreater(len(res_missing["errors"]), 0)

    def test_module2_compatibility_diff(self):
        with open("sample_data/contract_v1.xsd", "r") as f:
            v1 = f.read()
        with open("sample_data/contract_v2_breaking.xsd", "r") as f:
            v2_break = f.read()
        with open("sample_data/contract_v2_compatible.xsd", "r") as f:
            v2_compat = f.read()

        # Breaking check
        res_break = assess_contract_compatibility(v1, v2_break)
        self.assertFalse(res_break["is_compatible"])
        self.assertGreater(len(res_break["breaking_changes"]), 0)

        # Compatible check
        res_compat = assess_contract_compatibility(v1, v2_compat)
        self.assertTrue(res_compat["is_compatible"])
        self.assertEqual(len(res_compat["breaking_changes"]), 0)

    def test_module3_soap_communication(self):
        # Test live roundtrip to built-in Calculator mock Add
        payload = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:Add>
      <tns:intA>50</tns:intA>
      <tns:intB>75</tns:intB>
    </tns:Add>
  </soap:Body>
</soap:Envelope>"""
        
        resp = self.client.post("/soap/calculator", data=payload, content_type="text/xml; charset=utf-8")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("AddResult", resp.get_data(as_text=True))
        self.assertIn("125", resp.get_data(as_text=True))

        # Test SOAP Fault (Divide by zero)
        div_zero_payload = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:Divide>
      <tns:intA>10</tns:intA>
      <tns:intB>0</tns:intB>
    </tns:Divide>
  </soap:Body>
</soap:Envelope>"""
        resp_fault = self.client.post("/soap/calculator", data=div_zero_payload, content_type="text/xml; charset=utf-8")
        self.assertEqual(resp_fault.status_code, 500)
        self.assertIn("soap:Fault", resp_fault.get_data(as_text=True))
        self.assertIn("Division by zero", resp_fault.get_data(as_text=True))

    def test_routes_load(self):
        for route in ["/", "/module1", "/module2", "/module3", "/reports"]:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
