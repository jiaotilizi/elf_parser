import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.elf_parser import ELFParserFactory
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader
from core.plugin_registry import PluginRegistry


def profile_elf_parser(elf_path: str, parser_type: str = 'elftools'):
    print("\n" + "=" * 60)
    print("ELF Parser Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    parser = ELFParserFactory.create(elf_path, parser_type)
    total_time = time.time() - start
    
    print(f"\nTotal ELF Parser init: {total_time:.3f}s")
    print(f"  ELF Path: {elf_path}")
    print(f"  File size: {os.path.getsize(elf_path) / (1024 * 1024):.1f} MB")
    print(f"  Architecture: {'32-bit' if parser.is_32bit() else '64-bit'}")
    
    return parser


def profile_dump_reader(dump_path: str, memory_regions: list):
    print("\n" + "=" * 60)
    print("Dump Reader Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    reader = DumpReader(dump_path, memory_regions)
    total_time = time.time() - start
    
    print(f"\nTotal Dump Reader init: {total_time:.3f}s")
    print(f"  Dump Path: {dump_path}")
    print(f"  Dump size: {reader.get_dump_size() / (1024 * 1024):.1f} MB")
    print(f"  Memory regions: {len(reader.memory_regions)}")
    for region in reader.memory_regions:
        print(f"    - {region.name}: 0x{region.start_addr:08x} - 0x{region.end_addr:08x} (size={region.size/1024:.0f} KB)")
    
    return reader


def profile_plugin_execution(parser, reader, profile):
    print("\n" + "=" * 60)
    print("Plugin Execution Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    registry = PluginRegistry()
    plugins = registry.get_plugins_for_profile(profile)
    plugin_load_time = time.time() - start
    
    print(f"\nPlugin load time: {plugin_load_time:.3f}s")
    print(f"Number of plugins: {len(plugins)}")
    for plugin in plugins:
        print(f"  - {plugin.name} ({plugin.__class__.__name__})")
    
    context = {
        'elf_parser': parser,
        'dump_reader': reader,
        'profile': profile,
        'results': {},
        'config': {},
        'plugins': plugins,
    }
    
    start = time.time()
    for plugin in plugins:
        plugin.initialize(context)
    init_time = time.time() - start
    
    print(f"\nPlugin initialize time: {init_time:.3f}s")
    
    start = time.time()
    plugin_results = {}
    for plugin in plugins:
        plugin_start = time.time()
        try:
            result = plugin.execute(context)
            if result:
                plugin_results[plugin.name] = result
        except Exception as e:
            print(f"  Error executing {plugin.name}: {e}")
            plugin_results[plugin.name] = {'error': str(e)}
        plugin_time = time.time() - plugin_start
        print(f"  - {plugin.name}: {plugin_time:.3f}s")
    
    total_exec_time = time.time() - start
    print(f"\nTotal plugin execution time: {total_exec_time:.3f}s")
    
    return plugin_results


def profile_type_parsing(parser):
    print("\n" + "=" * 60)
    print("Type Parsing Performance Profiling")
    print("=" * 60)
    
    test_types = ['TX_THREAD', 'TX_MUTEX', 'TX_SEMAPHORE', 'TX_QUEUE']
    
    for type_name in test_types:
        start = time.time()
        type_info = parser.get_struct_type(type_name)
        elapsed = time.time() - start
        
        if type_info:
            print(f"  {type_name}: {elapsed:.3f}s (size={type_info.get('byte_size', 0)} bytes, members={len(type_info.get('members', []))})")
        else:
            print(f"  {type_name}: {elapsed:.3f}s - NOT FOUND")


def main():
    if len(sys.argv) != 4:
        print("Usage: python profile_performance.py <elf_path> <dump_path> <profile_path>")
        sys.exit(1)
    
    elf_path = sys.argv[1]
    dump_path = sys.argv[2]
    profile_path = sys.argv[3]
    
    print(f"\n{'=' * 60}")
    print("Unisoc Chip1 Dump Analysis Performance Profile")
    print(f"{'=' * 60}")
    print(f"ELF: {elf_path}")
    print(f"Dump: {dump_path}")
    print(f"Profile: {profile_path}")
    
    total_start = time.time()
    
    loader = ProfileLoader()
    profile = loader.load_profile(profile_path)
    memory_regions = loader.get_memory_regions(profile)
    parser_config = loader.get_parser_config(profile)
    parser_type = parser_config.get('type', 'elftools')
    
    parser = profile_elf_parser(elf_path, parser_type)
    reader = profile_dump_reader(dump_path, memory_regions)
    profile_type_parsing(parser)
    profile_plugin_execution(parser, reader, profile)
    
    total_time = time.time() - total_start
    
    print("\n" + "=" * 60)
    print(f"TOTAL ANALYSIS TIME: {total_time:.3f}s")
    print("=" * 60)


if __name__ == '__main__':
    main()