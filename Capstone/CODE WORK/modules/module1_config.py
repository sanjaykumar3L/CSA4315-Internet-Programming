from lxml import etree
import re

WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"
SOAP_NS = "http://schemas.xmlsoap.org/wsdl/soap/"
SOAP12_NS = "http://schemas.xmlsoap.org/wsdl/soap12/"
XSD_NS = "http://www.w3.org/2001/XMLSchema"

def parse_wsdl_content(wsdl_xml_str):
    """
    Parses WSDL string and extracts:
    - Target Namespace
    - Services & Endpoints
    - Operations with input/output messages
    - Embedded XSD schemas
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True, recover=True)
        root = etree.fromstring(wsdl_xml_str.encode('utf-8'), parser)
    except Exception as e:
        return {"success": False, "error": f"Failed to parse WSDL XML: {str(e)}"}

    nsmap = root.nsmap.copy()
    if None in nsmap:
        nsmap["wsdl_default"] = nsmap.pop(None)

    target_namespace = root.attrib.get("targetNamespace", "urn:default-namespace")
    
    # 1. Extract Services and Endpoints
    services = []
    for service_node in root.findall(f"{{{WSDL_NS}}}service"):
        s_name = service_node.attrib.get("name", "UnknownService")
        ports = []
        for port in service_node.findall(f"{{{WSDL_NS}}}port"):
            p_name = port.attrib.get("name", "UnknownPort")
            binding = port.attrib.get("binding", "")
            address_node = port.find(f"{{{SOAP_NS}}}address")
            if address_node is None:
                address_node = port.find(f"{{{SOAP12_NS}}}address")
            endpoint_url = address_node.attrib.get("location", "") if address_node is not None else ""
            ports.append({
                "port_name": p_name,
                "binding": binding,
                "endpoint_url": endpoint_url
            })
        services.append({
            "service_name": s_name,
            "ports": ports
        })

    # 2. Extract PortTypes and Operations
    operations = []
    for port_type in root.findall(f"{{{WSDL_NS}}}portType"):
        pt_name = port_type.attrib.get("name", "DefaultPortType")
        for op in port_type.findall(f"{{{WSDL_NS}}}operation"):
            op_name = op.attrib.get("name", "")
            input_node = op.find(f"{{{WSDL_NS}}}input")
            output_node = op.find(f"{{{WSDL_NS}}}output")
            
            in_msg = input_node.attrib.get("message", "") if input_node is not None else ""
            out_msg = output_node.attrib.get("message", "") if output_node is not None else ""
            
            operations.append({
                "port_type": pt_name,
                "operation_name": op_name,
                "input_message": in_msg,
                "output_message": out_msg
            })

    # 3. Extract Embedded Schemas (XSD)
    embedded_schemas = []
    types_node = root.find(f"{{{WSDL_NS}}}types")
    if types_node is not None:
        for schema in types_node.findall(f"{{{XSD_NS}}}schema"):
            schema_str = etree.tostring(schema, pretty_print=True, encoding="utf-8").decode("utf-8")
            embedded_schemas.append(schema_str)

    default_endpoint = ""
    if services and services[0]["ports"]:
        default_endpoint = services[0]["ports"][0]["endpoint_url"]

    return {
        "success": True,
        "target_namespace": target_namespace,
        "services": services,
        "operations": operations,
        "embedded_schemas": embedded_schemas,
        "default_endpoint": default_endpoint
    }

def generate_soap_request_template(target_namespace, operation_name, parameters=None, soap_version="1.1"):
    """
    Generates a syntactically valid SOAP Request XML envelope for an operation.
    """
    if parameters is None:
        parameters = {"param1": "10", "param2": "20"}

    param_elements = ""
    for k, v in parameters.items():
        param_elements += f"         <{k}>{v}</{k}>\n"

    if soap_version == "1.2":
        env = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"
                 xmlns:tns="{target_namespace}">
  <soap12:Header/>
  <soap12:Body>
    <tns:{operation_name}>
{param_elements}    </tns:{operation_name}>
  </soap12:Body>
</soap12:Envelope>"""
    else:
        env = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="{target_namespace}">
  <soap:Header/>
  <soap:Body>
    <tns:{operation_name}>
{param_elements}    </tns:{operation_name}>
  </soap:Body>
</soap:Envelope>"""
    return env
