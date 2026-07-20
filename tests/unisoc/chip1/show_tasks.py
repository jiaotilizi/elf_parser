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
    profile_name = 'profiles/unisoc/chip1.yaml'

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

    loader = ProfileLoader()
    profile = loader.load_profile(profile_name)
    if not profile:
        print(f"✗ 无法加载 profile: {profile_name}")
        return 1

    regions = loader.get_memory_regions(profile)

    print("Loading ELF...")
    elf_parser = ELFParser(elf_path)

    print("Loading Dump...")
    dump_reader = DumpReader(dump_path, regions)

    print("\n=== ThreadX Task Information ===")
    
    created_ptr_sym = elf_parser.get_symbol_by_name('_tx_thread_created_ptr')
    if created_ptr_sym:
        created_ptr_addr = created_ptr_sym['address']
        created_ptr_value = dump_reader.read_uint32(created_ptr_addr)
        print(f"\n_tx_thread_created_ptr @ 0x{created_ptr_addr:08x} = 0x{created_ptr_value:08x}")
        
        if created_ptr_value != 0:
            print(f"\nParsing TX_THREAD type...")
            tx_thread_type = elf_parser.get_struct_type('TX_THREAD')
            if tx_thread_type:
                print(f"  TX_THREAD size: {tx_thread_type.get('byte_size')} bytes")
                print(f"  TX_THREAD kind: {tx_thread_type.get('kind')}")
                
                members = tx_thread_type.get('members', [])
                print(f"  TX_THREAD members: {len(members)}")
                
                member_offsets = {}
                for m in members:
                    name = m.get('name')
                    if name:
                        member_offsets[name] = m.get('offset', 0)
                        print(f"    - {name}: offset=0x{m.get('offset', 0):04x}, size={m.get('byte_size', 0)}")
        
        current_ptr_sym = elf_parser.get_symbol_by_name('_tx_thread_current_ptr')
        if current_ptr_sym:
            current_ptr_addr = current_ptr_sym['address']
            current_ptr_value = dump_reader.read_uint32(current_ptr_addr)
            print(f"\n_tx_thread_current_ptr @ 0x{current_ptr_addr:08x} = 0x{current_ptr_value:08x}")
            
            if current_ptr_value != 0:
                print(f"\nCurrent thread TCB @ 0x{current_ptr_value:08x}")
                current_tcb = elf_parser.parse_struct_auto('_tx_thread_current_ptr', dump_reader)
                if current_tcb:
                    print(f"  Thread name: {current_tcb.get('tx_thread_name', 'N/A')}")
                    print(f"  Thread state: {current_tcb.get('tx_thread_state', 'N/A')}")
                    print(f"  Thread priority: {current_tcb.get('tx_thread_priority', 'N/A')}")
                    print(f"  Thread entry: 0x{current_tcb.get('tx_thread_entry', 0):08x}")
    
    print("\n=== Loading ThreadX Plugin ===")
    try:
        from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
        
        plugin = ThreadXV6Plugin()
        context = {
            'elf_parser': elf_parser,
            'dump_reader': dump_reader,
            'profile': profile,
        }
        
        print("Initializing plugin...")
        if plugin.initialize(context):
            print("  ✓ Plugin initialized")
            
            print("\nExecuting plugin...")
            result = plugin.execute(context)
            
            if result:
                tasks = result.get('tasks', [])
                print(f"\nFound {len(tasks)} tasks:")
                print("-" * 100)
                print(f"{'Name':<30} {'Priority':>8} {'State':<12} {'Stack Size':>10} {'Address':>16}")
                print("-" * 100)
                
                for task in tasks:
                    name = task.get('name', 'N/A')
                    priority = task.get('priority', 'N/A')
                    state = task.get('state', 'N/A')
                    stack_size = task.get('stack_size', 0)
                    address = task.get('address', 0)
                    
                    print(f"{name:<30} {priority:>8} {state:<12} {stack_size:>10} 0x{address:08x}")
            
            else:
                print("  ✗ Plugin execute returned None")
        else:
            print("  ✗ Plugin initialize failed")
            
    except ImportError as e:
        print(f"  ✗ Failed to import plugin: {e}")
    except Exception as e:
        print(f"  ✗ Plugin error: {e}")
        import traceback
        traceback.print_exc()

    print("\nDone!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
