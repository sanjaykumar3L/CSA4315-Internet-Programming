from lxml import etree
import io

XSD_NS = "http://www.w3.org/2001/XMLSchema"

def validate_xml_well_formedness(xml_content):
    """
    Step 1: Check if the XML document is syntactically well-formed.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=False)
        etree.fromstring(xml_content.encode('utf-8'), parser)
        return {"valid": True, "error": None}
    except etree.XMLSyntaxError as err:
        return {
            "valid": False,
            "error": {
                "line": err.lineno,
                "column": err.offset,
                "message": err.msg
            }
        }
    except Exception as e:
        return {"valid": False, "error": {"line": 0, "column": 0, "message": str(e)}}

def validate_xml_against_xsd(xml_content, xsd_content):
    """
    Step 2 & 3: Validate XML document against XSD schema.
    Performs contract validation, checks required elements, and data types.
    """
    # 1. Check well-formedness first
    wf = validate_xml_well_formedness(xml_content)
    if not wf["valid"]:
        return {
            "valid": False,
            "status": "MALFORMED_XML",
            "summary": "XML document is not well-formed.",
            "errors": [wf["error"]]
        }

    # 2. Parse XSD schema
    try:
        schema_root = etree.fromstring(xsd_content.encode('utf-8'))
        xmlschema = etree.XMLSchema(schema_root)
    except etree.XMLSchemaParseError as se:
        return {
            "valid": False,
            "status": "INVALID_SCHEMA",
            "summary": f"XSD Schema contains syntax errors: {se}",
            "errors": [{"line": getattr(se, 'line', 0), "column": 0, "message": str(se)}]
        }
    except Exception as e:
        return {
            "valid": False,
            "status": "INVALID_SCHEMA",
            "summary": f"Could not load XSD schema: {str(e)}",
            "errors": [{"line": 0, "column": 0, "message": str(e)}]
        }

    # 3. Parse XML document
    doc = etree.fromstring(xml_content.encode('utf-8'))

    # If this is a SOAP Envelope, extract the inner payload body element for schema validation if appropriate
    envelope_ns = "http://schemas.xmlsoap.org/soap/envelope/"
    envelope_ns12 = "http://www.w3.org/2003/05/soap-envelope"
    target_node = doc
    if doc.tag in (f"{{{envelope_ns}}}Envelope", f"{{{envelope_ns12}}}Envelope"):
        body_node = doc.find(f"{{{envelope_ns}}}Body")
        if body_node is None:
            body_node = doc.find(f"{{{envelope_ns12}}}Body")
        if body_node is not None and len(body_node) > 0:
            target_node = body_node[0]

    # Validate against Schema
    is_valid = xmlschema.validate(target_node)
    if is_valid:
        return {
            "valid": True,
            "status": "VALID",
            "summary": "XML conforms completely to the Data Contract (XSD). All required elements and data types are verified.",
            "errors": []
        }
    else:
        errors = []
        for err in xmlschema.error_log:
            category = "Contract Mismatch"
            if "datatype" in err.message.lower() or "not a valid value of the atomic type" in err.message.lower():
                category = "Data Type Verification Failure"
            elif "missing child element" in err.message.lower() or "expected" in err.message.lower():
                category = "Missing Required Field"
            elif "not allowed" in err.message.lower() or "unexpected" in err.message.lower():
                category = "Unexpected Element / Schema Violation"

            errors.append({
                "category": category,
                "line": err.line,
                "column": err.column,
                "message": err.message,
                "level_name": err.level_name
            })

        return {
            "valid": False,
            "status": "CONTRACT_VIOLATION",
            "summary": f"Data contract violation detected ({len(errors)} error(s) found).",
            "errors": errors
        }

def assess_contract_compatibility(v1_xsd, v2_xsd):
    """
    Step 4: Compatibility Assessment
    Compares Schema V1 (Consumer/Old) and Schema V2 (Provider/New).
    Identifies breaking changes (removed fields, increased minOccurs, changed types)
    vs non-breaking changes (optional field additions, looser constraints).
    """
    try:
        root_v1 = etree.fromstring(v1_xsd.encode('utf-8'))
        root_v2 = etree.fromstring(v2_xsd.encode('utf-8'))
    except Exception as e:
        return {"success": False, "error": f"Error parsing schemas: {str(e)}"}

    def extract_elements(root):
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

    elements_v1 = extract_elements(root_v1)
    elements_v2 = extract_elements(root_v2)

    breaking_changes = []
    non_breaking_changes = []

    # Check for removed elements or modified constraints
    for name, v1_attr in elements_v1.items():
        if name not in elements_v2:
            breaking_changes.append(f"Element '{name}' was removed in newer schema (Breaking for existing consumers).")
        else:
            v2_attr = elements_v2[name]
            if v1_attr["type"] != v2_attr["type"]:
                breaking_changes.append(f"Element '{name}' type changed from '{v1_attr['type']}' to '{v2_attr['type']}'.")
            
            # minOccurs increased
            try:
                if int(v2_attr["minOccurs"]) > int(v1_attr["minOccurs"]):
                    breaking_changes.append(f"Element '{name}' minimum occurrence constraint increased from {v1_attr['minOccurs']} to {v2_attr['minOccurs']} (Now required).")
            except ValueError:
                pass

    # Check for added elements in v2
    for name, v2_attr in elements_v2.items():
        if name not in elements_v1:
            try:
                min_occ = int(v2_attr.get("minOccurs", "1"))
                if min_occ > 0:
                    breaking_changes.append(f"Mandatory new element '{name}' (minOccurs={min_occ}) added without backward default.")
                else:
                    non_breaking_changes.append(f"Optional new element '{name}' added (Backward compatible).")
            except ValueError:
                non_breaking_changes.append(f"New element '{name}' added.")

    is_compatible = len(breaking_changes) == 0

    return {
        "success": True,
        "is_compatible": is_compatible,
        "compatibility_status": "COMPATIBLE" if is_compatible else "INCOMPATIBLE (BREAKING CHANGES)",
        "breaking_changes": breaking_changes,
        "non_breaking_changes": non_breaking_changes,
        "v1_element_count": len(elements_v1),
        "v2_element_count": len(elements_v2)
    }
