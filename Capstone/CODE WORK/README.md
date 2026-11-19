# Integrated Web Service Interoperability and Data Contract Validation for Reliable System Communication

**Course:** CSA4315 – Internet Programming  
**Batch:** 09  

An enterprise-grade, fully functional full-stack platform designed to eliminate web service communication failures through dynamic WSDL inspection, strict XML Schema (XSD) contract validation, and live SOAP communication monitoring.

---

## 1. Project Modules

### **Module 1 — Web Service Configuration and Integration**
- **Real Dynamic WSDL Parsing:** Parses WSDL 1.1 / 2.0 definitions using C-level `libxml2` (`lxml.etree`).
- **Dynamic Service Discovery:** Extracts `<wsdl:service>`, `<wsdl:port>`, endpoint `<soap:address>`, target namespaces, and `<wsdl:operation>` sets.
- **Contract Parameter Extraction:** Reads embedded schemas inside `<wsdl:types>` and extracts child elements and types.
- **Conforming Request Generation:** Auto-generates valid SOAP 1.1 and SOAP 1.2 XML request envelopes with namespace mappings and placeholder/custom parameters.

### **Module 2 — Data Contract Validation and Compatibility Testing**
- **Strict XML Schema Validation:** Validates XML documents directly against XSD contracts via `lxml.etree.XMLSchema`.
- **Diagnostic Error Reporting:** Catches and maps syntax errors, missing mandatory fields (`minOccurs >= 1`), undeclared elements, and data type violations with line and column numbers.
- **Contract Compatibility Diff (V1 vs V2):** Analyzes contract evolutions between a Consumer schema (V1) and Provider schema (V2) to flag **breaking changes** (removed fields, tightened constraints, altered data types) versus **backward-compatible changes**.

### **Module 3 — Communication Monitoring and Validation Report Generation**
- **Live SOAP Dispatcher:** Sends real HTTP POST requests with appropriate `Content-Type` and `SOAPAction` headers using `requests`.
- **Latency & Fault Monitoring:** Measures real network roundtrip time in milliseconds, inspects HTTP status codes (200, 400, 500), and parses SOAP Fault envelopes (`<faultcode>`, `<faultstring>`).
- **Centralized Database Audit Trail:** Records all test history into an SQLite database (`test_history.db`).
- **Official PDF Report Generation:** Produces publication-ready PDF audit reports via `ReportLab`.

---

## 2. Prerequisites & Installation

Ensure Python 3.10+ is installed on your system.

Install all required production dependencies:
```bash
pip install -r requirements.txt
```

---

## 3. How to Run the Platform Locally

1. **Start the Flask Full-Stack Server:**
   ```bash
   python app.py
   ```
   *(Alternatively, double-click `Start_Capstone_Project.bat` on your Desktop).*

2. **Open the Web Application:**
   Open any modern web browser and navigate to:
   ```text
   http://127.0.0.1:5000
   ```

3. **Built-in Live Local SOAP Endpoints (Ready to Test Out-of-the-Box):**
   - **Calculator Service:** `http://127.0.0.1:5000/soap/calculator` (WSDL: `http://127.0.0.1:5000/soap/calculator?wsdl`)
   - Supports operations `Add` and `Divide` (including live SOAP Fault generation on division by zero).

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/wsdl/parse` | Parses WSDL file or XML text, returns operations, endpoints, and types. |
| `POST` | `/api/v1/wsdl/generate-envelope` | Generates a valid SOAP 1.1 or 1.2 request envelope for an operation. |
| `POST` | `/api/v1/contract/validate` | Validates an XML document against an XSD schema using `lxml.etree.XMLSchema`. |
| `POST` | `/api/v1/contract/compatibility` | Compares Schema V1 vs V2, identifies breaking and non-breaking changes. |
| `POST` | `/api/v1/soap/execute` | Dispatches a live SOAP request over HTTP, records latency, catches faults. |
| `GET` | `/api/v1/reports` | Retrieves recent test execution history from the SQLite database. |
| `GET` | `/reports/<id>/pdf` | Generates and downloads a formatted PDF audit report for a test record. |
