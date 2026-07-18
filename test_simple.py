#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('Step 1: Importing core modules')
try:
    from core.elf_parser import ELFParser
    print('Step 2: ELFParser imported successfully')
except Exception as e:
    print(f'Step 2 FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Step 3: Loading ELF')
try:
    elf = ELFParser('tests/qemu_m4_threadx/firmware/output/img/sample_threadx.elf')
    print(f'Step 4: ELF loaded: {"32-bit" if elf.is_32bit() else "64-bit"}')
    print(f'Step 5: Symbols count: {len(elf._symbol_cache)}')
    print(f'Step 6: Struct types count: {len(elf._struct_type_cache)}')
except Exception as e:
    print(f'Step 4 FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Step 7: Searching for tx_thread symbols')
try:
    symbols = elf.find_symbols_by_pattern('tx_thread')
    print(f'Step 8: Found {len(symbols)} symbols:')
    for s in symbols[:5]:
        print(f"  {s['name']}: {s['address']:#08x}")
except Exception as e:
    print(f'Step 8 FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Done!')