"""
MIT License

Copyright (c) 2026 Tom Yang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import argparse
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    from core.elf_parser import ELFParser
    from core.dump_reader import DumpReader
    from core.profile_loader import ProfileLoader
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.elf_parser import ELFParser
    from core.dump_reader import DumpReader
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
    parser.add_argument('--outfile', help='Output file path for display output')
    
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
            show_display(args.display, results, args.outfile)
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
    
    print(f"Validating profile...")
    validation_errors = profile_loader.validate_profile(profile)
    if validation_errors:
        raise ValueError(f"Profile validation failed: {'; '.join(validation_errors)}")
    
    print(f"Loading ELF: {elf_path}")
    elf_parser = ELFParser(elf_path)
    
    print(f"Loading dump: {dump_path}")
    memory_regions = profile_loader.get_memory_regions(profile)
    dump_reader = DumpReader(dump_path, memory_regions)
    
    keywords = profile.get('keyword', [])
    if keywords:
        print(f"Running keyword matching for profile: {', '.join(keywords)}")
        
        elf_unmatched = set(elf_parser.match_keywords(keywords))
        dump_unmatched = set(dump_reader.match_keywords(keywords))
        
        all_unmatched = elf_unmatched & dump_unmatched
        if all_unmatched:
            print(f"Keyword match failed:")
            if all_unmatched:
                print(f"  Unmatched in both ELF and Dump: {', '.join(sorted(all_unmatched))}")
            raise ValueError(f"Profile/ELF/Dump mismatch: {len(all_unmatched)} keywords not found in either ELF or dump")
    
    print(f"Loading plugins from profile...")
    plugins = profile_loader.load_plugins_from_profile(profile)
    
    context = {
        'elf_parser': elf_parser,
        'dump_reader': dump_reader,
        'profile': profile,
        'results': {},
        'config': {},
        'plugins': plugins,
    }
    
    print(f"Initializing plugins...")
    for plugin in plugins:
        plugin.initialize(context)
    
    print(f"Executing plugins...")
    plugin_results = {}
    for plugin in plugins:
        try:
            result = plugin.execute(context)
            if result:
                plugin_results[plugin.name] = result
        except Exception as e:
            print(f"Error executing plugin {plugin.name}: {e}")
            plugin_results[plugin.name] = {'error': str(e)}
    
    context['results'] = plugin_results
    
    return {
        'elf_parser': elf_parser,
        'dump_reader': dump_reader,
        'profile': profile,
        'plugins': [p.name for p in plugins],
        'results': plugin_results,
        'context': context,
    }


def show_display(scheme: str, results: dict, outfile: str = None):
    profile = results['profile']
    
    data_adapter = DataAdapter(results['context'])
    
    display = DisplayFactory.create(scheme, profile, data_adapter)
    
    import sys
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    if outfile:
        sys.stdout = open(outfile, 'w', encoding='utf-8')
        sys.stderr = sys.stdout
    
    display.run()
    
    if outfile:
        sys.stdout.close()
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def list_profiles():
    profile_loader = ProfileLoader()
    profiles = profile_loader.list_profiles()
    
    print("Available profiles:")
    for p in profiles:
        print(f"  - {p['name']}: {p['chip']}")


def list_plugins():
    from plugins.base import Plugin
    import importlib
    import os
    
    plugin_dirs = ['rtos', 'module']
    plugins = []
    
    for plugin_dir in plugin_dirs:
        full_dir = os.path.join(os.path.dirname(__file__), 'plugins', plugin_dir)
        if not os.path.exists(full_dir):
            continue
        
        for subdir in os.listdir(full_dir):
            subdir_path = os.path.join(full_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue
            
            for filename in os.listdir(subdir_path):
                if filename.endswith('.py') and not filename.startswith('_'):
                    module_path = f"plugins.{plugin_dir}.{subdir}.{filename[:-3]}"
                    try:
                        module = importlib.import_module(module_path)
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                                if attr.__name__ in ('RTOSPlugin', 'ModulePlugin', 'Plugin'):
                                    continue
                                plugins.append({
                                    'path': module_path.replace('plugins.', ''),
                                    'name': attr_name,
                                })
                    except Exception:
                        pass
    
    print("Available plugins:")
    for p in plugins:
        print(f"  - {p['path']}")


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
        data_adapter = DataAdapter(results['context'])
        display = DisplayFactory.create(display_config, profile, data_adapter)
        display.run()
        return
    
    output = {
        'profile': profile.get('chip', {}).get('name', 'unknown'),
        'plugins': results['plugins'],
        'analysis': results['results'],
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to: {output_file}")


if __name__ == '__main__':
    main()
