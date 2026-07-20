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
                print(f"CU offset: {cu.cu_offset}")
                print(f"DIE offset: {die.offset}")
                print(f"DIE tag: {die.tag}")
                print(f"Absolute offset (cu_offset + die.offset): {cu.cu_offset + die.offset}")
                sys.exit(0)