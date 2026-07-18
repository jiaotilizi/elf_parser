import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.plugin_manager import PluginManager, PluginContext
from core.profile_loader import ProfileLoader
from display import DisplayFactory
from display.data_adapter import DataAdapter


def main():
    parser = argparse.ArgumentParser(description='ELF/Dump offline analysis tool')
    parser.add_argument('--elf', help='Path to ELF/AXF file')
    parser.add_argument('--dump', help='Path to dump.bin file')
    parser.add_argument('--profile', help='Profile name or path')
    parser.add_argument('--output', help='Output file path (JSON)')
    parser.add_argument('--list-profiles', action='store_true', help='List available profiles')
    parser.add_argument('--list-plugins', action='store_true', help='List available plugins')
    parser.add_argument('--dump-struct', help='Dump specific struct by name')
    parser.add_argument('--dump-symbol', help='Dump specific symbol by name')
    parser.add_argument('--search-symbol', help='Search symbols by pattern')
    parser.add_argument('--display', help='Display scheme: cli_basic, cli_interactive, web_gui')
    
    args = parser.parse_args()
    
    if args.list_profiles:
        list_profiles()
        return
    
    if args.list_plugins:
        list_plugins()
        return
    
    if not args.elf or not args.dump or not args.profile:
        parser.print_help()
        return
    
    try:
        results = analyze(
            elf_path=args.elf,
            dump_path=args.dump,
            profile_name=args.profile
        )
        
        if args.dump_struct:
            dump_struct(results['elf_parser'], results['dump_reader'], args.dump_struct)
        elif args.dump_symbol:
            dump_symbol(results['elf_parser'], results['dump_reader'], args.dump_symbol)
        elif args.search_symbol:
            search_symbols(results['elf_parser'], args.search_symbol)
        elif args.display:
            show_display(args.display, results)
        else:
            output_results(results, args.output)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def analyze(elf_path: str, dump_path: str, profile_name: str) -> dict:
    print(f"Loading profile: {profile_name}")
    profile_loader = ProfileLoader()
    profile = profile_loader.load_profile(profile_name)
    
    if not profile:
        raise ValueError(f"Profile not found: {profile_name}")
    
    print(f"Loading ELF: {elf_path}")
    elf_parser = ELFParser(elf_path)
    
    print(f"Loading dump: {dump_path}")
    memory_regions = profile_loader.get_memory_regions(profile)
    dump_reader = DumpReader(dump_path, memory_regions)
    
    print(f"Discovering plugins...")
    plugin_manager = PluginManager()
    plugin_manager.discover_plugins()
    
    print(f"Loading plugins from profile...")
    plugins = plugin_manager.load_plugins_from_profile(profile)
    
    context = PluginContext()
    context.set_elf_parser(elf_parser)
    context.set_dump_reader(dump_reader)
    context.set_profile(profile)
    
    print(f"Initializing plugins...")
    initialized_plugins = plugin_manager.initialize_plugins(plugins, context.__dict__)
    
    print(f"Executing plugins...")
    plugin_results = plugin_manager.execute_plugins(initialized_plugins, context.__dict__)
    
    return {
        'elf_parser': elf_parser,
        'dump_reader': dump_reader,
        'profile': profile,
        'plugins': [p.name for p in initialized_plugins],
        'results': plugin_results,
        'plugin_manager': plugin_manager,
        'context': context.__dict__,
    }


def show_display(scheme: str, results: dict):
    profile = results['profile']
    plugin_manager = results['plugin_manager']
    context = results['context']
    
    data_adapter = DataAdapter(plugin_manager, context)
    
    display = DisplayFactory.create(scheme, profile, data_adapter)
    display.run()


def list_profiles():
    profile_loader = ProfileLoader()
    profiles = profile_loader.list_profiles()
    
    print("Available profiles:")
    for p in profiles:
        print(f"  - {p['name']}: {p['chip']} ({p['os']} {p['os_version']})")


def list_plugins():
    plugin_manager = PluginManager()
    plugin_manager.discover_plugins()
    plugins = plugin_manager.list_all_plugins()
    
    print("OS Plugins:")
    for p in plugins['os']:
        print(f"  - {p['name']}: {p['os_name']} {p['os_version']}")
    
    print("\nModule Plugins:")
    for p in plugins['module']:
        print(f"  - {p['name']}: {p['module_type']}")


def dump_struct(elf_parser, dump_reader, struct_name: str):
    struct_type = elf_parser.get_struct_type(struct_name)
    if not struct_type:
        print(f"Struct not found: {struct_name}")
        return
    
    print(f"Struct: {struct_name}")
    print(f"  Size: {struct_type['byte_size']} bytes")
    print(f"  Members:")
    for member in struct_type.get('members', []):
        print(f"    - {member.get('name', 'unknown')}: offset={member.get('offset', 0):#08x}, size={member.get('byte_size', 0)} bytes, type={member.get('type_name', 'unknown')}")


def dump_symbol(elf_parser, dump_reader, symbol_name: str):
    symbol = elf_parser.get_symbol_by_name(symbol_name)
    if not symbol:
        print(f"Symbol not found: {symbol_name}")
        return
    
    print(f"Symbol: {symbol_name}")
    print(f"  Address: {symbol['address']:#08x}")
    print(f"  Size: {symbol['size']} bytes")
    print(f"  Type: {symbol['type']}")
    
    if symbol['size'] > 0:
        raw_data = dump_reader.read_memory(symbol['address'], symbol['size'])
        if raw_data:
            print(f"  Raw data (hex): {raw_data.hex()}")
            
            struct_type = elf_parser.get_struct_type(symbol_name)
            if struct_type:
                parsed = elf_parser.parse_struct_from_dump(struct_type.get('name', ''), symbol['address'], dump_reader.dump_data)
                if parsed:
                    print(f"  Struct members:")
                    for name, member in parsed.get('members', {}).items():
                        print(f"    - {name}: value={member.get('value', 0):#08x} (offset={member.get('offset', 0):#04x})")


def search_symbols(elf_parser, pattern: str):
    symbols = elf_parser.find_symbols_by_pattern(pattern)
    
    if not symbols:
        print(f"No symbols found matching: {pattern}")
        return
    
    print(f"Symbols matching '{pattern}':")
    for sym in symbols:
        print(f"  - {sym['name']}: {sym['address']:#08x} (size={sym['size']}, type={sym['type']})")


def output_results(results: dict, output_file: str = None):
    profile = results['profile']
    display_config = profile.get('display', {}).get('scheme', 'cli_basic')
    
    if not output_file:
        data_adapter = DataAdapter(results['plugin_manager'], results['context'])
        display = DisplayFactory.create(display_config, profile, data_adapter)
        display.run()
        return
    
    output = {
        'profile': profile.get('chip', {}).get('name', 'unknown'),
        'os': profile.get('os', {}).get('name', 'unknown'),
        'os_version': profile.get('os', {}).get('version', 'unknown'),
        'plugins': results['plugins'],
        'analysis': results['results'],
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to: {output_file}")


if __name__ == '__main__':
    main()