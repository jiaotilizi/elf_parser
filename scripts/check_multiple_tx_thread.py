import sys
sys.path.insert(0, '.')

from elftools.elf.elffile import ELFFile

elf_path = sys.argv[1]

with open(elf_path, 'rb') as f:
    elffile = ELFFile(f)
    dwarfinfo = elffile.get_dwarf_info()
    
    print("All TX_THREAD entries:")
    count = 0
    for cu in dwarfinfo.iter_CUs():
        for die in cu.iter_DIEs():
            name_attr = die.attributes.get('DW_AT_name')
            if name_attr and name_attr.value.decode('utf-8') == 'TX_THREAD':
                print(f"  #{count}: CU={cu.cu_offset}, DIE={die.offset}, tag={die.tag}")
                count += 1
    
    print(f"\nTotal TX_THREAD entries found: {count}")