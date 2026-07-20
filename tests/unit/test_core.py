import os
import sys
import unittest
import tempfile
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dump_reader import DumpReader, MemoryRegion
from core.profile_loader import ProfileLoader
from core.plugin_registry import PluginRegistry
from plugins.rtos.base import RTOSPlugin
from plugins.module.base import ModulePlugin


class TestDumpReader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dump_data = bytearray(0x1000)
        for i in range(0x1000):
            self.dump_data[i] = i % 256

        self.dump_path = os.path.join(self.temp_dir, 'test_dump.bin')
        with open(self.dump_path, 'wb') as f:
            f.write(self.dump_data)

    def tearDown(self):
        os.remove(self.dump_path)
        os.rmdir(self.temp_dir)

    def test_read_uint8(self):
        reader = DumpReader(self.dump_path)
        for i in range(0x100):
            self.assertEqual(reader.read_uint8(i), i % 256)

    def test_read_uint32(self):
        reader = DumpReader(self.dump_path)
        for i in range(0, 0x100, 4):
            expected = i | ((i+1) << 8) | ((i+2) << 16) | ((i+3) << 24)
            self.assertEqual(reader.read_uint32(i), expected)

    def test_read_memory(self):
        reader = DumpReader(self.dump_path)
        data = reader.read_memory(0x100, 0x20)
        self.assertEqual(len(data), 0x20)
        for i in range(0x20):
            self.assertEqual(data[i], (0x100 + i) % 256)

    def test_multi_region(self):
        regions = [
            {'name': 'ram', 'start_addr': 0x88000000, 'size': 0x800},
            {'name': 'llram', 'start_addr': 0x8A000000, 'size': 0x400},
        ]
        reader = DumpReader(self.dump_path, regions)
        self.assertEqual(reader.read_uint8(0x88000000), 0)
        self.assertEqual(reader.read_uint8(0x880007FF), 0x7FF % 256)
        self.assertEqual(reader.read_uint8(0x8A000000), 0x800 % 256)
        self.assertEqual(reader.read_uint8(0x8A0003FF), (0x800 + 0x3FF) % 256)

    def test_read_string(self):
        test_str = b"Hello, World!\x00"
        with open(self.dump_path, 'wb') as f:
            f.write(test_str + b'\x00' * (0x1000 - len(test_str)))

        reader = DumpReader(self.dump_path)
        self.assertEqual(reader.read_string(0), "Hello, World!")

    def test_read_pointer(self):
        ptr_value = 0x88001234
        with open(self.dump_path, 'wb') as f:
            f.write(struct.pack('<I', ptr_value) + b'\x00' * (0x1000 - 4))

        reader = DumpReader(self.dump_path)
        self.assertEqual(reader.read_pointer(0, True), ptr_value)


class TestPluginRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = PluginRegistry()

    def test_load_os_plugin(self):
        plugin = self.registry.load_plugin('rtos.threadx.threadx_v6p5p1')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'threadx_v6p5p1')
        self.assertIsInstance(plugin, RTOSPlugin)

    def test_load_module_plugin(self):
        plugin = self.registry.load_plugin('module.assert_info.assert_info_v0')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'assert_info')
        self.assertIsInstance(plugin, ModulePlugin)

    def test_load_nonexistent_plugin(self):
        with self.assertRaises(ValueError):
            self.registry.load_plugin('rtos.nonexistent.plugin')

    def test_list_plugins(self):
        plugins = self.registry.list_plugins()
        self.assertGreater(len(plugins), 0)
        plugin_paths = [p['path'] for p in plugins]
        self.assertIn('rtos.threadx.threadx_v6p5p1', plugin_paths)
        self.assertIn('module.assert_info.assert_info_v0', plugin_paths)


class TestProfileLoader(unittest.TestCase):
    def test_list_profiles(self):
        loader = ProfileLoader()
        profiles = loader.list_profiles()

        self.assertGreater(len(profiles), 0)

        profile_names = [p['name'] for p in profiles]
        self.assertIn('nxp/demo_chip', profile_names)

    def test_load_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/nxp/demo_chip.yaml')

        self.assertIsNotNone(profile)
        self.assertEqual(profile['chip']['name'], 'demo_chip')

    def test_load_qemu_m4_bare_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/qemu/mps2_an386_bare.yaml')

        self.assertIsNotNone(profile)
        self.assertIn('memory', profile)
        self.assertTrue(len(profile['memory']) > 0)

    def test_load_bss_simulated_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/bss_simulated.yaml')

        self.assertIsNotNone(profile)
        self.assertIn('memory', profile)

    def test_get_memory_regions(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/nxp/demo_chip.yaml')

        regions = loader.get_memory_regions(profile)
        self.assertTrue(len(regions) > 0)
        self.assertIn('name', regions[0])
        self.assertIn('start_addr', regions[0])
        self.assertIn('size', regions[0])

    def test_validate_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/nxp/demo_chip.yaml')

        errors = loader.validate_profile(profile)
        self.assertEqual(len(errors), 0)

    def test_load_plugins_from_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/qemu/mps2_an386_threadx.yaml')

        registry = PluginRegistry()
        plugins = registry.get_plugins_for_profile(profile)
        self.assertTrue(len(plugins) > 0)
        
        plugin_names = [p.name for p in plugins]
        self.assertIn('threadx_v6p5p1', plugin_names)


class TestMemoryRegion(unittest.TestCase):
    def test_contains(self):
        region = MemoryRegion('ram', 0x20000000, 0x10000)
        self.assertTrue(region.contains(0x20000000))
        self.assertTrue(region.contains(0x2000FFFF))
        self.assertFalse(region.contains(0x1FFFFFFF))
        self.assertFalse(region.contains(0x20010000))

    def test_to_dump_offset(self):
        region = MemoryRegion('ram', 0x20000000, 0x10000, 0x100)
        self.assertEqual(region.to_dump_offset(0x20000000), 0x100)
        self.assertEqual(region.to_dump_offset(0x20000100), 0x200)
