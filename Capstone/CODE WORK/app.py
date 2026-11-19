import os
import io
import time
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, Response, render_template_string
from flask_cors import CORS
import ipaddress
import socket
from urllib.parse import urlsplit
from lxml import etree
import requests

# ---------------------------------------------------------
# Flask App Setup & CORS
# ---------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, resources={r"/api/*": {"origins": os.environ.get("CAPSTONE_ALLOWED_ORIGIN", "http://127.0.0.1:5000")}})
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max payload

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_history.db")
PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_reports")
os.makedirs(PDF_DIR, exist_ok=True)

# XML & WSDL Standard Namespaces
WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"
SOAP_NS = "http://schemas.xmlsoap.org/wsdl/soap/"
SOAP12_NS = "http://schemas.xmlsoap.org/wsdl/soap12/"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP12_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"

# ---------------------------------------------------------
# Database Layer (SQLite3)
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configured_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            target_namespace TEXT,
            endpoint_url TEXT NOT NULL,
            wsdl_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            operation_name TEXT NOT NULL,
            endpoint_url TEXT NOT NULL,
            test_type TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time_ms REAL,
            http_status_code INTEGER,
            request_xml TEXT,
            response_xml TEXT,
            validation_errors TEXT,
            compatibility_assessment TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def db_save_service(service_name, target_namespace, endpoint_url, wsdl_content):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO configured_services (service_name, target_namespace, endpoint_url, wsdl_content)
            VALUES (?, ?, ?, ?)
        """, (service_name, target_namespace, endpoint_url, wsdl_content))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except Exception as e:
        print(f"[DB ERROR] save_service: {e}")
        return None

def db_save_test_record(service_name, operation_name, endpoint_url, test_type, status,
                        response_time_ms, http_status_code, request_xml, response_xml,
                        validation_errors, compatibility_assessment, summary):
    try:
        conn = get_db()
        cursor = conn.cursor()
        errors_str = json.dumps(validation_errors) if isinstance(validation_errors, (list, dict)) else str(validation_errors or "")
        cursor.execute("""
            INSERT INTO test_records (
                service_name, operation_name, endpoint_url, test_type, status,
                response_time_ms, http_status_code, request_xml, response_xml,
                validation_errors, compatibility_assessment, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            service_name, operation_name, endpoint_url, test_type, status,
            response_time_ms, http_status_code, request_xml, response_xml,
            errors_str, compatibility_assessment, summary
        ))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id
    except Exception as e:
        print(f"[DB ERROR] save_test_record: {e}")
        return None

def db_get_test_records(limit=50):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_records ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        results = []
        for r in rows:
            item = dict(r)
            try:
                item["validation_errors_list"] = json.loads(item["validation_errors"]) if item["validation_errors"] else []
            except Exception:
                item["validation_errors_list"] = [item["validation_errors"]] if item["validation_errors"] else []
            results.append(item)
        return results
    except Exception as e:
        print(f"[DB ERROR] get_test_records: {e}")
        return []

