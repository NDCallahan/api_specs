#!/usr/bin/env python3
"""
Convert VoIP.ms server.wsdl -> voipms.yaml (OpenAPI 3.0.3)
Each WSDL operation becomes a distinct GET path using the
?method=<operationName> pattern of the VoIP.ms REST API.
"""

import xml.etree.ElementTree as ET
import yaml
import sys
import re
from pathlib import Path

WSDL_PATH = Path("/Users/ndcallahan/Downloads/API 2/server.wsdl")
OUT_PATH   = Path("/Users/ndcallahan/ndc_development/openapi_spec/api_specs/voipms.yaml")

XSD_NS    = "http://www.w3.org/2001/XMLSchema"
WSDL_NS   = "http://schemas.xmlsoap.org/wsdl/"
SCHEMA_NS = "https://voip.ms/api/schema"

# Map XSD types to OpenAPI/JSON Schema types
XSD_TYPE_MAP = {
    "string":  {"type": "string"},
    "integer": {"type": "integer"},
    "int":     {"type": "integer"},
    "boolean": {"type": "boolean"},
    "bool":    {"type": "boolean"},
    "decimal": {"type": "number", "format": "decimal"},
    "float":   {"type": "number", "format": "float"},
    "double":  {"type": "number", "format": "double"},
    "date":    {"type": "string", "format": "date"},
    "dateTime":{"type": "string", "format": "date-time"},
}

REQUIRED_SKIP = {"api_username", "api_password"}

def xsd_to_openapi(xsd_type: str) -> dict:
    local = xsd_type.split(":")[-1]
    return XSD_TYPE_MAP.get(local, {"type": "string"})

def camel_to_words(name: str) -> str:
    """Convert camelCase/PascalCase to Title Case words."""
    s = re.sub(r'([A-Z])', r' \1', name).strip()
    return s.title()

def parse_types(root) -> dict:
    """Return {typeName: [(fieldName, xsdType), ...]} for all *Input complex types."""
    types = {}
    for schema in root.iter(f"{{{XSD_NS}}}schema"):
        for ct in schema.findall(f"{{{XSD_NS}}}complexType"):
            name = ct.get("name", "")
            if not name.endswith("Input"):
                continue
            fields = []
            for elem in ct.iter(f"{{{XSD_NS}}}element"):
                fname = elem.get("name")
                ftype = elem.get("type", "xsd:string")
                if fname:
                    fields.append((fname, ftype))
            types[name] = fields
    return types

def parse_operations(root) -> list:
    """Return a list of operation names from the portType."""
    ops = []
    seen = set()
    for pt in root.iter(f"{{{WSDL_NS}}}portType"):
        for op in pt.findall(f"{{{WSDL_NS}}}operation"):
            name = op.get("name")
            if name and name not in seen:
                ops.append(name)
                seen.add(name)
    return ops

def build_parameters(fields: list, op_name: str) -> list:
    """Build OpenAPI parameter list from XSD fields."""
    params = [
        {"$ref": "#/components/parameters/ApiUsername"},
        {"$ref": "#/components/parameters/ApiPassword"},
        {
            "name": "method",
            "in": "query",
            "required": True,
            "schema": {"type": "string", "enum": [op_name]},
            "description": "API method to call",
        },
    ]
    for fname, ftype in fields:
        if fname in REQUIRED_SKIP:
            continue
        schema = xsd_to_openapi(ftype)
        params.append({
            "name": fname,
            "in": "query",
            "required": False,
            "schema": schema,
            "description": f"{camel_to_words(fname)}",
        })
    return params

def build_spec(operations: list, types: dict) -> dict:
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "VoIP.ms API",
            "description": (
                "Full OpenAPI specification for the VoIP.ms REST API. "
                "Generated from server.wsdl. Each operation is exposed as a "
                "distinct GET path under ?method=<operation>."
            ),
            "version": "1.0.0",
        },
        "servers": [
            {
                "url": "https://voip.ms/api/v1/rest.php",
                "description": "VoIP.ms REST API production server",
            }
        ],
        "components": {
            "securitySchemes": {
                "basicAuth": {"type": "http", "scheme": "basic"}
            },
            "parameters": {
                "ApiUsername": {
                    "name": "api_username",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Email used to login to VoIP.ms portal",
                },
                "ApiPassword": {
                    "name": "api_password",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Password created for the API",
                },
            },
        },
        "security": [{"basicAuth": []}],
        "paths": {},
    }

    for op in operations:
        input_type_name = op[0].upper() + op[1:] + "Input"  # e.g. getBalanceInput
        # also try exact casing variants
        fields = types.get(input_type_name) or types.get(op + "Input") or []

        path_key = f"/{op}"
        spec["paths"][path_key] = {
            "get": {
                "summary": camel_to_words(op),
                "operationId": op,
                "parameters": build_parameters(fields, op),
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                    },
                                    "additionalProperties": True,
                                }
                            }
                        },
                    },
                    "400": {"description": "Invalid request or API error"},
                },
            }
        }

    return spec

def main():
    if not WSDL_PATH.exists():
        print(f"ERROR: WSDL not found at {WSDL_PATH}", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(WSDL_PATH)
    root = tree.getroot()

    types = parse_types(root)
    operations = parse_operations(root)

    print(f"Parsed {len(types)} input types and {len(operations)} operations.")

    spec = build_spec(operations, types)

    # Use a representer that outputs multiline strings cleanly
    class LiteralStr(str):
        pass

    def representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(LiteralStr, representer)
    yaml.add_representer(str, representer)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Written: {OUT_PATH}")
    print(f"Total paths: {len(spec['paths'])}")

if __name__ == "__main__":
    main()
