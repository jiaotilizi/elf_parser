import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.elf_parser import ELFParserFactory
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader
from core.plugin_registry import PluginRegistry


def profile_elf_parser(elf_path: str, parser_type: str = 'elftools'):
    print("\n" + "=" * 60)
    print("1. ELF Parser Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    parser = ELFParserFactory.create(elf_path, parser_type)
    total_time = time.time() - start
    
    print(f"\n  ELF Path: {elf_path}")
    print(f"  File size: {os.path.getsize(elf_path) / (1024 * 1024):.1f} MB")
    print(f"  Architecture: {'32-bit' if parser.is_32bit() else '64-bit'}")
    
    return parser


def profile_dump_reader(dump_path: str, memory_regions: list):
    print("\n" + "=" * 60)
    print("2. Dump Reader Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    reader = DumpReader(dump_path, memory_regions)
    total_time = time.time() - start
    
    print(f"\n  Total Dump Reader init: {total_time:.3f}s")
    print(f"  Dump Path: {dump_path}")
    print(f"  Dump size: {reader.get_dump_size() / (1024 * 1024):.1f} MB")
    print(f"  Memory regions: {len(reader.memory_regions)}")
    for region in reader.memory_regions:
        print(f"    - {region.name}: 0x{region.start_addr:08x} - 0x{region.end_addr:08x} (size={region.size/1024:.0f} KB)")
    
    return reader


def profile_type_parsing(parser):
    print("\n" + "=" * 60)
    print("3. Type Parsing (First-time, lazy-loaded)")
    print("=" * 60)
    
    test_types = ['TX_THREAD', 'TX_MUTEX', 'TX_SEMAPHORE', 'TX_QUEUE',
                  'TX_EVENT_FLAGS_GROUP', 'TX_TIMER', 'TX_BLOCK_POOL', 'TX_BYTE_POOL']
    
    for type_name in test_types:
        start = time.time()
        type_info = parser.get_struct_type(type_name)
        elapsed = time.time() - start
        
        if type_info:
            print(f"  {type_name}: {elapsed:.3f}s (size={type_info.get('byte_size', 0)} bytes, members={len(type_info.get('members', []))})")
        else:
            print(f"  {type_name}: {elapsed:.3f}s - NOT FOUND")


def profile_plugin_execution(parser, reader, profile):
    print("\n" + "=" * 60)
    print("4. Plugin Execution Performance Profiling")
    print("=" * 60)
    
    start = time.time()
    registry = PluginRegistry()
    plugins = registry.get_plugins_for_profile(profile)
    plugin_load_time = time.time() - start
    
    print(f"\n  Plugin load time: {plugin_load_time:.3f}s")
    print(f"  Number of plugins: {len(plugins)}")
    for plugin in plugins:
        print(f"    - {plugin.name} ({plugin.__class__.__name__})")
    
    context = {
        'elf_parser': parser,
        'dump_reader': reader,
        'profile': profile,
        'results': {},
        'config': {},
        'plugins': plugins,
    }
    
    # Plugin initialize
    start = time.time()
    for plugin in plugins:
        plugin.initialize(context)
    init_time = time.time() - start
    print(f"\n  Plugin initialize time: {init_time:.3f}s")
    
    # Plugin execute with sub-stage breakdown
    # Note: execute() internally calls get_resource() for each type,
    # so we only call execute() and measure the total.
    plugin_results = {}
    for plugin in plugins:
        print(f"\n  --- {plugin.name} execute ---")
        plugin_start = time.time()
        
        try:
            result = plugin.execute(context)
            if result:
                plugin_results[plugin.name] = result
                # Print sub-resource counts from result
                for key, val in result.items():
                    if isinstance(val, list):
                        print(f"    {key}: {len(val)} items")
                    elif isinstance(val, dict) and val:
                        print(f"    {key}: present")
        except Exception as e:
            print(f"    Error executing {plugin.name}: {e}")
            import traceback
            traceback.print_exc()
            plugin_results[plugin.name] = {'error': str(e)}
        
        plugin_time = time.time() - plugin_start
        print(f"    Total execute time: {plugin_time:.3f}s")
    
    return plugin_results, context


def profile_display(context, profile):
    print("\n" + "=" * 60)
    print("5. Display Performance Profiling")
    print("=" * 60)
    
    from display import DisplayFactory
    from display.data_adapter import DataAdapter
    
    t0 = time.time()
    data_adapter = DataAdapter(context)
    t_adapter = time.time() - t0
    print(f"\n  DataAdapter init: {t_adapter:.3f}s")
    
    t0 = time.time()
    display = DisplayFactory.create('cli_basic', profile, data_adapter)
    t_create = time.time() - t0
    print(f"  DisplayFactory.create: {t_create:.3f}s")
    
    t0 = time.time()
    display.run()
    t_run = time.time() - t0
    print(f"\n  display.run(): {t_run:.3f}s")


def main():
    if len(sys.argv) < 4:
        elf_path = 'tests/unisoc/chip1/output/QogirS6_PS_modem.axf'
        dump_path = 'tests/unisoc/chip1/output/2026_07_03_14_19_35_658_1.mem'
        profile_path = 'profiles/unisoc/chip1.yaml'
    else:
        elf_path = sys.argv[1]
        dump_path = sys.argv[2]
        profile_path = sys.argv[3]
    
    print(f"\n{'=' * 60}")
    print("Unisoc Chip1 Dump Analysis - ELFTools Parser Performance Profile")
    print(f"{'=' * 60}")
    print(f"ELF: {elf_path}")
    print(f"Dump: {dump_path}")
    print(f"Profile: {profile_path}")
    
    total_start = time.time()
    
    # Load profile
    loader = ProfileLoader()
    profile = loader.load_profile(profile_path)
    memory_regions = loader.get_memory_regions(profile)
    parser_config = loader.get_parser_config(profile)
    parser_type = parser_config.get('type', 'elftools')
    
    # 1. ELF Parser
    parser = profile_elf_parser(elf_path, parser_type)
    
    # 2. Dump Reader
    reader = profile_dump_reader(dump_path, memory_regions)
    
    # 3. Type Parsing (first-time lazy)
    profile_type_parsing(parser)
    
    # 4. Plugin Execution
    plugin_results, context = profile_plugin_execution(parser, reader, profile)
    
    # 5. Display
    profile_display(context, profile)
    
    total_time = time.time() - total_start
    
    print("\n" + "=" * 60)
    print(f"TOTAL WALL TIME: {total_time:.3f}s")
    print("=" * 60)


if __name__ == '__main__':
    main()