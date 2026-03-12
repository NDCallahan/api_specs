#!/usr/bin/env python3
"""
Apply descriptions from CSV to voipms.yaml paths.
CSV expected columns: Category,Function,Description
"""
import csv, yaml
from pathlib import Path

CSV_PATH = Path('/Users/ndcallahan/Desktop/voip-ms_api-calls.csv')
YAML_PATH = Path('/Users/ndcallahan/ndc_development/openapi_spec/api_specs/voipms.yaml')

if not CSV_PATH.exists():
    print('CSV not found:', CSV_PATH)
    raise SystemExit(1)
if not YAML_PATH.exists():
    print('YAML not found:', YAML_PATH)
    raise SystemExit(1)

# Load CSV
mapping = {}
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        fn = row.get('Function')
        desc = row.get('Description')
        if fn and desc:
            mapping[fn.strip()] = desc.strip()

# Load YAML
with open(YAML_PATH, 'r', encoding='utf-8') as f:
    spec = yaml.safe_load(f)

paths = spec.get('paths', {})
updated = 0
for path_key, path_item in list(paths.items()):
    # path_key may be '/getBalance' or 'getBalance' depending on generation
    key_name = path_key.lstrip('/')
    if key_name in mapping:
        desc = mapping[key_name]
        # Update description for GET operation if exists
        getop = path_item.get('get')
        if getop is not None:
            existing = getop.get('description', '')
            if existing != desc:
                getop['description'] = desc
                updated += 1

# Write back YAML
with open(YAML_PATH, 'w', encoding='utf-8') as f:
    yaml.dump(spec, f, sort_keys=False, allow_unicode=True)

print(f'Updated {updated} path descriptions in {YAML_PATH}')
