#!/usr/bin/env python
"""
Launcher script for:
Integrated Web Service Interoperability and Data Contract Validation for Reliable System Communication
Course: CSA4315 – Internet Programming
"""

import sys
from app import app

if __name__ == "__main__":
    print("=" * 80)
    print(" INTEGRATED WEB SERVICE INTEROPERABILITY AND DATA CONTRACT VALIDATION")
    print(" CSA4315 – Internet Programming")
    print("=" * 80)
    print(" Starting Local Server: http://127.0.0.1:5000")
    print(" Built-in Mock SOAP Endpoints:")
    print("   - Calculator Service: http://127.0.0.1:5000/soap/calculator (WSDL: ?wsdl)")
    print("   - Order Service:      http://127.0.0.1:5000/soap/orders     (WSDL: ?wsdl)")
    print(" Press Ctrl+C to terminate.")
    print("=" * 80)
    app.run(host="127.0.0.1", port=5000, debug=False)