def db_get_record_by_id(record_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        item = dict(row)
        try:
            item["validation_errors_list"] = json.loads(item["validation_errors"]) if item["validation_errors"] else []
        except Exception:
            item["validation_errors_list"] = [item["validation_errors"]] if item["validation_errors"] else []
        return item
    except Exception as e:
        print(f"[DB ERROR] get_record_by_id: {e}")
        return None

# ---------------------------------------------------------
# Core Logic: Module 1 - Real Dynamic WSDL Parser
# ---------------------------------------------------------
def parse_wsdl_stream(wsdl_content_bytes):
    try:
        parser = etree.XMLParser(remove_blank_text=True, recover=False, resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
        root = etree.fromstring(wsdl_content_bytes, parser)
    except etree.XMLSyntaxError as err:
        return {
            "success": False,
            "error_type": "XML_SYNTAX_ERROR",
            "message": f"WSDL XML Syntax Error: {err.msg} (Line {err.lineno}, Col {err.offset})"
        }
    except Exception as e:
        return {
            "success": False,
            "error_type": "PARSE_EXCEPTION",
            "message": f"Failed to parse WSDL: {str(e)}"
        }

    target_namespace = root.attrib.get("targetNamespace", "urn:unspecified-namespace")

    # 1. Extract Services and Port Endpoints
    services = []
    default_endpoint = ""
    for service_node in root.findall(f"{{{WSDL_NS}}}service"):
        s_name = service_node.attrib.get("name", "UnnamedService")
        ports = []
        for port_node in service_node.findall(f"{{{WSDL_NS}}}port"):
            p_name = port_node.attrib.get("name", "UnnamedPort")
            binding = port_node.attrib.get("binding", "")
            
            # Check SOAP 1.1 or 1.2 address
            addr_11 = port_node.find(f"{{{SOAP_NS}}}address")
            addr_12 = port_node.find(f"{{{SOAP12_NS}}}address")
            endpoint_url = ""
            soap_ver = "1.1"
            if addr_11 is not None:
                endpoint_url = addr_11.attrib.get("location", "")
                soap_ver = "1.1"
            elif addr_12 is not None:
                endpoint_url = addr_12.attrib.get("location", "")
                soap_ver = "1.2"

            if endpoint_url and not default_endpoint:
                default_endpoint = endpoint_url

            ports.append({
                "port_name": p_name,
                "binding": binding,
                "endpoint_url": endpoint_url,
                "soap_version": soap_ver
            })
        services.append({
            "service_name": s_name,
            "ports": ports
        })

    # 2. Extract Embedded Schemas & Element Types
    types_node = root.find(f"{{{WSDL_NS}}}types")
    schema_elements = {}
    if types_node is not None:
        for schema in types_node.findall(f"{{{XSD_NS}}}schema"):
            for elem in schema.findall(f"{{{XSD_NS}}}element"):
                el_name = elem.attrib.get("name")
                if not el_name:
                    continue
                # Extract child parameters if complexType
                params = []
                complex_type = elem.find(f"{{{XSD_NS}}}complexType")
                if complex_type is not None:
                    seq = complex_type.find(f"{{{XSD_NS}}}sequence")
                    if seq is not None:
                        for child in seq.findall(f"{{{XSD_NS}}}element"):
                            c_name = child.attrib.get("name", "")
                            c_type = child.attrib.get("type", "xs:string")
                            min_occ = child.attrib.get("minOccurs", "1")
                            params.append({
                                "name": c_name,
                                "type": c_type,
                                "required": min_occ != "0"
                            })
                schema_elements[el_name] = params

    # 3. Extract PortTypes & Operations
    operations = []
    for pt in root.findall(f"{{{WSDL_NS}}}portType"):
        pt_name = pt.attrib.get("name", "DefaultPortType")
        for op in pt.findall(f"{{{WSDL_NS}}}operation"):
            op_name = op.attrib.get("name", "")
            input_node = op.find(f"{{{WSDL_NS}}}input")
            output_node = op.find(f"{{{WSDL_NS}}}output")

            in_msg = input_node.attrib.get("message", "") if input_node is not None else ""
            out_msg = output_node.attrib.get("message", "") if output_node is not None else ""

            # Check if we have element parameters matching the operation name
            params = schema_elements.get(op_name, [])
            operations.append({
                "port_type": pt_name,
                "operation_name": op_name,
                "input_message": in_msg,
                "output_message": out_msg,
                "parameters": params
            })

    service_name = services[0]["service_name"] if services else "ParsedWebService"

    return {
        "success": True,
        "service_name": service_name,
        "target_namespace": target_namespace,
        "default_endpoint": default_endpoint,
        "services": services,
        "operations": operations,
        "total_operations": len(operations)
    }

# ---------------------------------------------------------
# Core Logic: Module 2 - Real XSD & Schema Diff Engine
# ---------------------------------------------------------
def validate_xml_with_xsd(xml_string, xsd_string):
    # Step 1: Syntactic parsing of XML
    try:
        xml_parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
        xml_root = etree.fromstring(xml_string.encode('utf-8'), xml_parser)
    except etree.XMLSyntaxError as se:
        return {
            "is_valid": False,
            "status": "MALFORMED_XML",
            "summary": f"XML document has syntax errors: {se.msg}",
            "errors": [{
                "line": se.lineno,
                "column": se.offset,
                "category": "XML Syntax Error",
                "message": se.msg
            }]
        }
    except Exception as e:
        return {
            "is_valid": False,
            "status": "MALFORMED_XML",
            "summary": f"Could not parse XML: {str(e)}",
            "errors": [{
                "line": 1,
                "column": 1,
                "category": "XML Syntax Error",
                "message": str(e)
            }]
        }

    # Step 2: Compile XSD Schema
    try:
        xsd_root = etree.fromstring(xsd_string.encode('utf-8'), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
        xml_schema = etree.XMLSchema(xsd_root)
    except etree.XMLSchemaParseError as xse:
        return {
            "is_valid": False,
            "status": "INVALID_SCHEMA",
            "summary": f"XSD Schema contains syntax or compilation errors: {str(xse)}",
            "errors": [{
                "line": getattr(xse, "line", 1),
                "column": 0,
                "category": "Schema Compilation Error",
                "message": str(xse)
            }]
        }
    except Exception as e:
        return {
            "is_valid": False,
            "status": "INVALID_SCHEMA",
            "summary": f"Failed to initialize XSD Schema: {str(e)}",
            "errors": [{
                "line": 1,
                "column": 1,
                "category": "Schema Compilation Error",
                "message": str(e)
            }]
        }

    # Step 3: Handle SOAP Envelope Wrapper vs Direct Payload
    target_node = xml_root
    if xml_root.tag in (f"{{{SOAP_ENV_NS}}}Envelope", f"{{{SOAP12_ENV_NS}}}Envelope"):
        body_node = xml_root.find(f"{{{SOAP_ENV_NS}}}Body")
        if body_node is None:
            body_node = xml_root.find(f"{{{SOAP12_ENV_NS}}}Body")
        if body_node is not None and len(body_node) > 0:
            target_node = body_node[0]

    # Step 4: Validate against XSD
    is_valid = xml_schema.validate(target_node)
    if is_valid:
        return {
            "is_valid": True,
            "status": "PASSED",
            "summary": "XML document fully conforms to the XSD Data Contract. All elements and types are valid.",
            "errors": []
        }
    else:
        errors = []
        for err in xml_schema.error_log:
            msg = err.message
            msg_lower = msg.lower()
            category = "Contract Violation"
            if "datatype" in msg_lower or "not a valid value" in msg_lower or "is not a valid value of the atomic type" in msg_lower:
                category = "Data Type Verification Failure"
            elif "missing child element" in msg_lower or "expected" in msg_lower:
                category = "Missing Mandatory Field"
            elif "not allowed" in msg_lower or "unexpected" in msg_lower:
                category = "Unexpected Element / Schema Mismatch"

            errors.append({
                "line": err.line,
                "column": err.column,
                "category": category,
                "message": msg
            })

        return {
            "is_valid": False,
            "status": "FAILED",
            "summary": f"Data contract violation detected ({len(errors)} error(s) found).",
            "errors": errors
        }

def diff_schema_compatibility(v1_xsd, v2_xsd):
    try:
        root_v1 = etree.fromstring(v1_xsd.encode('utf-8'), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
        root_v2 = etree.fromstring(v2_xsd.encode('utf-8'), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse schemas for compatibility diff: {str(e)}"
        }

    def collect_elements(root):
        elems = {}
        for el in root.iter(f"{{{XSD_NS}}}element"):
            name = el.attrib.get("name")
            if name:
                elems[name] = {
                    "type": el.attrib.get("type", "complex/unspecified"),
                    "minOccurs": el.attrib.get("minOccurs", "1"),
                    "maxOccurs": el.attrib.get("maxOccurs", "1")
                }
        return elems

    v1_map = collect_elements(root_v1)
    v2_map = collect_elements(root_v2)

    breaking = []
    non_breaking = []

    # Check for removed elements or changed attributes in existing elements
    for name, v1_attr in v1_map.items():
        if name not in v2_map:
            breaking.append(f"Element '{name}' was removed in V2 schema (Breaking for existing consumers).")
        else:
            v2_attr = v2_map[name]
            if v1_attr["type"] != v2_attr["type"]:
                breaking.append(f"Element '{name}' type changed from '{v1_attr['type']}' to '{v2_attr['type']}'.")
            try:
                if int(v2_attr["minOccurs"]) > int(v1_attr["minOccurs"]):
                    breaking.append(f"Element '{name}' occurrence constraint tightened from minOccurs={v1_attr['minOccurs']} to minOccurs={v2_attr['minOccurs']} (Now strictly mandatory).")
            except ValueError:
                pass

    # Check for new elements in V2
    for name, v2_attr in v2_map.items():
        if name not in v1_map:
            try:
                min_occ = int(v2_attr.get("minOccurs", "1"))
                if min_occ > 0:
                    breaking.append(f"Mandatory new element '{name}' (minOccurs={min_occ}) added in V2 without backward default value.")
                else:
                    non_breaking.append(f"Optional new element '{name}' added (minOccurs=0, backward compatible).")
            except ValueError:
                non_breaking.append(f"New element '{name}' added.")

    is_compatible = (len(breaking) == 0)
    return {
        "success": True,
        "is_compatible": is_compatible,
        "compatibility_status": "COMPATIBLE" if is_compatible else "INCOMPATIBLE (BREAKING CHANGES)",
        "breaking_changes": breaking,
        "non_breaking_changes": non_breaking,
        "v1_count": len(v1_map),
        "v2_count": len(v2_map)
    }

# ---------------------------------------------------------
# Core Logic: Module 3 - Real SOAP Client & PDF Generator
# ---------------------------------------------------------
def check_soap_endpoint(endpoint_url):
    """Reject unsupported/private destinations; allow the built-in local calculator demo."""
    try:
        parsed = urlsplit(endpoint_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return "Only HTTP and HTTPS SOAP endpoints are supported."
        if parsed.username or parsed.password:
            return "Credentials in endpoint URLs are not supported."
        if parsed.hostname in ("127.0.0.1", "localhost", "::1"):
            if parsed.port == 5000 and parsed.path == "/soap/calculator":
                return None
            return "Only the built-in local Calculator SOAP endpoint is allowed on loopback."
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses:
            return "The SOAP endpoint hostname could not be resolved."
        for item in addresses:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                return "Private, loopback and reserved network destinations are blocked."
    except (ValueError, socket.gaierror, OSError) as exc:
        return f"Invalid or unresolved SOAP endpoint: {exc}"
    return None

def dispatch_real_soap_request(endpoint_url, request_xml, soap_action="", soap_version="1.1", timeout=12, service_name="SOAPService", operation_name="Operation"):
    headers = {
        "User-Agent": "Integrated-Contract-Validator/1.0",
    }
    if soap_version == "1.2":
        headers["Content-Type"] = "application/soap+xml; charset=utf-8"
        if soap_action:
            headers["Content-Type"] += f'; action="{soap_action}"'
    else:
        headers["Content-Type"] = "text/xml; charset=utf-8"
        if soap_action:
            headers["SOAPAction"] = f'"{soap_action}"'

    start_timer = time.perf_counter()
    try:
        resp = requests.post(
            endpoint_url,
            data=request_xml.encode('utf-8'),
            headers=headers,
            timeout=timeout,
            allow_redirects=False
        )
        latency_ms = round((time.perf_counter() - start_timer) * 1000, 2)
        status_code = resp.status_code
        response_text = resp.text
    except requests.exceptions.Timeout:
        latency_ms = round((time.perf_counter() - start_timer) * 1000, 2)
        err_msg = f"Network Timeout: Service failed to respond within {timeout} seconds."
        rec_id = db_save_test_record(service_name, operation_name, endpoint_url, "SOAP_COMMUNICATION", "FAILED",
                                    latency_ms, 0, request_xml, "", [{"category": "Timeout", "message": err_msg}], "", err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "error_type": "TIMEOUT",
            "http_status_code": 0,
            "latency_ms": latency_ms,
            "message": err_msg,
            "record_id": rec_id,
            "response_xml": ""
        }
    except requests.exceptions.ConnectionError as ce:
        latency_ms = round((time.perf_counter() - start_timer) * 1000, 2)
        err_msg = f"Connection Failed: Unable to reach {endpoint_url}. ({str(ce)})"
        rec_id = db_save_test_record(service_name, operation_name, endpoint_url, "SOAP_COMMUNICATION", "FAILED",
                                    latency_ms, 0, request_xml, "", [{"category": "Connection Failure", "message": err_msg}], "", err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "error_type": "CONNECTION_ERROR",
            "http_status_code": 0,
            "latency_ms": latency_ms,
            "message": err_msg,
            "record_id": rec_id,
            "response_xml": ""
        }
    except requests.exceptions.RequestException as re:
        latency_ms = round((time.perf_counter() - start_timer) * 1000, 2)
        err_msg = f"HTTP Request Error: {str(re)}"
        rec_id = db_save_test_record(service_name, operation_name, endpoint_url, "SOAP_COMMUNICATION", "FAILED",
                                    latency_ms, 0, request_xml, "", [{"category": "Request Error", "message": err_msg}], "", err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "error_type": "REQUEST_ERROR",
            "http_status_code": 0,
            "latency_ms": latency_ms,
            "message": err_msg,
            "record_id": rec_id,
            "response_xml": ""
        }

    # Inspect Response XML for SOAP Faults
    is_fault = False
    fault_code = ""
    fault_string = ""
    errors = []

    try:
        resp_root = etree.fromstring(response_text.encode('utf-8'), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
        fault_node = resp_root.find(f".//{{{SOAP_ENV_NS}}}Fault")
        if fault_node is None:
            fault_node = resp_root.find(f".//{{{SOAP12_ENV_NS}}}Fault")

        if fault_node is not None:
            is_fault = True
            fc = fault_node.find("faultcode") or fault_node.find(f"{{{SOAP12_ENV_NS}}}Code")
            fs = fault_node.find("faultstring") or fault_node.find(f"{{{SOAP12_ENV_NS}}}Reason")
            fault_code = fc.text if fc is not None else "SOAP:Server"
            fault_string = fs.text if fs is not None else "Internal SOAP Fault encountered."
            errors.append({
                "category": "SOAP Fault Received",
                "fault_code": fault_code,
                "message": fault_string
            })
    except Exception as parse_ex:
        errors.append({
            "category": "Response Parse Warning",
            "message": f"Response could not be parsed as valid XML: {str(parse_ex)}"
        })

    overall_status = "PASSED" if (status_code == 200 and not is_fault) else "FAILED"
    summary = f"SOAP request executed in {latency_ms} ms with HTTP {status_code}."
    if is_fault:
        summary = f"SOAP Fault: [{fault_code}] {fault_string}"
    elif status_code != 200:
        summary = f"HTTP {status_code} Error returned by endpoint."

    rec_id = db_save_test_record(
        service_name=service_name,
        operation_name=operation_name,
        endpoint_url=endpoint_url,
        test_type="SOAP_COMMUNICATION",
        status=overall_status,
        response_time_ms=latency_ms,
        http_status_code=status_code,
        request_xml=request_xml,
        response_xml=response_text,
        validation_errors=errors,
        compatibility_assessment="",
        summary=summary
    )

    return {
        "success": overall_status == "PASSED",
        "status": overall_status,
        "record_id": rec_id,
        "latency_ms": latency_ms,
        "http_status_code": status_code,
        "is_soap_fault": is_fault,
        "fault_code": fault_code,
        "fault_string": fault_string,
        "summary": summary,
        "response_xml": response_text,
        "errors": errors
    }

def build_pdf_document(record, destination_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(destination_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569'), spaceAfter=14)
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=12)

    elements = []
    elements.append(Paragraph("Web Service Interoperability & Contract Validation Audit Report", title_style))
    elements.append(Paragraph(f"Test Execution ID: #{record.get('id', 'N/A')} | Recorded: {record.get('created_at', 'N/A')}", sub_style))

    status = record.get('status', 'UNKNOWN')
    status_color = colors.green if status == 'PASSED' else colors.red

    table_data = [
        [Paragraph("<b>Service Name:</b>", body_style), Paragraph(str(record.get('service_name', 'N/A')), body_style)],
        [Paragraph("<b>Operation:</b>", body_style), Paragraph(str(record.get('operation_name', 'N/A')), body_style)],
        [Paragraph("<b>Endpoint URL:</b>", body_style), Paragraph(str(record.get('endpoint_url', 'N/A')), body_style)],
        [Paragraph("<b>Test Execution Type:</b>", body_style), Paragraph(str(record.get('test_type', 'N/A')), body_style)],
        [Paragraph("<b>Execution Status:</b>", body_style), Paragraph(f"<b><font color='{status_color}'>{status}</font></b>", body_style)],
        [Paragraph("<b>Response Latency:</b>", body_style), Paragraph(f"{record.get('response_time_ms', 0)} ms", body_style)],
        [Paragraph("<b>HTTP Status Code:</b>", body_style), Paragraph(str(record.get('http_status_code', 'N/A')), body_style)],
        [Paragraph("<b>Summary:</b>", body_style), Paragraph(str(record.get('summary', 'N/A')), body_style)]
    ]

    t = Table(table_data, colWidths=[130, 400])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))

    errors = record.get('validation_errors_list', [])
    if errors:
        elements.append(Paragraph("Validation Diagnostics & Line Mismatches", h2_style))
        err_rows = [[Paragraph("<b>Category</b>", body_style), Paragraph("<b>Diagnostic Message</b>", body_style)]]
        for e in errors:
            if isinstance(e, dict):
                cat = e.get("category", "Error")
                msg = e.get("message", json.dumps(e))
                line_info = f" (Line {e.get('line')})" if e.get('line') else ""
                err_rows.append([Paragraph(f"{cat}{line_info}", body_style), Paragraph(msg, body_style)])
            else:
                err_rows.append([Paragraph("Error", body_style), Paragraph(str(e), body_style)])

        err_table = Table(err_rows, colWidths=[150, 380])
        err_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#FEE2E2')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#FECACA')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(err_table)

    doc.build(elements)
    return destination_path

# ---------------------------------------------------------
# Built-In Live SOAP Web Services (For Offline Local Testing)
# ---------------------------------------------------------
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
</definitions>"""

@app.route("/soap/calculator", methods=["GET", "POST"])
def live_mock_calculator():
    if request.method == "GET":
        if "wsdl" in request.args or request.path.endswith("?wsdl"):
            return Response(CALCULATOR_WSDL, mimetype="text/xml")
        return Response("Calculator SOAP Service Active. Append ?wsdl for contract.", mimetype="text/plain")

    raw_body = request.get_data(as_text=True)
    try:
        root = etree.fromstring(raw_body.encode('utf-8'))
        add_elem = root.find(".//{http://example.com/calculator}Add")
        if add_elem is not None:
            a = add_elem.find("{http://example.com/calculator}intA")
            if a is None: a = add_elem.find("intA")
            b = add_elem.find("{http://example.com/calculator}intB")
            if b is None: b = add_elem.find("intB")

            if a is None or b is None or a.text is None or b.text is None:
                return generate_soap_fault("Client", "Missing required parameters 'intA' or 'intB'."), 400
            try:
                v_a, v_b = int(a.text.strip()), int(b.text.strip())
            except ValueError:
                return generate_soap_fault("Client", "Type mismatch: intA and intB must be valid integers."), 400

            ans = v_a + v_b
            xml_resp = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:AddResponse>
      <tns:AddResult>{ans}</tns:AddResult>
    </tns:AddResponse>
  </soap:Body>
</soap:Envelope>"""
            return Response(xml_resp, mimetype="text/xml")

        div_elem = root.find(".//{http://example.com/calculator}Divide")
        if div_elem is not None:
            a = div_elem.find("{http://example.com/calculator}intA")
            if a is None: a = div_elem.find("intA")
            b = div_elem.find("{http://example.com/calculator}intB")
            if b is None: b = div_elem.find("intB")

            if a is None or b is None or a.text is None or b.text is None:
                return generate_soap_fault("Client", "Missing parameters for Divide operation."), 400
            try:
                v_a, v_b = int(a.text.strip()), int(b.text.strip())
            except ValueError:
                return generate_soap_fault("Client", "Type mismatch: intA and intB must be integers."), 400

            if v_b == 0:
                return generate_soap_fault("Server", "ArithmeticException: Division by zero is not permitted."), 500

            ans = int(v_a / v_b)
            xml_resp = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Body>
    <tns:DivideResponse>
      <tns:DivideResult>{ans}</tns:DivideResult>
    </tns:DivideResponse>
  </soap:Body>
</soap:Envelope>"""
            return Response(xml_resp, mimetype="text/xml")

        return generate_soap_fault("Client", "Operation not recognized by service contract."), 400
    except Exception as e:
        return generate_soap_fault("Client", f"XML Deserialization Error: {str(e)}"), 400

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

# ---------------------------------------------------------
# REST API Endpoints (Fully Connected, Real Processing)
# ---------------------------------------------------------
@app.route("/")
def index_page():
    return render_template("index.html")

# API 1: Parse WSDL
@app.route("/api/v1/wsdl/parse", methods=["POST"])
def api_parse_wsdl():
    try:
        content_bytes = None
        if "file" in request.files:
            file_obj = request.files["file"]
            content_bytes = file_obj.read()
        else:
            json_data = request.get_json(silent=True) or {}
            wsdl_str = json_data.get("wsdl_content", "")
            if wsdl_str:
                content_bytes = wsdl_str.encode("utf-8")

        if not content_bytes or not content_bytes.strip():
            return jsonify({
                "status": "error",
                "error_type": "EMPTY_PAYLOAD",
                "message": "No WSDL content or file was supplied."
            }), 400

        res = parse_wsdl_stream(content_bytes)
        if not res["success"]:
            return jsonify({
                "status": "error",
                "error_type": res.get("error_type", "PARSE_ERROR"),
                "message": res.get("message", "WSDL parsing failed.")
            }), 400

        # Persist service
        db_save_service(res["service_name"], res["target_namespace"], res["default_endpoint"], content_bytes.decode("utf-8", errors="ignore"))
        return jsonify(res), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error_type": "INTERNAL_SERVER_ERROR",
            "message": f"Server encountered an error while parsing WSDL: {str(e)}"
        }), 500

# API 2: Generate SOAP Envelope
@app.route("/api/v1/wsdl/generate-envelope", methods=["POST"])
def api_generate_envelope():
    try:
        data = request.get_json(silent=True) or {}
        target_ns = data.get("target_namespace", "http://tempuri.org/")
        op_name = data.get("operation_name", "Execute")
        soap_ver = data.get("soap_version", "1.1")
        params = data.get("parameters", {})

        if soap_ver not in ("1.1", "1.2"):
            return jsonify({"status": "error", "message": "soap_version must be 1.1 or 1.2."}), 400
        if not isinstance(params, dict) or not isinstance(target_ns, str) or not isinstance(op_name, str):
            return jsonify({"status": "error", "message": "Invalid operation, namespace or parameters."}), 400
        if not op_name or not etree.QName(op_name).localname == op_name:
            return jsonify({"status": "error", "message": "Operation name must be a valid XML local name."}), 400
        envelope_ns = SOAP12_ENV_NS if soap_ver == "1.2" else SOAP_ENV_NS
        envelope_prefix = "soap12" if soap_ver == "1.2" else "soap"
        try:
            root = etree.Element(
                f"{{{envelope_ns}}}Envelope",
                nsmap={envelope_prefix: envelope_ns, "tns": target_ns}
            )
            etree.SubElement(root, f"{{{envelope_ns}}}Header")
            body = etree.SubElement(root, f"{{{envelope_ns}}}Body")
            operation = etree.SubElement(body, f"{{{target_ns}}}{op_name}")
            for name, value in params.items():
                if not isinstance(name, str) or not name or etree.QName(name).localname != name:
                    raise ValueError("Parameter names must be valid XML local names.")
                child = etree.SubElement(operation, f"{{{target_ns}}}{name}")
                child.text = str(value)
            env = etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True).decode("utf-8")
        except (ValueError, TypeError, etree.LxmlError) as exc:
            return jsonify({"status": "error", "message": f"Invalid XML field or namespace: {exc}"}), 400

        return jsonify({
            "status": "success",
            "request_envelope": env
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to generate template: {str(e)}"
        }), 500

# API 3: Validate Contract (XML vs XSD)
@app.route("/api/v1/contract/validate", methods=["POST"])
def api_validate_contract():
    try:
        data = request.get_json(silent=True) or {}
        xml_payload = data.get("xml_payload", "")
        xsd_schema = data.get("xsd_schema", "")
        service_name = data.get("service_name", "Contract Validation Engine")
        operation_name = data.get("operation_name", "Schema Check")

        if not xml_payload.strip() or not xsd_schema.strip():
            return jsonify({
                "status": "error",
                "message": "Both xml_payload and xsd_schema must be supplied."
            }), 400

        res = validate_xml_with_xsd(xml_payload, xsd_schema)
        rec_status = "PASSED" if res["is_valid"] else "FAILED"
        rec_id = db_save_test_record(
            service_name=service_name,
            operation_name=operation_name,
            endpoint_url="Internal XSD Validator",
            test_type="CONTRACT_VALIDATION",
            status=rec_status,
            response_time_ms=0.0,
            http_status_code=200 if res["is_valid"] else 422,
            request_xml=xml_payload,
            response_xml=xsd_schema,
            validation_errors=res.get("errors", []),
            compatibility_assessment="",
            summary=res.get("summary", "")
        )
        res["record_id"] = rec_id
        http_code = 200 if res["is_valid"] else 422
        return jsonify(res), http_code
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error during validation: {str(e)}"
        }), 500

# API 4: Compatibility Diff (V1 vs V2)
@app.route("/api/v1/contract/compatibility", methods=["POST"])
def api_assess_compatibility():
    try:
        data = request.get_json(silent=True) or {}
        v1 = data.get("v1_xsd", "")
        v2 = data.get("v2_xsd", "")
        if not v1.strip() or not v2.strip():
            return jsonify({
                "status": "error",
                "message": "Both v1_xsd and v2_xsd schemas are required."
            }), 400

        res = diff_schema_compatibility(v1, v2)
        if not res["success"]:
            return jsonify({"status": "error", "message": res.get("error")}), 400

        return jsonify(res), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Compatibility analysis failed: {str(e)}"
        }), 500

# API 5: Execute Real SOAP Request
@app.route("/api/v1/soap/execute", methods=["POST"])
def api_execute_soap():
    try:
        data = request.get_json(silent=True) or {}
        endpoint_url = data.get("endpoint_url", "").strip()
        request_xml = data.get("request_xml", "").strip()
        soap_action = data.get("soap_action", "").strip()
        soap_ver = data.get("soap_version", "1.1")
        service_name = data.get("service_name", "SOAP Endpoint")
        operation_name = data.get("operation_name", "Operation")
        try:
            timeout = float(data.get("timeout", 12))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Timeout must be numeric."}), 400
        if not 1 <= timeout <= 30:
            return jsonify({"status": "error", "message": "Timeout must be between 1 and 30 seconds."}), 400

        if not endpoint_url or not request_xml:
            return jsonify({
                "status": "error",
                "message": "Endpoint URL and SOAP Request XML are required."
            }), 400

        endpoint_error = check_soap_endpoint(endpoint_url)
        if endpoint_error:
            return jsonify({"status": "error", "message": endpoint_error}), 400
        res = dispatch_real_soap_request(
            endpoint_url=endpoint_url,
            request_xml=request_xml,
            soap_action=soap_action,
            soap_version=soap_ver,
            timeout=timeout,
            service_name=service_name,
            operation_name=operation_name
        )
        return jsonify(res), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error executing SOAP transmission: {str(e)}"
        }), 500

# API 6: Fetch Audit Logs
@app.route("/api/v1/reports", methods=["GET"])
def api_get_reports():
    records = db_get_test_records(limit=100)
    return jsonify({"status": "success", "records": records}), 200

# Download PDF Report
@app.route("/reports/<int:record_id>/pdf", methods=["GET"])
def download_pdf_audit(record_id):
    rec = db_get_record_by_id(record_id)
    if not rec:
        return "Test record not found", 404

    target_pdf = os.path.join(PDF_DIR, f"Validation_Report_{record_id}.pdf")
    build_pdf_document(rec, target_pdf)
    return send_file(target_pdf, as_attachment=True, download_name=f"Validation_Report_Test_{record_id}.pdf")

# ---------------------------------------------------------
# Launcher Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    print("==========================================================================")
    print(" Integrated Web Service Interoperability and Data Contract Validation")
    print(" Active Server running on http://127.0.0.1:5000")
    print(" Live SOAP Calculator Endpoint: http://127.0.0.1:5000/soap/calculator?wsdl")
    print("==========================================================================")
    app.run(host="127.0.0.1", port=5000, debug=False)
