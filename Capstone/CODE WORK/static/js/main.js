// Web Service Interoperability & Contract Validation Platform JavaScript

document.addEventListener("DOMContentLoaded", function () {
  initModule1Handlers();
  initModule2Handlers();
  initModule3Handlers();
});

// ==========================================
// MODULE 1: Service Configuration & Integration
// ==========================================
function initModule1Handlers() {
  const btnParseWsdl = document.getElementById("btn-parse-wsdl");
  const wsdlPresetSelect = document.getElementById("wsdl-preset-select");
  const wsdlTextarea = document.getElementById("wsdl-content");
  const btnGenerateTemplate = document.getElementById("btn-generate-template");

  if (wsdlPresetSelect && wsdlTextarea) {
    wsdlPresetSelect.addEventListener("change", function () {
      const preset = this.value;
      if (!preset) return;

      fetch("/api/parse-wsdl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset: preset })
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          // If preset is selected, fetch raw content or display
          renderWsdlDetails(data);
        }
      })
      .catch(err => console.error("Error loading preset:", err));
    });
  }

  if (btnParseWsdl && wsdlTextarea) {
    btnParseWsdl.addEventListener("click", function () {
      const content = wsdlTextarea.value.trim();
      if (!content) {
        alert("Please paste WSDL XML content or select a preset.");
        return;
      }
      btnParseWsdl.innerHTML = '<span class="loading-spinner"></span> Parsing WSDL...';
      btnParseWsdl.disabled = true;

      fetch("/api/parse-wsdl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wsdl_content: content })
      })
      .then(res => res.json())
      .then(data => {
        btnParseWsdl.innerHTML = '<i class="bi bi-cpu me-1"></i> Parse & Discover Operations';
        btnParseWsdl.disabled = false;
        renderWsdlDetails(data);
      })
      .catch(err => {
        btnParseWsdl.innerHTML = '<i class="bi bi-cpu me-1"></i> Parse & Discover Operations';
        btnParseWsdl.disabled = false;
        alert("Error connecting to server: " + err);
      });
    });
  }

  if (btnGenerateTemplate) {
    btnGenerateTemplate.addEventListener("click", function () {
      const opSelect = document.getElementById("discovered-operations");
      const targetNs = document.getElementById("target-namespace-val") ? document.getElementById("target-namespace-val").innerText : "http://example.com/calculator";
      const opName = opSelect ? opSelect.value : "Add";
      const soapVer = document.querySelector('input[name="soapVersion"]:checked') ? document.querySelector('input[name="soapVersion"]:checked').value : "1.1";

      fetch("/api/generate-request-template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_namespace: targetNs,
          operation_name: opName,
          soap_version: soapVer,
          parameters: opName === "Divide" ? { "intA": "100", "intB": "5" } : { "intA": "40", "intB": "60" }
        })
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          const reqArea = document.getElementById("generated-soap-envelope");
          if (reqArea) reqArea.value = data.request_envelope;
        }
      });
    });
  }
}

