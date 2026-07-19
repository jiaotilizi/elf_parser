import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUStStm32vldiscoveryFirmwareAutoParse(unittest.TestCase):
    """QEMU STM32VLDISCOVERY (Cortex-M3) bare metal 测试"""

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_stm32.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_stm32.bin')
    RAM_START = 0x20000000
    RAM_END = 0x20005000

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("STM32 firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/st_stm32vldiscovery_bare')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)

    def test_stm32_elf_exists(self):
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_stm32_elf_header(self):
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_stm32_scalar_values(self):
        ticks = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertIsInstance(ticks, int)
        self.assertGreater(ticks, 0)

    def test_stm32_test_points_array(self):
        sym = self.elf_parser.get_symbol_by_name('test_points')
        if sym is None:
            self.skipTest("test_points symbol not found")
        
        tps = self.elf_parser.parse_struct_auto('test_points', self.dump_reader)
        self.assertIsInstance(tps, list)
        self.assertEqual(len(tps), 5)

        expected_names = ['init', 'config', 'ready', 'run', 'done']
        for i, tp in enumerate(tps):
            self.assertEqual(tp['id'], i + 1)
            self.assertEqual(tp['name'], expected_names[i])

    def test_stm32_keyword_match(self):
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/st_stm32vldiscovery_bare')
        keywords = profile.get('keyword', [])
        
        if keywords:
            unmatched = self.elf_parser.match_keywords(keywords)
            self.assertLessEqual(len(unmatched), 2)


if __name__ == '__main__':
    unittest.main()
