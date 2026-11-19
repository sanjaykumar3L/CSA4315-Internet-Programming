from flask import Blueprint, request, Response
from lxml import etree
import uuid

mock_bp = Blueprint("mock_soap", __name__, url_prefix="/soap")

CALCULATOR_WSDL = """<?xml version="1.0" encoding="UTF-8"?>
<definitions name="CalculatorService"
             targetNamespace="http://example.com/calculator"
             xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="http://example.com/calculator"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema">

  <types>
    <xsd:schema targetNamespace="http://example.com/calculator" elementFormDefault="qualified">
      <xsd:element name="Add">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="intA" type="xsd:int" minOccurs="1"/>
            <xsd:element name="intB" type="xsd:int" minOccurs="1"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="AddResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="AddResult" type="xsd:int"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>

      <xsd:element name="Divide">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="intA" type="xsd:int" minOccurs="1"/>
            <xsd:element name="intB" type="xsd:int" minOccurs="1"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="DivideResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="DivideResult" type="xsd:int"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>

  <message name="AddRequest">
    <part name="parameters" element="tns:Add"/>
  </message>
  <message name="AddResponse">
    <part name="parameters" element="tns:AddResponse"/>
  </message>

  <message name="DivideRequest">
    <part name="parameters" element="tns:Divide"/>
  </message>
  <message name="DivideResponse">
    <part name="parameters" element="tns:DivideResponse"/>
  </message>

  <portType name="CalculatorPortType">
    <operation name="Add">
      <input message="tns:AddRequest"/>
      <output message="tns:AddResponse"/>
    </operation>
    <operation name="Divide">
      <input message="tns:DivideRequest"/>
      <output message="tns:DivideResponse"/>
    </operation>
  </portType>

  <binding name="CalculatorBinding" type="tns:CalculatorPortType">
    <soap:binding transport="http://schemas.xmlsoap.org/soap/http" style="document"/>
    <operation name="Add">
      <soap:operation soapAction="http://example.com/calculator/Add"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
    <operation name="Divide">
      <soap:operation soapAction="http://example.com/calculator/Divide"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
  </binding>

  <service name="CalculatorService">
    <port name="CalculatorPort" binding="tns:CalculatorBinding">
      <soap:address location="http://127.0.0.1:5000/soap/calculator"/>
    </port>
  </service>
</definitions>
"""

ORDER_WSDL = """<?xml version="1.0" encoding="UTF-8"?>
<definitions name="OrderService"
             targetNamespace="http://example.com/orders"
             xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="http://example.com/orders"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema">

  <types>
    <xsd:schema targetNamespace="http://example.com/orders" elementFormDefault="qualified">
      <xsd:element name="CreateOrder">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="customerId" type="xsd:string" minOccurs="1"/>
            <xsd:element name="itemCode" type="xsd:string" minOccurs="1"/>
            <xsd:element name="quantity" type="xsd:int" minOccurs="1"/>
            <xsd:element name="pricePerUnit" type="xsd:decimal" minOccurs="1"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="CreateOrderResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="orderId" type="xsd:string"/>
            <xsd:element name="totalAmount" type="xsd:decimal"/>
            <xsd:element name="status" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>

  <portType name="OrderPortType">
    <operation name="CreateOrder">
      <input message="tns:CreateOrderRequest"/>
      <output message="tns:CreateOrderResponse"/>
    </operation>
  </portType>

  <binding name="OrderBinding" type="tns:OrderPortType">
    <soap:binding transport="http://schemas.xmlsoap.org/soap/http" style="document"/>
    <operation name="CreateOrder">
      <soap:operation soapAction="http://example.com/orders/CreateOrder"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
  </binding>

  <service name="OrderService">
    <port name="OrderPort" binding="tns:OrderBinding">
      <soap:address location="http://127.0.0.1:5000/soap/orders"/>
    </port>
  </service>
</definitions>
"""

