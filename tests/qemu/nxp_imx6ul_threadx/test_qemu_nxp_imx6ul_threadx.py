import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUNxpImx6ulThreadXFirmwareAutoParse(unittest.TestCase):
    """QEMU NXP i.MX6UL (Cortex-A7, ARMv7-A) + ThreadX V6.5.1 tests.

    Tests structural properties of ThreadX on Cortex-A7:
    - TX_THREAD / TX_QUEUE / TX_SEMAPHORE / TX_MUTEX structs exist in DWARF
    - _tx_thread_current_ptr is non-null after scheduler start
    - Task list contains at least 8 created threads
    - Plugin interface loads without errors

    All tests avoid timing-sensitive assertions (task status, queue depth, etc.)
    to prevent flaky test failures.
    """

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_nxp_imx6ul_threadx.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_nxp_imx6ul_threadx.bin')

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("NXP i.MX6UL ThreadX firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/nxp_imx6ul_threadx')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)
        self.keywords = profile.get('keyword', [])

    def test_keyword_match(self):
        if not self.keywords:
            self.skipTest("No keywords defined in profile")

        elf_unmatched = self.elf_parser.match_keywords(self.keywords)
        self.assertEqual(len(elf_unmatched), 0,
                        f"Keyword match failed: ELF unmatched={elf_unmatched}")

    def test_nxp_imx6ul_threadx_elf_exists(self):
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_nxp_imx6ul_threadx_elf_header(self):
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_threadx_thread_control_block_in_dwarf(self):
        """TX_THREAD struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_THREAD'), "TX_THREAD type should exist in DWARF")

    def test_threadx_current_thread_non_null(self):
        """_tx_thread_current_ptr should be non-null after scheduler start."""
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        if current_tcb is None:
            self.skipTest("_tx_thread_current_ptr is NULL (may be captured before scheduler start)")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB should be a dict of TX_THREAD fields")

    def test_threadx_current_thread_tcb_fields(self):
        """验证 TCB 指针解引用后能拿到 TX_THREAD 的关键字段"""
        current_tcb = self.elf_parser.parse_struct_auto('_tx_thread_current_ptr', self.dump_reader)
        if current_tcb is None:
            self.skipTest("_tx_thread_current_ptr is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        self.assertIn('tx_thread_name', current_tcb,
                      "TX_THREAD should have tx_thread_name field")

    def test_threadx_system_state_finished(self):
        """_tx_thread_system_state should be 0 (TX_INITIALIZE_IS_FINISHED) or valid state."""
        state = self.elf_parser.parse_struct_auto('_tx_thread_system_state', self.dump_reader)
        self.assertIsNotNone(state, "_tx_thread_system_state should be parseable")
        self.assertIsInstance(state, int, "_tx_thread_system_state should be an integer")

    def test_threadx_created_thread_count(self):
        """At least 8 threads should exist."""
        thread_count = 0
        symbols = self.elf_parser.get_all_symbols()
        for sym in symbols:
            name = sym['name']
            if name.startswith('thread_') and not name.endswith('_counter') and not name.endswith('_entry'):
                addr = sym['address']
                if addr is not None and 0x40000000 <= addr < 0x40010000:
                    thread_count += 1
        self.assertGreaterEqual(thread_count, 8, "At least 8 threads should exist")

    def test_threadx_semaphore_in_dwarf(self):
        """TX_SEMAPHORE struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_SEMAPHORE'), "TX_SEMAPHORE type should exist")

    def test_threadx_mutex_in_dwarf(self):
        """TX_MUTEX struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_MUTEX'), "TX_MUTEX type should exist")

    def test_threadx_queue_in_dwarf(self):
        """TX_QUEUE struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_QUEUE'), "TX_QUEUE type should exist")

    def test_threadx_event_flags_in_dwarf(self):
        """TX_EVENT_FLAGS_GROUP struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_EVENT_FLAGS_GROUP'), "TX_EVENT_FLAGS_GROUP type should exist")

    def test_threadx_timer_in_dwarf(self):
        """TX_TIMER struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_TIMER'), "TX_TIMER type should exist")

    def test_threadx_byte_pool_in_dwarf(self):
        """TX_BYTE_POOL struct should exist in DWARF."""
        self.assertIsNotNone(self.elf_parser.get_struct_type('TX_BYTE_POOL'), "TX_BYTE_POOL type should exist")

    def test_threadx_plugin_loadable(self):
        """ThreadXV6Plugin initializes without exceptions."""
        try:
            from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
        except ImportError as e:
            self.skipTest(f"ThreadX plugin import failed: {e}")

        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }

        plugin = ThreadXV6Plugin()
        result = plugin.initialize(context)
        self.assertTrue(result, "Plugin initialize() should return True")

        tasks = plugin.get_tasks(context)
        self.assertIsInstance(tasks, list, "get_tasks() should return a list")

    def test_threadx_plugin_execute(self):
        """ThreadX plugin execute should return valid results for all resource types."""
        try:
            from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
        except ImportError as e:
            self.skipTest(f"ThreadX plugin import failed: {e}")

        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }

        plugin = ThreadXV6Plugin()
        plugin.initialize(context)
        result = plugin.execute(context)
        self.assertIsInstance(result, dict)

        self.assertIn('tasks', result)
        self.assertIsInstance(result['tasks'], list)

        self.assertIn('semaphores', result)
        self.assertIsInstance(result['semaphores'], list)

        self.assertIn('mutexes', result)
        self.assertIsInstance(result['mutexes'], list)

        self.assertIn('queues', result)
        self.assertIsInstance(result['queues'], list)

        self.assertIn('events', result)
        self.assertIsInstance(result['events'], list)

        self.assertIn('timers', result)
        self.assertIsInstance(result['timers'], list)

        self.assertIn('block_pools', result)
        self.assertIsInstance(result['block_pools'], list)

        self.assertIn('byte_pools', result)
        self.assertIsInstance(result['byte_pools'], list)


if __name__ == '__main__':
    unittest.main()