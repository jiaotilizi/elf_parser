import sys
sys.path.insert(0, '.')

from elftools.elf.elffile import ELFFile

elf_path = sys.argv[1]

with open(elf_path, 'rb') as f:
    elffile = ELFFile(f)
    dwarfinfo = elffile.get_dwarf_info()
    
    for cu in dwarfinfo.iter_CUs():
        for die in cu.iter_DIEs():
            name_attr = die.attributes.get('DW_AT_name')
            if name_attr and name_attr.value.decode('utf-8') == 'TX_THREAD':
                print(f"CU cu_offset: {cu.cu_offset}")
                print(f"DIE offset: {die.offset}")
                print(f"CU + DIE: {cu.cu_offset + die.offset}")
                
                # Check if die.offset is already absolute
                print(f"\nChecking if die.offset is absolute or relative:")
                for cu2 in dwarfinfo.iter_CUs():
                    if cu2.cu_offset <= die.offset < cu2.cu_offset + (cu2.size if hasattr(cu2, 'size') else 0x10000):
                        print(f"die.offset {die.offset} falls within CU at {cu2.cu_offset}")
                        break
                else:
                    print(f"die.offset {die.offset} does NOT fall within any CU's range")
                    
                sys.exit(0)