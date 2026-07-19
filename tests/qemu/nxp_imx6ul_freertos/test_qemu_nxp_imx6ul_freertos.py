import os
import unittest

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader
from plugins.rtos.freertos.freertos_v11p3p0 import FreeRTOSV11Plugin


class TestQEMUNxpImx6ulFreeRTOSFirmwareAutoParse(unittest.TestCase):
    """QEMU NXP i.MX6UL (Cortex-A7, ARMv7-A) + FreeRTOS test"""

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_nxp_imx6ul_freertos.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_nxp_imx6ul_freertos.bin')

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("NXP i.MX6UL FreeRTOS firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/nxp_imx6ul_freertos')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)

    def test_nxp_imx6ul_freertos_elf_exists(self):
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_nxp_imx6ul_freertos_elf_header(self):
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_nxp_imx6ul_freertos_keyword_match(self):
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/nxp_imx6ul_freertos')
        keywords = profile.get('keyword', [])

        if keywords:
            unmatched = self.elf_parser.match_keywords(keywords)
            self.assertLessEqual(len(unmatched), 2)


if __name__ == '__main__':
    unittest.main()