function renderWsdlDetails(data) {
  const resultsCard = document.getElementById("wsdl-discovery-results");
  if (!resultsCard) return;

  if (!data.success) {
    resultsCard.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i> ${data.error}</div>`;
    resultsCard.classList.remove("d-none");
    return;
  }

  let opsHtml = "";
  if (data.operations && data.operations.length > 0) {
    opsHtml = `<div class="mb-3">
      <label class="form-label fw-semibold">Discovered Operations:</label>
      <select id="discovered-operations" class="form-select">
        ${data.operations.map(op => `<option value="${op.operation_name}">${op.operation_name} (PortType: ${op.port_type})</option>`).join("")}
      </select>
    </div>`;
  } else {
    opsHtml = `<div class="alert alert-warning">No operations found in WSDL portType.</div>`;
  }

  let servicesHtml = "";
  if (data.services && data.services.length > 0) {
    servicesHtml = data.services.map(s => `
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <div>
          <strong>${s.service_name}</strong>
          <div class="small text-muted">Endpoint: <code>${s.ports[0]?.endpoint_url || 'N/A'}</code></div>
        </div>
        <span class="badge bg-primary rounded-pill">${s.ports.length} Port(s)</span>
      </li>
    `).join("");
  }

  resultsCard.innerHTML = `
    <div class="alert alert-success d-flex align-items-center mb-3">
      <i class="bi bi-check-circle-fill me-2 fs-5"></i>
      <div>WSDL Successfully Parsed! Service & Schema definitions discovered.</div>
    </div>
    <div class="row g-3 mb-3">
      <div class="col-md-6">
        <div class="card p-3 bg-light">
          <div class="text-muted small">Target Namespace:</div>
          <code id="target-namespace-val" class="fw-bold">${data.target_namespace}</code>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card p-3 bg-light">
          <div class="text-muted small">Default Endpoint:</div>
          <code class="fw-bold text-truncate">${data.default_endpoint || 'None'}</code>
        </div>
      </div>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Configured Services:</label>
      <ul class="list-group">${servicesHtml}</ul>
    </div>
    ${opsHtml}
  `;
  resultsCard.classList.remove("d-none");
}

// ==========================================
// MODULE 2: Contract Validation & Compatibility
// ==========================================
function initModule2Handlers() {
  const btnValidate = document.getElementById("btn-validate-contract");
  const xmlArea = document.getElementById("contract-xml-input");
  const xsdArea = document.getElementById("contract-xsd-input");
  const sampleSelect = document.getElementById("validation-sample-select");
  const btnAssessCompat = document.getElementById("btn-assess-compatibility");

  if (sampleSelect && xmlArea && xsdArea) {
    sampleSelect.addEventListener("change", function () {
      const choice = this.value;
      if (!choice) return;

      // Always load the calculator schema
      fetch("/api/sample-data/calculator_schema")
      .then(r => r.json())
      .then(d => { if (d.success) xsdArea.value = d.content; });

      let xmlFile = "valid_xml";
      if (choice === "invalid_type") xmlFile = "invalid_type_xml";
      if (choice === "missing_field") xmlFile = "missing_field_xml";

      fetch(`/api/sample-data/${xmlFile}`)
      .then(r => r.json())
      .then(d => { if (d.success) xmlArea.value = d.content; });
    });
  }

  if (btnValidate && xmlArea && xsdArea) {
    btnValidate.addEventListener("click", function () {
      const xml = xmlArea.value.trim();
      const xsd = xsdArea.value.trim();

      if (!xml || !xsd) {
        alert("Please provide both an XML instance and an XSD schema.");
        return;
      }

      btnValidate.innerHTML = '<span class="loading-spinner"></span> Validating Contract...';
      btnValidate.disabled = true;

      fetch("/api/validate-contract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          xml_content: xml,
          xsd_content: xsd,
          service_name: "Module 2 Contract Engine",
          operation_name: "XSD Contract Check"
        })
      })
      .then(res => res.json())
      .then(data => {
        btnValidate.innerHTML = '<i class="bi bi-shield-check me-1"></i> Run Contract Validation';
        btnValidate.disabled = false;
        renderValidationResults(data);
      })
      .catch(err => {
        btnValidate.innerHTML = '<i class="bi bi-shield-check me-1"></i> Run Contract Validation';
        btnValidate.disabled = false;
        alert("Validation error: " + err);
      });
    });
  }

  // Compatibility assessment
  if (btnAssessCompat) {
    btnAssessCompat.addEventListener("click", function () {
      const v1 = document.getElementById("compat-v1-xsd").value.trim();
      const v2 = document.getElementById("compat-v2-xsd").value.trim();

      if (!v1 || !v2) {
        alert("Please supply both Schema V1 and Schema V2.");
        return;
      }

      btnAssessCompat.innerHTML = '<span class="loading-spinner"></span> Analyzing Changes...';
      btnAssessCompat.disabled = true;

      fetch("/api/assess-compatibility", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ v1_xsd: v1, v2_xsd: v2 })
      })
      .then(res => res.json())
      .then(data => {
        btnAssessCompat.innerHTML = '<i class="bi bi-shuffle me-1"></i> Compare Schemas & Assess Compatibility';
        btnAssessCompat.disabled = false;
        renderCompatibilityResults(data);
      })
      .catch(err => {
        btnAssessCompat.innerHTML = '<i class="bi bi-shuffle me-1"></i> Compare Schemas & Assess Compatibility';
        btnAssessCompat.disabled = false;
        alert("Error: " + err);
      });
    });
  }
}

function renderValidationResults(data) {
  const container = document.getElementById("validation-results-card");
  if (!container) return;

  if (data.valid) {
    container.innerHTML = `
      <div class="alert alert-success d-flex align-items-center">
        <i class="bi bi-check-circle-fill fs-3 me-3"></i>
        <div>
          <h5 class="alert-heading mb-1 fw-bold">Data Contract Validation PASSED</h5>
          <p class="mb-0">${data.summary}</p>
        </div>
      </div>
      <div class="card p-3 bg-light">
        <div class="text-success fw-bold"><i class="bi bi-patch-check-fill me-1"></i> Conformance Details:</div>
        <ul class="mb-0 mt-2 small text-muted">
          <li>XML Structure: Well-formed and syntax valid.</li>
          <li>Namespace & Elements: Matched XSD definition.</li>
          <li>Data Types: All element data types verified against schema definitions.</li>
          <li>Multiplicity Constraints: Required occurrences satisfied.</li>
        </ul>
      </div>
    `;
  } else {
    let errListHtml = "";
    if (data.errors && data.errors.length > 0) {
      errListHtml = data.errors.map(err => `
        <li class="list-group-item list-group-item-danger d-flex justify-content-between align-items-start">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${err.category || 'Schema Error'} ${err.line ? `(Line ${err.line})` : ''}</div>
            <div class="small">${err.message}</div>
          </div>
          <span class="badge bg-danger rounded-pill">Violation</span>
        </li>
      `).join("");
    }

    container.innerHTML = `
      <div class="alert alert-danger d-flex align-items-center">
        <i class="bi bi-x-octagon-fill fs-3 me-3"></i>
        <div>
          <h5 class="alert-heading mb-1 fw-bold">Data Contract Violation Detected</h5>
          <p class="mb-0">${data.summary}</p>
        </div>
      </div>
      <div class="card">
        <div class="card-header bg-danger-subtle text-danger fw-semibold">
          <i class="bi bi-bug-fill me-1"></i> Error Diagnostics & Line Mismatches:
        </div>
        <ul class="list-group list-group-flush">${errListHtml}</ul>
      </div>
    `;
  }
  container.classList.remove("d-none");
}

function renderCompatibilityResults(data) {
  const container = document.getElementById("compatibility-results-card");
  if (!container) return;

  if (!data.success) {
    container.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
    container.classList.remove("d-none");
    return;
  }

  const isCompat = data.is_compatible;
  const alertClass = isCompat ? "alert-success" : "alert-warning";
  const icon = isCompat ? "bi-check-circle-fill" : "bi-exclamation-triangle-fill";

  let breakingList = "";
  if (data.breaking_changes && data.breaking_changes.length > 0) {
    breakingList = `
      <div class="mt-3">
        <h6 class="text-danger fw-bold"><i class="bi bi-x-circle-fill me-1"></i> Breaking Changes Detected:</h6>
        <ul class="list-group">
          ${data.breaking_changes.map(b => `<li class="list-group-item list-group-item-danger small">${b}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  let nonBreakingList = "";
  if (data.non_breaking_changes && data.non_breaking_changes.length > 0) {
    nonBreakingList = `
      <div class="mt-3">
        <h6 class="text-success fw-bold"><i class="bi bi-check-circle-fill me-1"></i> Non-Breaking / Backward-Compatible Changes:</h6>
        <ul class="list-group">
          ${data.non_breaking_changes.map(nb => `<li class="list-group-item list-group-item-success small">${nb}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="alert ${alertClass} d-flex align-items-center">
      <i class="bi ${icon} fs-3 me-3"></i>
      <div>
        <h5 class="alert-heading mb-1 fw-bold">Compatibility Status: ${data.compatibility_status}</h5>
        <div class="small">V1 Elements: <b>${data.v1_element_count}</b> | V2 Elements: <b>${data.v2_element_count}</b></div>
      </div>
    </div>
    ${breakingList}
    ${nonBreakingList}
  `;
  container.classList.remove("d-none");
}

// ==========================================
// MODULE 3: Communication Monitoring & Test Execution
// ==========================================
function initModule3Handlers() {
  const btnSendSoap = document.getElementById("btn-send-soap");
  const endpointInput = document.getElementById("soap-endpoint-url");
  const requestXmlArea = document.getElementById("soap-request-xml");
  const presetSelect = document.getElementById("soap-scenario-select");

  if (presetSelect && endpointInput && requestXmlArea) {
    presetSelect.addEventListener("change", function () {
      const choice = this.value;
      if (choice === "calc_add_valid") {
        endpointInput.value = "http://127.0.0.1:5000/soap/calculator";
        document.getElementById("soap-action-header").value = "http://example.com/calculator/Add";
        requestXmlArea.value = `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Header/>
  <soap:Body>
    <tns:Add>
      <tns:intA>125</tns:intA>
      <tns:intB>375</tns:intB>
    </tns:Add>
  </soap:Body>
</soap:Envelope>`;
      } else if (choice === "calc_div_zero") {
        endpointInput.value = "http://127.0.0.1:5000/soap/calculator";
        document.getElementById("soap-action-header").value = "http://example.com/calculator/Divide";
        requestXmlArea.value = `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/calculator">
  <soap:Header/>
  <soap:Body>
    <tns:Divide>
      <tns:intA>50</tns:intA>
      <tns:intB>0</tns:intB>
    </tns:Divide>
  </soap:Body>
</soap:Envelope>`;
      } else if (choice === "order_create_valid") {
        endpointInput.value = "http://127.0.0.1:5000/soap/orders";
        document.getElementById("soap-action-header").value = "http://example.com/orders/CreateOrder";
        requestXmlArea.value = `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://example.com/orders">
  <soap:Header/>
  <soap:Body>
    <tns:CreateOrder>
      <tns:customerId>CUST-9921</tns:customerId>
      <tns:itemCode>PROD-884</tns:itemCode>
      <tns:quantity>5</tns:quantity>
      <tns:pricePerUnit>49.99</tns:pricePerUnit>
    </tns:CreateOrder>
  </soap:Body>
</soap:Envelope>`;
      }
    });
  }

  if (btnSendSoap && endpointInput && requestXmlArea) {
    btnSendSoap.addEventListener("click", function () {
      const url = endpointInput.value.trim();
      const xml = requestXmlArea.value.trim();
      const action = document.getElementById("soap-action-header").value.trim();

      if (!url || !xml) {
        alert("Please specify the Endpoint URL and SOAP Request XML.");
        return;
      }

      btnSendSoap.innerHTML = '<span class="loading-spinner"></span> Transmitting SOAP Request...';
      btnSendSoap.disabled = true;

      fetch("/api/execute-soap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_url: url,
          request_xml: xml,
          soap_action: action,
          service_name: url.includes("calculator") ? "Calculator Service" : "Order Service",
          operation_name: action ? action.split("/").pop() : "SOAPRequest"
        })
      })
      .then(res => res.json())
      .then(data => {
        btnSendSoap.innerHTML = '<i class="bi bi-send-fill me-1"></i> Send SOAP Request & Monitor';
        btnSendSoap.disabled = false;
        renderSoapResponse(data);
      })
      .catch(err => {
        btnSendSoap.innerHTML = '<i class="bi bi-send-fill me-1"></i> Send SOAP Request & Monitor';
        btnSendSoap.disabled = false;
        alert("Communication Error: " + err);
      });
    });
  }
}

function renderSoapResponse(data) {
  const container = document.getElementById("soap-response-container");
  if (!container) return;

  const isSuccess = data.status === "PASSED";
  const badgeClass = isSuccess ? "bg-success" : "bg-danger";
  const statusIcon = isSuccess ? "bi-check-circle-fill" : "bi-x-circle-fill";

  container.innerHTML = `
    <div class="card shadow-sm border-top border-4 ${isSuccess ? 'border-success' : 'border-danger'}">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <div class="d-flex align-items-center">
          <i class="bi ${statusIcon} fs-4 ${isSuccess ? 'text-success' : 'text-danger'} me-2"></i>
          <div>
            <span class="badge ${badgeClass} me-2">${data.status}</span>
            <span class="fw-semibold text-secondary">HTTP ${data.http_status_code}</span>
          </div>
        </div>
        <div>
          <span class="badge bg-secondary me-2"><i class="bi bi-stopwatch me-1"></i> Latency: ${data.latency_ms} ms</span>
          ${data.record_id ? `<a href="/reports/${data.record_id}/pdf" class="btn btn-sm btn-outline-danger"><i class="bi bi-file-earmark-pdf-fill me-1"></i> Download PDF Report</a>` : ''}
        </div>
      </div>
      <div class="card-body">
        <div class="alert ${isSuccess ? 'alert-success' : 'alert-danger'} py-2 mb-3">
          <strong>Summary:</strong> ${data.summary}
        </div>
        ${data.soap_fault_detected ? `
          <div class="alert alert-warning py-2 mb-3">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            <strong>SOAP Fault Received:</strong> [${data.fault_code}] ${data.fault_string}
          </div>
        ` : ''}
        <label class="form-label fw-semibold text-muted small">Raw Response SOAP XML:</label>
        <pre class="xml-view"><code>${escapeHtml(data.response_xml || '(No response received)')}</code></pre>
      </div>
    </div>
  `;
  container.classList.remove("d-none");
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