@mock_bp.route("/calculator", methods=["GET", "POST"])
def mock_calculator():
    if request.method == "GET":
        if "wsdl" in request.args or request.path.endswith("?wsdl"):
            return Response(CALCULATOR_WSDL, mimetype="text/xml")
        return Response("Calculator SOAP Web Service is Active. Append ?wsdl to view contract.", mimetype="text/plain")

    raw_xml = request.get_data(as_text=True)
    try:
        root = etree.fromstring(raw_xml.encode('utf-8'))
        
        # Check Add
        add_elem = root.find(".//{http://example.com/calculator}Add")
        if add_elem is not None:
            a_elem = add_elem.find("{http://example.com/calculator}intA")
            if a_elem is None:
                a_elem = add_elem.find("intA")
            b_elem = add_elem.find("{http://example.com/calculator}intB")
            if b_elem is None:
                b_elem = add_elem.find("intB")

            if a_elem is None or b_elem is None or a_elem.text is None or b_elem.text is None:
                return generate_soap_fault("Client", "Missing required input parameters 'intA' or 'intB'."), 400
            
            try:
                val_a = int(a_elem.text.strip())
                val_b = int(b_elem.text.strip())
            except ValueError:
                return generate_soap_fault("Client", "Data type mismatch: intA and intB must be valid integers."), 400

            result = val_a + val_b
            soap_resp = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:AddResponse>
      <tns:AddResult>{result}</tns:AddResult>
    </tns:AddResponse>
  </soap:Body>
</soap:Envelope>"""
            return Response(soap_resp, mimetype="text/xml")

        # Check Divide
        div_elem = root.find(".//{http://example.com/calculator}Divide")
        if div_elem is not None:
            a_elem = div_elem.find("{http://example.com/calculator}intA")
            if a_elem is None:
                a_elem = div_elem.find("intA")
            b_elem = div_elem.find("{http://example.com/calculator}intB")
            if b_elem is None:
                b_elem = div_elem.find("intB")

            if a_elem is None or b_elem is None or a_elem.text is None or b_elem.text is None:
                return generate_soap_fault("Client", "Missing parameters for Divide operation."), 400
            
            try:
                val_a = int(a_elem.text.strip())
                val_b = int(b_elem.text.strip())
            except ValueError:
                return generate_soap_fault("Client", "Data type mismatch: intA and intB must be valid integers."), 400

            if val_b == 0:
                return generate_soap_fault("Server", "ArithmeticException: Division by zero is not permitted."), 500

            result = int(val_a / val_b)
            soap_resp = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:DivideResponse>
      <tns:DivideResult>{result}</tns:DivideResult>
    </tns:DivideResponse>
  </soap:Body>
</soap:Envelope>"""
            return Response(soap_resp, mimetype="text/xml")

        return generate_soap_fault("Client", "Unsupported or unrecognized operation."), 400

    except Exception as e:
        return generate_soap_fault("Client", f"XML Parsing Error: {str(e)}"), 400

@mock_bp.route("/orders", methods=["GET", "POST"])
def mock_orders():
    if request.method == "GET":
        if "wsdl" in request.args or request.path.endswith("?wsdl"):
            return Response(ORDER_WSDL, mimetype="text/xml")
        return Response("Order Processing SOAP Web Service is Active. Append ?wsdl to view contract.", mimetype="text/plain")

    raw_xml = request.get_data(as_text=True)
    try:
        root = etree.fromstring(raw_xml.encode('utf-8'))
        create_order_elem = root.find(".//{http://example.com/orders}CreateOrder")
        if create_order_elem is not None:
            qty_elem = create_order_elem.find("{http://example.com/orders}quantity")
            if qty_elem is None:
                qty_elem = create_order_elem.find("quantity")
            price_elem = create_order_elem.find("{http://example.com/orders}pricePerUnit")
            if price_elem is None:
                price_elem = create_order_elem.find("pricePerUnit")

            if qty_elem is None or price_elem is None or qty_elem.text is None or price_elem.text is None:
                return generate_soap_fault("Client", "Missing mandatory order details (quantity, pricePerUnit)."), 400

            qty = int(qty_elem.text)
            price = float(price_elem.text)
            total = round(qty * price, 2)
            new_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

            soap_resp = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/orders">
  <soap:Body>
    <tns:CreateOrderResponse>
      <tns:orderId>{new_id}</tns:orderId>
      <tns:totalAmount>{total}</tns:totalAmount>
      <tns:status>CONFIRMED</tns:status>
    </tns:CreateOrderResponse>
  </soap:Body>
</soap:Envelope>"""
            return Response(soap_resp, mimetype="text/xml")

        return generate_soap_fault("Client", "Unrecognized Order Service Request"), 400
    except Exception as e:
        return generate_soap_fault("Client", f"XML Error: {str(e)}"), 400

def generate_soap_fault(fault_code, fault_string):
    fault_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:{fault_code}</faultcode>
      <faultstring>{fault_string}</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""
    return Response(fault_xml, mimetype="text/xml")
