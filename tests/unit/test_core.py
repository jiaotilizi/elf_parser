import os
import sys
import unittest
import tempfile
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dump_reader import DumpReader, MemoryRegion
from core.plugin_manager import PluginManager
from core.profile_loader import ProfileLoader


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
            {'name': 'iram', 'start_addr': 0x8A010000, 'size': 0x400},
        ]
        reader = DumpReader(self.dump_path, regions)

        self.assertEqual(reader.read_uint8(0x88000000), 0x00)
        self.assertEqual(reader.read_uint8(0x880000FF), 0xFF)
        self.assertEqual(reader.read_uint8(0x8A000000), 0x00)
        self.assertEqual(reader.read_uint8(0x8A0003FF), 255)
        self.assertEqual(reader.read_uint8(0x8A010000), 0x00)
        self.assertEqual(reader.read_uint8(0x8A0103FF), 255)

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


class TestPluginManager(unittest.TestCase):
    def test_plugin_discovery(self):
        pm = PluginManager()
        pm.discover_plugins()

        self.assertGreater(len(pm.plugins), 0)
        self.assertIn('assert_info_demo', pm.plugins)
        self.assertIn('test_point_demo', pm.plugins)
        self.assertIn('threadx_v5p6p0', pm.os_plugins)
        self.assertIn('freertos_v11p3p0', pm.os_plugins)

    def test_get_os_plugin(self):
        pm = PluginManager()
        pm.discover_plugins()

        plugin = pm.get_os_plugin('threadx', 'v5p6p0')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'threadx_v5p6p0')

        plugin = pm.get_os_plugin('freertos', 'v11p3p0')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'freertos_v11p3p0')

    def test_get_module_plugin(self):
        pm = PluginManager()
        pm.discover_plugins()

        plugin = pm.get_module_plugin('assert_info_demo')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'assert_info_demo')


class TestProfileLoader(unittest.TestCase):
    def test_list_profiles(self):
        loader = ProfileLoader()
        profiles = loader.list_profiles()

        self.assertGreater(len(profiles), 0)

        profile_names = [p['name'] for p in profiles]
        self.assertIn('nxp/demo_chip', profile_names)
        self.assertIn('unisoc/S6', profile_names)
        self.assertIn('bss_simulated', profile_names)
        self.assertIn('qemu/m4_bare', profile_names)

    def test_load_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('nxp/demo_chip')

        self.assertIsNotNone(profile)
        self.assertEqual(profile['chip']['name'], 'demo_chip')
        self.assertEqual(profile['os']['name'], 'threadx')
        self.assertEqual(profile['os']['version'], 'v5p6p0')

    def test_load_bss_simulated_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('bss_simulated')

        self.assertIsNotNone(profile)
        self.assertEqual(profile['chip']['name'], 'bss_simulated')
        self.assertEqual(profile['os']['name'], 'baremetal')
        self.assertIn('memory', profile)

    def test_load_qemu_m4_bare_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('qemu/m4_bare')

        self.assertIsNotNone(profile)
        self.assertEqual(profile['chip']['name'], 'qemu_m4_bare')
        self.assertEqual(profile['chip']['cpu'], 'cortex-m4')
        self.assertEqual(profile['os']['name'], 'baremetal')
        self.assertIn('qemu', profile)
        self.assertEqual(profile['qemu']['machine'], 'mps2-an386')

    def test_get_memory_regions(self):
        loader = ProfileLoader()
        profile = loader.load_profile('nxp/demo_chip')
        regions = loader.get_memory_regions(profile)

        self.assertEqual(len(regions), 3)
        self.assertEqual(regions[0]['name'], 'ram')
        self.assertEqual(regions[0]['start_addr'], 0x88000000)

    def test_validate_profile(self):
        loader = ProfileLoader()
        profile = loader.load_profile('nxp/demo_chip')
        errors = loader.validate_profile(profile)

        self.assertEqual(len(errors), 0)


class TestMemoryRegion(unittest.TestCase):
    def test_contains(self):
        region = MemoryRegion('ram', 0x88000000, 0x1000)

        self.assertTrue(region.contains(0x88000000))
        self.assertTrue(region.contains(0x88000FFF))
        self.assertFalse(region.contains(0x87FFFFF))
        self.assertFalse(region.contains(0x88001000))

    def test_to_dump_offset(self):
        region = MemoryRegion('ram', 0x88000000, 0x1000, 0x200)

        self.assertEqual(region.to_dump_offset(0x88000000), 0x200)
        self.assertEqual(region.to_dump_offset(0x88000500), 0x700)


if __name__ == '__main__':
    unittest.main()
