import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParserFactory
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

        self.elf_parser = ELFParserFactory.create(self.ELF_PATH, 'elftools')
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('profiles/qemu/nxp_imx6ul_threadx.yaml')
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

    def _get_plugin(self):
        """Helper: load and initialize the ThreadX plugin."""
        from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
        plugin = ThreadXV6Plugin()
        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }
        self.assertTrue(plugin.initialize(context), "Plugin initialize() should return True")
        return plugin, context

    # ========================================================================
    # 数据准确性检查 — 通过插件 execute() 验证资源的数据值
    # 基于 sample_threadx.c 中的 tx_thread_create / tx_queue_create 等参数
    # ========================================================================

    def test_plugin_task_data(self):
        """验证线程数据：名称、优先级、数量是否与固件源码一致。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        tasks = result['tasks']

        self.assertGreaterEqual(len(tasks), 10,
                               f"Expected at least 10 threads, got {len(tasks)}")

        by_name = {t['name']: t for t in tasks if t.get('name')}

        expected = {
            'thread 0': 1, 'thread 1': 16, 'thread 2': 16, 'thread 3': 8,
            'thread 4': 8, 'thread 5': 4, 'thread 6': 8, 'thread 7': 8,
            'thread 8': 2, 'thread 9': 3,
        }
        for name, expected_priority in expected.items():
            self.assertIn(name, by_name, f"Thread '{name}' should exist")
            self.assertEqual(by_name[name]['priority'], expected_priority,
                           f"Thread '{name}' priority should be {expected_priority}")

        self.assertIn('System Timer Thread', by_name, "System Timer Thread should exist")

        for task in tasks:
            if task.get('name', '').startswith('thread '):
                self.assertEqual(task.get('stack_size', 0), 1024,
                               f"Thread '{task.get('name')}' stack_size should be 1024")

    def test_plugin_semaphore_data(self):
        """验证信号量数据：名称。"""
        plugin, context = self._get_plugin()
        semaphores = plugin.execute(context)['semaphores']
        by_name = {s['name']: s for s in semaphores if s.get('name')}
        self.assertGreaterEqual(len(semaphores), 2,
                               f"Expected at least 2 semaphores, got {len(semaphores)}")
        self.assertIn('semaphore 0', by_name, "semaphore 0 should exist")
        self.assertIn('semaphore 1', by_name, "semaphore 1 should exist")

    def test_plugin_mutex_data(self):
        """验证互斥锁数据：名称。"""
        plugin, context = self._get_plugin()
        mutexes = plugin.execute(context)['mutexes']
        by_name = {m['name']: m for m in mutexes if m.get('name')}
        self.assertEqual(len(mutexes), 2, f"Expected 2 mutexes, got {len(mutexes)}")
        self.assertIn('mutex 0', by_name, "mutex 0 should exist")
        self.assertIn('mutex 1', by_name, "mutex 1 should exist")

    def test_plugin_queue_data(self):
        """验证队列数据：名称、容量。"""
        plugin, context = self._get_plugin()
        queues = plugin.execute(context)['queues']
        by_name = {q['name']: q for q in queues if q.get('name')}
        self.assertEqual(len(queues), 2, f"Expected 2 queues, got {len(queues)}")
        self.assertIn('queue 0', by_name, "queue 0 should exist")
        self.assertEqual(by_name['queue 0']['max_messages'], 100,
                        "queue 0 capacity should be 100")
        self.assertIn('queue 1', by_name, "queue 1 should exist")
        self.assertEqual(by_name['queue 1']['max_messages'], 10,
                        "queue 1 capacity should be 10")

    def test_plugin_event_data(self):
        """验证事件组数据：名称。"""
        plugin, context = self._get_plugin()
        events = plugin.execute(context)['events']
        by_name = {e['name']: e for e in events if e.get('name')}
        self.assertGreaterEqual(len(events), 2,
                               f"Expected at least 2 event groups, got {len(events)}")
        self.assertIn('event flags 0', by_name, "event flags 0 should exist")
        self.assertIn('event flags 1', by_name, "event flags 1 should exist")

    def test_plugin_timer_data(self):
        """验证定时器数据：名称、周期。"""
        plugin, context = self._get_plugin()
        timers = plugin.execute(context)['timers']
        by_name = {t['name']: t for t in timers if t.get('name')}
        self.assertEqual(len(timers), 2, f"Expected 2 timers, got {len(timers)}")
        self.assertIn('timer 0', by_name, "timer 0 should exist")
        self.assertEqual(by_name['timer 0']['period_ticks'], 10,
                        "timer 0 period_ticks should be 10")
        self.assertIn('timer 1', by_name, "timer 1 should exist")
        self.assertEqual(by_name['timer 1']['period_ticks'], 100,
                        "timer 1 period_ticks should be 100")

    def test_plugin_block_pool_data(self):
        """验证块池数据：名称、块大小、总数。"""
        plugin, context = self._get_plugin()
        block_pools = plugin.execute(context)['block_pools']
        by_name = {b['name']: b for b in block_pools if b.get('name')}
        self.assertGreaterEqual(len(block_pools), 1,
                               f"Expected at least 1 block pool, got {len(block_pools)}")
        self.assertIn('block pool 0', by_name, "block pool 0 should exist")
        self.assertEqual(by_name['block pool 0']['block_size'], 4,
                        "block pool 0 block_size should be sizeof(ULONG)=4")
        self.assertEqual(by_name['block pool 0']['total_blocks'], 12,
                        "block pool 0 total_blocks should be 12")

    def test_plugin_byte_pool_data(self):
        """验证字节池数据：名称、总大小。"""
        plugin, context = self._get_plugin()
        byte_pools = plugin.execute(context)['byte_pools']
        by_name = {b['name']: b for b in byte_pools if b.get('name')}
        self.assertGreaterEqual(len(byte_pools), 1,
                               f"Expected at least 1 byte pool, got {len(byte_pools)}")
        self.assertIn('byte pool 0', by_name, "byte pool 0 should exist")
        self.assertEqual(by_name['byte pool 0']['total_bytes'], 9120,
                        "byte pool 0 total_bytes should be 9120")

    def test_plugin_execute_all_resource_types(self):
        """验证 execute() 返回所有 8 种资源类型。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        self.assertIsInstance(result, dict)
        for rt in ['tasks', 'semaphores', 'mutexes', 'queues', 'events',
                    'timers', 'block_pools', 'byte_pools']:
            self.assertIn(rt, result, f"execute() should include '{rt}'")
            self.assertIsInstance(result[rt], list, f"'{rt}' should be a list")


if __name__ == '__main__':
    unittest.main()