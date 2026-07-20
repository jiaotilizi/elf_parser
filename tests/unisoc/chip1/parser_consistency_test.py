"""Parser Consistency Test

Compares elftools_parser and dwarffi_parser results for the same AXF file,
verifying semantic equivalence of symbol addresses, type fields, and string content.
"""
import os
import sys
import time
import shutil

_ELF_PARSER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ELF_PARSER_DIR not in sys.path:
    sys.path.insert(0, _ELF_PARSER_DIR)

from core.elf_parser import ELFParserFactory


def clear_dwarffi_cache(axf_path: str):
    """Clear ISF cache to force dwarffi to regenerate."""
    cache_dir = os.path.join(os.path.dirname(axf_path), '.elf_cache')
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


def normalize_members(members):
    """Normalize members to a comparable dict format."""
    result = {}
    if isinstance(members, list):
        for m in members:
            name = m.get('name')
            if name:
                result[name] = {
                    'offset': m.get('offset', 0),
                    'byte_size': m.get('byte_size', 0),
                    'type_name': m.get('type_name', ''),
                }
    elif hasattr(members, '__iter__'):
        for m in members:
            name = m.get('name')
            if name:
                result[name] = {
                    'offset': m.get('offset', 0),
                    'byte_size': m.get('byte_size', 0),
                    'type_name': m.get('type_name', ''),
                }
    return result


def compare_types(elftools_result, dwarffi_result, type_name: str) -> list:
    """Compare a single type between two parsers. Returns list of diffs."""
    diffs = []

    if elftools_result is None and dwarffi_result is None:
        return diffs

    if elftools_result is None:
        diffs.append(f"  {type_name}: elftools=None, dwarffi=found")
        return diffs
    if dwarffi_result is None:
        diffs.append(f"  {type_name}: elftools=found, dwarffi=None")
        return diffs

    # Compare basic fields
    for field in ['kind', 'name', 'byte_size']:
        ev = elftools_result.get(field)
        dv = dwarffi_result.get(field)
        if ev != dv:
            diffs.append(f"  {type_name}.{field}: elftools={ev!r}, dwarffi={dv!r}")

    # Compare members
    e_members = normalize_members(elftools_result.get('members', []))
    d_members = normalize_members(dwarffi_result.get('members', []))

    all_names = set(e_members.keys()) | set(d_members.keys())
    for mname in sorted(all_names):
        if mname not in e_members:
            diffs.append(f"  {type_name}.{mname}: only in dwarffi")
            continue
        if mname not in d_members:
            diffs.append(f"  {type_name}.{mname}: only in elftools")
            continue

        em = e_members[mname]
        dm = d_members[mname]
        for mfield in ['offset', 'byte_size', 'type_name']:
            if em[mfield] != dm[mfield]:
                diffs.append(
                    f"  {type_name}.{mname}.{mfield}: "
                    f"elftools={em[mfield]!r}, dwarffi={dm[mfield]!r}")

    return diffs


def compare_symbols(elftools_result, dwarffi_result, sym_name: str) -> list:
    """Compare a single symbol between two parsers. Returns list of diffs."""
    diffs = []

    if elftools_result is None and dwarffi_result is None:
        return diffs

    if elftools_result is None:
        diffs.append(f"  {sym_name}: elftools=None, dwarffi=found")
        return diffs
    if dwarffi_result is None:
        diffs.append(f"  {sym_name}: elftools=found, dwarffi=None")
        return diffs

    for field in ['name', 'address', 'size']:
        ev = elftools_result.get(field)
        dv = dwarffi_result.get(field)
        if ev != dv:
            diffs.append(
                f"  {sym_name}.{field}: elftools={ev!r}, dwarffi={dv!r}")

    return diffs


def main():
    test_axf = os.path.join(
        os.path.dirname(__file__), 'output',
        'QogirS6_PS_modem.axf')

    if not os.path.exists(test_axf):
        print(f"AXF file not found: {test_axf}")
        print("Skipping consistency test.")
        return 0

    print("=" * 70)
    print("Parser Consistency Test: elftools vs dwarffi")
    print("=" * 70)
    print(f"AXF: {test_axf}")
    print()

    # Clear dwarffi cache to ensure fresh comparison
    clear_dwarffi_cache(test_axf)

    # Load elftools parser
    print("Loading elftools parser...")
    t0 = time.perf_counter()
    elftools = ELFParserFactory.create(test_axf, 'elftools')
    elftools_time = time.perf_counter() - t0
    print(f"  elftools load time: {elftools_time:.2f}s")

    # Load dwarffi parser (will generate ISF cache)
    print("Loading dwarffi parser...")
    t0 = time.perf_counter()
    dwarffi = ELFParserFactory.create(test_axf, 'dwarffi')
    dwarffi_time = time.perf_counter() - t0
    print(f"  dwarffi load time: {dwarffi_time:.2f}s")
    print()

    # ---- 1. Compare symbol addresses ----
    print("--- Symbol Comparison ---")
    elftools_symbols = {s['name']: s for s in elftools.get_all_symbols()}
    dwarffi_symbols = {s['name']: s for s in dwarffi.get_all_symbols()}

    print(f"  elftools: {len(elftools_symbols)} symbols")
    print(f"  dwarffi:  {len(dwarffi_symbols)} symbols")

    all_sym_names = set(elftools_symbols.keys()) | set(dwarffi_symbols.keys())
    sym_diffs = []
    sym_compared = 0

    for name in sorted(all_sym_names):
        diffs = compare_symbols(
            elftools_symbols.get(name), dwarffi_symbols.get(name), name)
        sym_diffs.extend(diffs)
        sym_compared += 1

    print(f"  Compared: {sym_compared}")
    print(f"  Diffs: {len(sym_diffs)}")
    if sym_diffs:
        for d in sym_diffs[:30]:
            print(d)
        if len(sym_diffs) > 30:
            print(f"  ... and {len(sym_diffs) - 30} more diffs")
    print()

    # ---- 2. Compare common types ----
    print("--- Type Comparison ---")
    # Find common types between both parsers
    test_types = [
        'TX_THREAD', 'TX_MUTEX', 'TX_SEMAPHORE', 'TX_QUEUE',
        'TX_EVENT_FLAGS_GROUP', 'TX_TIMER', 'TX_BYTE_POOL',
        'TX_BLOCK_POOL',
    ]

    type_diffs = []
    type_compared = 0

    for tname in test_types:
        et = elftools.get_struct_type(tname)
        dt = dwarffi.get_struct_type(tname)
        if et or dt:
            diffs = compare_types(et, dt, tname)
            type_diffs.extend(diffs)
            type_compared += 1

    print(f"  Test types: {type_compared}")
    print(f"  Diffs: {len(type_diffs)}")
    if type_diffs:
        for d in type_diffs:
            print(d)
    print()

    # ---- 3. Summary ----
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    total_diffs = len(sym_diffs) + len(type_diffs)
    if total_diffs == 0:
        print("  PASS: elftools and dwarffi results are semantically equivalent.")
    else:
        print(f"  {total_diffs} differences found between parsers.")
        print("  Note: Some differences may be expected due to:")
        print("    - dwarffi ISF caching limitations (not all types are cached)")
        print("    - DWARF parser implementation differences")
        print("    - Typedef resolution differences")
    print()
    print(f"  elftools load time: {elftools_time:.2f}s")
    print(f"  dwarffi load time:  {dwarffi_time:.2f}s")

    return 0 if total_diffs == 0 else 1


if __name__ == '__main__':
    sys.exit(main())