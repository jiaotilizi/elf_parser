import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUM4ThreadXFirmwareAutoParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.firmware_dir = os.path.join(os.path.dirname(__file__), 'firmware')
        cls.elf_path = os.path.join(cls.firmware_dir, 'output', 'img', 'sample_threadx.elf')
        cls.dump_path = os.path.join(cls.firmware_dir, 'output', 'img', 'threadx_ram_dump.bin')

        assert os.path.exists(cls.elf_path), f"ELF not found: {cls.elf_path}"
        assert os.path.exists(cls.dump_path), f"Dump not found: {cls.dump_path}"

        loader = ProfileLoader()
        profile = loader.load_profile('qemu/m4_threadx')
        regions = loader.get_memory_regions(profile)

        cls.elf_parser = ELFParser(cls.elf_path)
        cls.dump_reader = DumpReader(cls.dump_path, regions)

    def test_threadx_thread_control_block_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_THREAD'),
                             "TX_THREAD type should exist in DWARF")

    def test_threadx_current_thread_non_null(self):
        # 使用 parse_struct_auto 自动解引用 TX_THREAD* 指针，返回 dict 或 None
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        self.assertIsNotNone(current_tcb, "Current thread pointer should not be NULL")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB should be a dict of TX_THREAD fields")

    def test_threadx_current_thread_tcb_fields(self):
        """验证 TCB 指针解引用后能拿到 TX_THREAD 的关键字段"""
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        if current_tcb is None:
            self.skipTest("_tx_thread_current_ptr is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        # TX_THREAD 必含字段：tx_thread_name (char[32])
        self.assertIn('tx_thread_name', current_tcb,
                      "TX_THREAD should have tx_thread_name field")

    def test_threadx_created_thread_count(self):
        thread_count = 0
        symbols = self.elf_parser.get_all_symbols()
        for sym in symbols:
            name = sym['name']
            if name.startswith('thread_') and not name.endswith('_counter') and not name.endswith('_entry'):
                addr = sym['address']
                if addr is not None and 0x20000000 <= addr < 0x20800000:
                    thread_count += 1
        self.assertGreaterEqual(thread_count, 8, "At least 8 threads should exist")

    def test_threadx_semaphore_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_SEMAPHORE'),
                             "TX_SEMAPHORE type should exist")

    def test_threadx_mutex_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_MUTEX'),
                             "TX_MUTEX type should exist")

    def test_threadx_queue_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_QUEUE'),
                             "TX_QUEUE type should exist")

    def test_threadx_event_flags_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_EVENT_FLAGS_GROUP'),
                             "TX_EVENT_FLAGS_GROUP type should exist")

    def test_threadx_byte_pool_in_dwarf(self):
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_BYTE_POOL'),
                             "TX_BYTE_POOL type should exist")


if __name__ == '__main__':
    unittest.main()
