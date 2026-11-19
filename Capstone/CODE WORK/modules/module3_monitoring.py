import requests
import time
from lxml import etree
import json
import os
from database import save_test_record
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

SOAP_FAULT_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP12_FAULT_NS = "http://www.w3.org/2003/05/soap-envelope"

def execute_soap_request(endpoint_url, request_xml, soap_action="", timeout=10, service_name="Web Service", operation_name="Operation"):
    """
    Module 3 - Communication Monitoring & Test Execution
    Sends live SOAP request, tracks response time, verifies response structure, and logs outcome.
    """
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
    }
    if soap_action:
        headers["SOAPAction"] = f'"{soap_action}"'

    start_time = time.time()
    try:
        response = requests.post(
            endpoint_url,
            data=request_xml.encode('utf-8'),
            headers=headers,
            timeout=timeout
        )
        latency_ms = round((time.time() - start_time) * 1000, 2)
        status_code = response.status_code
        response_text = response.text
    except requests.exceptions.RequestException as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        error_msg = f"Network/Connection error during SOAP request: {str(e)}"
        
        record_id = save_test_record(
            service_name=service_name,
            operation_name=operation_name,
            endpoint_url=endpoint_url,
            test_type="SOAP_COMMUNICATION",
            status="FAILED",
            response_time_ms=latency_ms,
            http_status_code=0,
            request_xml=request_xml,
            response_xml="",
            validation_errors=[{"category": "Communication Failure", "message": error_msg}],
            compatibility_assessment="",
            summary="SOAP communication failed due to connection error."
        )
        return {
            "success": False,
            "status": "FAILED",
            "record_id": record_id,
            "latency_ms": latency_ms,
            "http_status_code": 0,
            "error": error_msg,
            "response_xml": ""
        }

    # Verify Response XML and check for SOAP Fault
    soap_fault_detected = False
    fault_code = ""
    fault_string = ""
    is_valid_xml = False
    validation_errors = []

    try:
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(response_text.encode('utf-8'), parser)
        is_valid_xml = True

        # Check for SOAP 1.1 Fault
        fault_node = root.find(f".//{{{SOAP_FAULT_NS}}}Fault")
        if fault_node is None:
            fault_node = root.find(f".//{{{SOAP12_FAULT_NS}}}Fault")

        if fault_node is not None:
            soap_fault_detected = True
            fc = fault_node.find("faultcode") or fault_node.find(f"{{{SOAP12_FAULT_NS}}}Code")
            fs = fault_node.find("faultstring") or fault_node.find(f"{{{SOAP12_FAULT_NS}}}Reason")
            fault_code = fc.text if fc is not None else "UnknownFaultCode"
            fault_string = fs.text if fs is not None else "SOAP Fault occurred"
            validation_errors.append({
                "category": "SOAP Fault Received",
                "code": fault_code,
                "message": fault_string
            })
    except Exception as e:
        validation_errors.append({
            "category": "Malformed Response XML",
            "message": f"Response could not be parsed as XML: {str(e)}"
        })

    # Decide test status
    if status_code == 200 and not soap_fault_detected and is_valid_xml:
        overall_status = "PASSED"
        summary = f"SOAP communication succeeded with HTTP 200 OK in {latency_ms} ms."
    elif soap_fault_detected:
        overall_status = "FAILED"
        summary = f"SOAP Fault encountered: [{fault_code}] {fault_string}"
    else:
        overall_status = "FAILED"
        summary = f"HTTP error {status_code} returned by service."

    record_id = save_test_record(
        service_name=service_name,
        operation_name=operation_name,
        endpoint_url=endpoint_url,
        test_type="SOAP_COMMUNICATION",
        status=overall_status,
        response_time_ms=latency_ms,
        http_status_code=status_code,
        request_xml=request_xml,
        response_xml=response_text,
        validation_errors=validation_errors,
        compatibility_assessment="",
        summary=summary
    )

    return {
        "success": overall_status == "PASSED",
        "status": overall_status,
        "record_id": record_id,
        "latency_ms": latency_ms,
        "http_status_code": status_code,
        "soap_fault_detected": soap_fault_detected,
        "fault_code": fault_code,
        "fault_string": fault_string,
        "summary": summary,
        "response_xml": response_text,
        "validation_errors": validation_errors
    }

def generate_pdf_report(record, output_filepath):
    """
    Generates a professional PDF test summary report using ReportLab.
    """
    doc = SimpleDocTemplate(output_filepath, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=12
    )
    
    sub_style = ParagraphStyle(
        'SubStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=9,
        leading=13
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        backColor=colors.HexColor('#F8FAFC')
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("Web Service Interoperability & Contract Validation Report", title_style))
    elements.append(Paragraph(f"Generated on: {record.get('created_at', 'N/A')} | Test ID: #{record.get('id', 'N/A')}", sub_style))
    elements.append(Spacer(1, 10))

    # Summary Table
    status = record.get('status', 'UNKNOWN')
    status_color = colors.green if status == 'PASSED' else colors.red

    table_data = [
        [Paragraph("<b>Service Name:</b>", body_style), Paragraph(str(record.get('service_name', 'N/A')), body_style)],
        [Paragraph("<b>Operation:</b>", body_style), Paragraph(str(record.get('operation_name', 'N/A')), body_style)],
        [Paragraph("<b>Endpoint URL:</b>", body_style), Paragraph(str(record.get('endpoint_url', 'N/A')), body_style)],
        [Paragraph("<b>Test Type:</b>", body_style), Paragraph(str(record.get('test_type', 'N/A')), body_style)],
        [Paragraph("<b>Overall Status:</b>", body_style), Paragraph(f"<b><font color='{status_color}'>{status}</font></b>", body_style)],
        [Paragraph("<b>Response Time:</b>", body_style), Paragraph(f"{record.get('response_time_ms', 0)} ms", body_style)],
        [Paragraph("<b>HTTP Status Code:</b>", body_style), Paragraph(str(record.get('http_status_code', 'N/A')), body_style)],
        [Paragraph("<b>Summary:</b>", body_style), Paragraph(str(record.get('summary', 'N/A')), body_style)]
    ]

    t = Table(table_data, colWidths=[130, 400])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # Error Details Section
    errors = record.get('validation_errors_list', [])
    if errors:
        elements.append(Paragraph("Validation & Error Details", h2_style))
        err_rows = [[Paragraph("<b>Category</b>", body_style), Paragraph("<b>Details</b>", body_style)]]
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
        elements.append(Spacer(1, 15))

    doc.build(elements)
    return output_filepath
