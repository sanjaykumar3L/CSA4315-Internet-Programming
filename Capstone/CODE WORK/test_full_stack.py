from app import app

client = app.test_client()

# 1. Test index page
r1 = client.get('/')
assert r1.status_code == 200, f'Index failed: {r1.status_code}'

# 2. Test WSDL parsing with Calculator WSDL
wsdl_test = client.get('/soap/calculator?wsdl').get_data(as_text=True)
r2 = client.post('/api/v1/wsdl/parse', json={'wsdl_content': wsdl_test})
assert r2.status_code == 200, f'Parse failed: {r2.status_code}'
data2 = r2.get_json()
assert data2['service_name'] == 'CalculatorService', f'Wrong service: {data2}'
assert len(data2['operations']) == 2, f'Wrong ops: {data2}'

# 3. Test Contract Validation (Valid)
xsd_test = """<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" targetNamespace="http://example.com/test" elementFormDefault="qualified">
<xsd:element name="Item"><xsd:complexType><xsd:sequence><xsd:element name="id" type="xsd:int"/></xsd:sequence></xsd:complexType></xsd:element></xsd:schema>"""
xml_valid = '<Item xmlns="http://example.com/test"><id>10</id></Item>'
r3 = client.post('/api/v1/contract/validate', json={'xml_payload': xml_valid, 'xsd_schema': xsd_test})
assert r3.status_code == 200, f'Valid validation failed: {r3.status_code}'
assert r3.get_json()['is_valid'] == True

# 4. Test Contract Validation (Invalid Type)
xml_invalid = '<Item xmlns="http://example.com/test"><id>ABC</id></Item>'
r4 = client.post('/api/v1/contract/validate', json={'xml_payload': xml_invalid, 'xsd_schema': xsd_test})
assert r4.status_code == 422, f'Invalid validation status unexpected: {r4.status_code}'
assert r4.get_json()['is_valid'] == False
assert len(r4.get_json()['errors']) > 0

# 5. Test Live SOAP Calculation (25 + 75 = 100)
soap_payload = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:Add>
      <tns:intA>25</tns:intA>
      <tns:intB>75</tns:intB>
    </tns:Add>
  </soap:Body>
</soap:Envelope>"""
r5 = client.post('/soap/calculator', data=soap_payload, content_type='text/xml; charset=utf-8')
assert r5.status_code == 200
assert '<tns:AddResult>100</tns:AddResult>' in r5.get_data(as_text=True)

# 6. Test Reports API
r6 = client.get('/api/v1/reports')
assert r6.status_code == 200
assert len(r6.get_json()['records']) > 0

print("FULL-STACK SMOKE TEST PASSED: All 6 endpoints verified with real data!")
