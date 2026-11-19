import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "test_history.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Table for Services / WSDL configurations (Module 1)
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
    
    # Table for Validation and Communication Test Records (Modules 2 & 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            operation_name TEXT NOT NULL,
            endpoint_url TEXT NOT NULL,
            test_type TEXT NOT NULL,          -- 'CONTRACT_VALIDATION', 'SOAP_COMMUNICATION', 'COMPATIBILITY_CHECK'
            status TEXT NOT NULL,             -- 'PASSED', 'FAILED', 'WARNING'
            response_time_ms REAL,
            http_status_code INTEGER,
            request_xml TEXT,
            response_xml TEXT,
            validation_errors TEXT,          -- JSON list of error details
            compatibility_assessment TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def save_service(service_name, target_namespace, endpoint_url, wsdl_content):
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

def get_services():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM configured_services ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_test_record(service_name, operation_name, endpoint_url, test_type, status,
                     response_time_ms, http_status_code, request_xml, response_xml,
                     validation_errors, compatibility_assessment, summary):
    conn = get_db()
    cursor = conn.cursor()
    if isinstance(validation_errors, (list, dict)):
        validation_errors_str = json.dumps(validation_errors)
    else:
        validation_errors_str = str(validation_errors or "")

    cursor.execute("""
        INSERT INTO test_records (
            service_name, operation_name, endpoint_url, test_type, status,
            response_time_ms, http_status_code, request_xml, response_xml,
            validation_errors, compatibility_assessment, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        service_name, operation_name, endpoint_url, test_type, status,
        response_time_ms, http_status_code, request_xml, response_xml,
        validation_errors_str, compatibility_assessment, summary
    ))
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id

def get_test_records(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test_records ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        try:
            r['validation_errors_list'] = json.loads(r['validation_errors']) if r['validation_errors'] else []
        except Exception:
            r['validation_errors_list'] = [r['validation_errors']] if r['validation_errors'] else []
        results.append(r)
    return results

def get_test_record_by_id(record_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    try:
        r['validation_errors_list'] = json.loads(r['validation_errors']) if r['validation_errors'] else []
    except Exception:
        r['validation_errors_list'] = [r['validation_errors']] if r['validation_errors'] else []
    return r

def get_dashboard_metrics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM test_records")
    total_tests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM test_records WHERE status = 'PASSED'")
    passed_tests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM test_records WHERE status = 'FAILED'")
    failed_tests = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(response_time_ms) FROM test_records WHERE response_time_ms IS NOT NULL")
    avg_latency = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT COUNT(*) FROM configured_services")
    configured_services_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "avg_latency": round(avg_latency, 2),
        "configured_services": configured_services_count
    }
