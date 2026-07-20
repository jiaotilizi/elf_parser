import json
import sys

cache_path = sys.argv[1]

with open(cache_path, 'r') as f:
    d = json.load(f)

print(f"die_to_cu keys: {len(d.get('die_to_cu', {}))}")
tx_offset = d['type_index']['TX_THREAD']
print(f"TX_THREAD offset: {tx_offset}")
print(f"TX_THREAD in die_to_cu: {tx_offset in d.get('die_to_cu', {})}")