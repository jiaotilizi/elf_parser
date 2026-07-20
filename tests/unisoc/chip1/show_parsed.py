import os
import sys

_ELF_PARSER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ELF_PARSER_DIR not in sys.path:
    sys.path.insert(0, _ELF_PARSER_DIR)

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    elf_path = os.path.join(SCENARIO_DIR, 'output', 'QogirS6_PS_modem.axf')
    dump_path = os.path.join(SCENARIO_DIR, 'output', '2026_07_03_14_19_35_658_1.mem')
    profile_name = 'unisoc/chip1'

    print(f"ELF  : {elf_path}")
    print(f"Dump : {dump_path}")
    print(f"Profile: {profile_name}")
    print()

    if not os.path.exists(elf_path):
        print(f"✗ ELF 不存在: {elf_path}")
        return 1
    if not os.path.exists(dump_path):
        print(f"✗ Dump 不存在: {dump_path}")
        return 1

    print("Loading profile...")
    loader = ProfileLoader()
    profile = loader.load_profile(profile_name)
    if not profile:
        print(f"✗ 无法加载 profile: {profile_name}")
        return 1
    print(f"  ✓ Profile loaded: {profile['chip']['name']}")

    print("Loading memory regions...")
    regions = loader.get_memory_regions(profile)
    for r in regions:
        print(f"  - {r['name']}: 0x{r['start_addr']:08x} - 0x{r['start_addr'] + r['size']:08x}, offset=0x{r['offset_in_dump']:08x}")

    print("\nLoading ELF...")
    elf_parser = ELFParser(elf_path)
    elf_parser.print_build_info()

    print(f"\n  ✓ Symbols count: {len(elf_parser.get_all_symbols())}")
    print(f"  ✓ Architecture: {'32-bit' if elf_parser.is_32bit() else '64-bit'}")

    print("\nLoading Dump...")
    dump_reader = DumpReader(dump_path, regions)
    print(f"  ✓ Dump size: {dump_reader.get_dump_size()} bytes")
    print(f"  ✓ Memory regions: {dump_reader.get_memory_regions_info()}")

    print("\nSearching for ThreadX keywords...")
    keywords = profile.get('keyword', [])
    if keywords:
        for kw in keywords:
            sym = elf_parser.get_symbol_by_name(kw)
            if sym:
                print(f"  ✓ Found symbol: {kw} at 0x{sym['address']:08x}")
                data = dump_reader.read_uint32(sym['address'])
                if data is not None:
                    print(f"    Value: 0x{data:08x}")
            else:
                print(f"  ✗ Symbol not found: {kw}")

    print("\nSearching for TX_THREAD related symbols...")
    tx_thread_symbols = elf_parser.find_symbols_by_pattern('tx_thread')
    print(f"  Found {len(tx_thread_symbols)} TX_THREAD related symbols")
    for sym in tx_thread_symbols[:10]:
        print(f"    - {sym['name']}: 0x{sym['address']:08x}")

    print("\nSearching for TX_ related struct types...")
    tx_structs = [k for k in elf_parser._type_name_to_offset.keys() if 'TX_' in k or 'tx_' in k]
    print(f"  Found {len(tx_structs)} TX_ related struct types")
    for st in tx_structs[:10]:
        st_info = elf_parser.get_struct_type(st)  # 懒加载触发
        print(f"    - {st}: kind={st_info.get('kind')}, size={st_info.get('byte_size')} bytes")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    sys.exit(main())