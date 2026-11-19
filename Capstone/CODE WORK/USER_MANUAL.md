# User Manual & Operating Guide
## Integrated Web Service Interoperability and Data Contract Validation for Reliable System Communication
**Course:** CSA4315 – Internet Programming | **Batch:** 09

---

## 1. What This Platform Does (Executive Summary)

In distributed enterprise software, applications communicate across different systems using web services and protocols like SOAP, WSDL, and XML. Communication failures frequently occur due to:
- Missing mandatory XML elements.
- Data type mismatches (e.g., passing text where an integer is expected).
- Incompatible XML Schemas between a service consumer and provider.
- Network and service-level SOAP Faults.

**This platform is an automated, full-stack web service testing and contract verification system that:**
1. **Parses & Discovers Services (Module 1):** Reads WSDL definitions, extracts service endpoints and operations, and generates conforming SOAP XML request envelopes.
2. **Validates Data Contracts (Module 2):** Checks XML documents against XSD schemas, isolates syntax errors with line/column numbers, verifies data types, and compares Schema V1 against V2 to detect breaking changes.
3. **Monitors Live Communication (Module 3):** Dispatches live SOAP HTTP requests, measures latency in milliseconds, inspects HTTP response codes, catches SOAP Faults (`<faultcode>`, `<faultstring>`), and logs every execution in a centralized SQLite database.
4. **Generates Official Audit Reports:** Produces searchable web test logs and downloadable, publication-ready PDF reports with ReportLab.

---

## 2. Quick Start: Launching the Platform

1. Go to your **Desktop** and double-click:
   ```
   Start_Capstone_Project.bat
   ```
2. The script will automatically launch your browser and open:
   ```
   http://127.0.0.1:5000
   ```
3. To stop the server at any time, go to the black command terminal and press `Ctrl + C`.

---

## 3. Step-by-Step Module Guide

### **Module 1: Web Service Configuration and Integration**
*Purpose:* Import service specifications and prepare compliant SOAP requests.

- **Step 1:** Click on **Module 1: Service Configuration** in the top navigation bar.
- **Step 2:** Under the *WSDL Service Definition* box, click the dropdown **"-- Load Sample WSDL --"** and pick:
  - `Calculator Service (Local Mock)` or `Order Service (Local Mock)`.
  - Alternatively, paste any custom external WSDL XML.
- **Step 3:** Click **"Parse & Discover Operations"**.
  - The system displays the target namespace, active service endpoints, and discovered operations (e.g., `Add`, `Divide`).
- **Step 4:** In the right-hand panel, select the SOAP version (`SOAP 1.1` or `SOAP 1.2`) and click **"Auto-Generate SOAP Request Envelope"**.
  - A formatted, syntactically valid SOAP XML request envelope is generated with appropriate namespaces and placeholder arguments.
- **Step 5:** Click **"Proceed to Module 2"** or **"Proceed to Module 3"**.

---

### **Module 2: Data Contract Validation and Compatibility Testing**
*Purpose:* Verify whether XML documents comply strictly with the XSD schema and assess contract evolutions.

#### **Part A: XML Schema & Data Type Validation**
- **Step 1:** Navigate to **Module 2: Contract Validation** -> Click the **"Part A: XML Schema & Data Type Validation"** tab.
- **Step 2:** From the dropdown **"-- Load Sample Test Case --"**, select one of three scenarios:
  1. **Valid Request (Conforming):** Valid XML matching the XSD.
  2. **Invalid Data Type Error:** Passes string text `"NOT_A_NUMBER"` into an integer element (`intA`).
  3. **Missing Required Field Error:** Omits the required `<intB>` tag (`minOccurs=1`).
- **Step 3:** Click **"Run Contract Validation"**.
  - **If Valid:** Displays a green **PASSED** badge and confirms that data types and occurrences comply with the schema.
  - **If Invalid:** Displays a red **Data Contract Violation** banner with exact line numbers, violation categories, and the schema rule that failed.

#### **Part B: Contract Compatibility Assessment (V1 vs V2 Diff)**
- **Step 1:** Click the **"Part B: Schema Compatibility Assessment"** tab.
- **Step 2:** Click **"Load Sample V1"** to populate the base consumer schema.
- **Step 3:** Click either:
  - **"Load Breaking V2"**: Introduces breaking changes (removes the `email` element and adds a mandatory `age` element without a default).
  - **"Load Compatible V2"**: Adds an optional `loyaltyTier` element (`minOccurs=0`).
- **Step 4:** Click **"Compare Schemas & Assess Compatibility"**.
  - The system analyzes element additions, deletions, type alterations, and constraint tightens, reporting whether the update is **COMPATIBLE** or **INCOMPATIBLE (BREAKING CHANGES)**.

---

### **Module 3: Communication Monitoring & Validation Report Generation**
*Purpose:* Transmit live SOAP requests over HTTP, inspect roundtrip latency, capture SOAP Faults, and log results.

- **Step 1:** Click on **Module 3: Communication Monitoring** in the navigation bar.
- **Step 2:** Select a scenario from **"-- Quick Load Scenarios --"**:
  - `Calculator Add: Valid (45 + 55)` &rarr; Targets `http://127.0.0.1:5000/soap/calculator`.
  - `Calculator Divide: Zero Division` &rarr; Sends a divisor of `0` to test SOAP Fault handling.
  - `Order Service: Create Order` &rarr; Submits a dynamic order request to `/soap/orders`.
- **Step 3:** Click **"Send SOAP Request & Monitor"**.
- **Step 4:** Observe real-time results in the response card:
  - **Overall Status:** `PASSED` (green) or `FAILED` (red).
  - **HTTP Status Code:** e.g., `200 OK` or `500 Internal Server Error`.
  - **Latency:** Exact roundtrip execution time measured in milliseconds (ms).
  - **Raw SOAP Response XML:** Syntax-highlighted response envelope.
  - **SOAP Fault Inspection:** If an error occurs (such as division by zero), parses `<faultcode>` and `<faultstring>`.
- **Step 5:** Click **"Download PDF Report"** to instantly generate an official, formatted test report.

---

### **Reports & Audit History**
- Click on **Reports & Logs** in the top navigation.
- View the complete log of every executed test (Test ID, Service Name, Operation, Latency, HTTP Code, Status).
- Filter tests by **All**, **Passed**, or **Failed**.
- Click **"Details"** on any record to view its full request and response envelopes.
- Click **"PDF"** to download an archived PDF report at any time.

---

## 4. Built-in Mock SOAP Web Services Reference

The platform includes two live SOAP services that run automatically with the application:

| Service Name | Endpoint URL | WSDL Contract URL | Operations |
| :--- | :--- | :--- | :--- |
| **Calculator Service** | `http://127.0.0.1:5000/soap/calculator` | `http://127.0.0.1:5000/soap/calculator?wsdl` | `Add`, `Divide` |
| **Order Service** | `http://127.0.0.1:5000/soap/orders` | `http://127.0.0.1:5000/soap/orders?wsdl` | `CreateOrder` |

---

## 5. Automated Verification

To run the automated test suite from the command line:
```powershell
python test_platform.py
```
This runs 5 comprehensive unit tests covering WSDL parsing, XSD validation, type checking, schema compatibility diffing, and mock SOAP communication.
