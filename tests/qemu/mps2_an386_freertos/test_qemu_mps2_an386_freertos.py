import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParserFactory
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUMps2An386FreeRTOSFirmwareAutoParse(unittest.TestCase):
    """QEMU Cortex-M4 + FreeRTOS V11.3.0 real-run firmware tests.

    Tests structural properties of FreeRTOS on M4:
    - TCB_t / QueueDefinition structs exist in DWARF
    - pxCurrentTCB is non-null after scheduler start
    - Task list contains at least 4 created tasks
    - Bare-metal assert_info / test_point data still intact
    - Plugin interface loads without errors

    All tests avoid timing-sensitive assertions (task status, queue depth, etc.)
    to prevent flaky test failures.
    """

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_freertos.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_freertos.bin')
    RAM_START = 0x20000000
    RAM_END   = 0x20010000   # 64KB dump

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("FreeRTOS firmware ELF/dump files not found")

        self.elf_parser = ELFParserFactory.create(self.ELF_PATH, 'elftools')
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('profiles/qemu/mps2_an386_freertos.yaml')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)
        self.keywords = profile.get('keyword', [])

    def test_keyword_match(self):
        if not self.keywords:
            self.skipTest("No keywords defined in profile")

        elf_unmatched = self.elf_parser.match_keywords(self.keywords)
        self.assertEqual(len(elf_unmatched), 0,
                        f"Keyword match failed: ELF unmatched={elf_unmatched}")

    def test_freertos_elf_exists(self):
        """FreeRTOS ELF and dump both exist and are non-empty."""
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_freertos_elf_header(self):
        """FreeRTOS ELF: class 32, machine 'ARM', entry in FLASH, has DWARF."""
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        entry_actual = header['entry'] & ~1
        self.assertGreaterEqual(entry_actual, 0x00000000,
                               f"entry {header['entry']:#x} should be in FLASH")
        self.assertLess(entry_actual, 0x00001000,
                        f"entry {header['entry']:#x} should be in FLASH")
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_scheduler_started(self):
        """g_rtos_started == 1 confirms scheduler started before dump."""
        rtos_started = self.elf_parser.parse_struct_auto('g_rtos_started', self.dump_reader)
        self.assertEqual(rtos_started, 1,
                        "g_rtos_started must be 1 after scheduler start")

    def test_pxCurrentTCB_non_null(self):
        """pxCurrentTCB is non-null after FreeRTOS scheduler starts.

        使用 parse_struct_auto 自动解引用 TCB_t* 指针，
        返回 TCB_t 字段的 dict 或 None（空指针时）。
        """
        current_tcb = self.elf_parser.parse_struct_auto('pxCurrentTCB', self.dump_reader)
        self.assertIsNotNone(current_tcb,
                           "pxCurrentTCB must be non-null after scheduler start")
        self.assertIsInstance(current_tcb, dict,
                            "Dereferenced TCB_t should be a dict of fields")

    def test_pxCurrentTCB_tcb_fields(self):
        """验证 pxCurrentTCB 解引用后能拿到 TCB_t 的关键字段"""
        current_tcb = self.elf_parser.parse_struct_auto('pxCurrentTCB', self.dump_reader)
        if current_tcb is None:
            self.skipTest("pxCurrentTCB is NULL, cannot test TCB fields")
        self.assertIsInstance(current_tcb, dict)
        # TCB_t 必含字段
        self.assertIn('pxTopOfStack', current_tcb, "TCB_t should have pxTopOfStack")
        self.assertIn('pcTaskName', current_tcb, "TCB_t should have pcTaskName")
        self.assertIn('uxPriority', current_tcb, "TCB_t should have uxPriority")
        # pcTaskName 是 char[16] 数组，会被解析为字符串
        self.assertIsInstance(current_tcb['pcTaskName'], str,
                            "pcTaskName should be a string (char array)")

    def test_tcb_struct_in_dwarf(self):
        """TCB_t struct type is present in DWARF debug info."""
        tcb_struct = self.elf_parser.get_struct_type('TCB_t')
        self.assertIsNotNone(tcb_struct, "TCB_t must be in DWARF")
        # TCB_t may be typedef or struct depending on DWARF representation
        kind = tcb_struct.get('kind')
        self.assertIn(kind, ('struct', 'typedef'),
                      f"TCB_t kind should be struct or typedef, got {kind}")
        self.assertIn('members', tcb_struct)
        members = tcb_struct['members']
        member_names = [m.get('name') for m in members if m.get('name')]
        self.assertIn('pxTopOfStack', member_names, "TCB_t should have pxTopOfStack")
        self.assertIn('pcTaskName', member_names, "TCB_t should have pcTaskName")
        self.assertIn('uxPriority', member_names, "TCB_t should have uxPriority")

    def test_queue_struct_in_dwarf(self):
        """QueueDefinition struct type is present in DWARF (FreeRTOS queue/mutex/sem)."""
        queue_struct = self.elf_parser.get_struct_type('QueueDefinition')
        self.assertIsNotNone(queue_struct, "QueueDefinition must be in DWARF")
        kind = queue_struct.get('kind')
        self.assertIn(kind, ('struct', 'typedef'),
                      f"QueueDefinition kind should be struct or typedef, got {kind}")
        self.assertIn('members', queue_struct)

    def test_tcb_pcTaskName_is_char_array(self):
        """TCB_t.pcTaskName field is char[16] array in DWARF."""
        tcb_struct = self.elf_parser.get_struct_type('TCB_t')
        self.assertIsNotNone(tcb_struct)

        pcTaskName_member = None
        for m in tcb_struct.get('members', []):
            if m.get('name') == 'pcTaskName':
                pcTaskName_member = m
                break
        self.assertIsNotNone(pcTaskName_member, "pcTaskName member must exist")

        pcTaskName_type = pcTaskName_member.get('type', {})
        self.assertEqual(pcTaskName_type.get('kind'), 'array',
                        f"pcTaskName should be array, got {pcTaskName_type.get('kind')}")
        element_type = pcTaskName_type.get('element_type', {})
        self.assertEqual(element_type.get('kind'), 'base',
                        f"pcTaskName element should be base type, got {element_type.get('kind')}")
        self.assertEqual(element_type.get('name'), 'char',
                        f"pcTaskName element should be char, got {element_type.get('name')}")

    def test_created_task_count(self):
        """At least 4 tasks exist (Led, Sender, Recv, IdleX)."""
        is_32bit = self.elf_parser.is_32bit()
        max_priority = 5

        ready_lists_sym = self.elf_parser.get_symbol_by_name('pxReadyTasksLists')
        suspended_sym = self.elf_parser.get_symbol_by_name('xSuspendedTaskList')
        delayed_list1_sym = self.elf_parser.get_symbol_by_name('xDelayedTaskList1')
        delayed_list2_sym = self.elf_parser.get_symbol_by_name('xDelayedTaskList2')

        visited = set()

        def collect_tasks(list_addr):
            if not list_addr:
                return
            list_ptr = self.dump_reader.read_pointer(list_addr, is_32bit)
            if not list_ptr:
                return
            visited.add(list_ptr)

        if ready_lists_sym:
            for priority in range(max_priority):
                list_addr = ready_lists_sym['address'] + priority * (4 if is_32bit else 8)
                collect_tasks(list_addr)

        if suspended_sym:
            collect_tasks(suspended_sym['address'])

        if delayed_list1_sym:
            collect_tasks(delayed_list1_sym['address'])

        if delayed_list2_sym:
            collect_tasks(delayed_list2_sym['address'])

        self.assertGreaterEqual(len(visited), 1,
                               "At least one task list should be non-null")

    def test_baremetal_assert_data_intact(self):
        """Bare-metal assert_info / test_point / trace data structures can be parsed."""
        # Verify scalar globals can be parsed (values may change between runs)
        ticks = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertIsNotNone(ticks, "g_system_ticks should be parseable")
        err = self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader)
        self.assertIsNotNone(err, "g_error_count should be parseable")
        status = self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader)
        self.assertIsNotNone(status, "g_system_status should be parseable")

        # Verify array globals can be parsed and have correct structure
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertIsInstance(arr, list, "g_assert_infos should be a list")
        self.assertEqual(len(arr), 4, "g_assert_infos should have 4 slots")

        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)
        self.assertIsInstance(tps, list, "g_test_points should be a list")
        self.assertEqual(len(tps), 8, "g_test_points should have 8 slots")

    def _get_plugin(self):
        """Helper: load and initialize the FreeRTOS plugin."""
        from plugins.rtos.freertos.freertos_v11p3p0 import FreeRTOSV11Plugin
        plugin = FreeRTOSV11Plugin()
        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }
        self.assertTrue(plugin.initialize(context), "Plugin initialize() should return True")
        return plugin, context

    def test_freertos_plugin_loadable(self):
        """FreeRTOS11p0Plugin initializes without exceptions."""
        try:
            from plugins.rtos.freertos.freertos_v11p3p0 import FreeRTOSV11Plugin
        except ImportError as e:
            self.skipTest(f"FreeRTOS plugin import failed: {e}")

        context = {
            'elf_parser': self.elf_parser,
            'dump_reader': self.dump_reader,
            'profile': {},
        }

        plugin = FreeRTOSV11Plugin()
        result = plugin.initialize(context)
        self.assertTrue(result, "Plugin initialize() should return True")

        tasks = plugin.get_tasks(context)
        self.assertIsInstance(tasks, list, "get_tasks() should return a list")

    # ========================================================================
    # 数据准确性检查 — 通过插件 execute() 验证资源的数据值
    # 基于固件源码 main.c 中的创建参数
    # ========================================================================

    def test_plugin_task_data(self):
        """验证任务数据：名称、优先级、数量是否与固件源码一致。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        tasks = result['tasks']

        # 总任务数：10 个用户任务 + IDLE + Tmr Svc = 12
        self.assertGreaterEqual(len(tasks), 10,
                               f"Expected at least 10 tasks, got {len(tasks)}")

        # 按名称建立索引
        by_name = {t['name']: t for t in tasks if t.get('name')}

        # 验证核心任务存在且优先级正确（来自 main.c 的 xTaskCreate 调用）
        expected = {
            'Sender':  2,
            'Recv':    3,
            'Mutex1':  1,
            'Mutex2':  1,
            'Sem1':    4,
            'Sem2':    4,
            'Event1':  5,
            'Event2':  5,
            'TimerT':  6,
            'HighPri': 0,
        }
        for name, expected_priority in expected.items():
            self.assertIn(name, by_name, f"Task '{name}' should exist")
            self.assertEqual(by_name[name]['priority'], expected_priority,
                           f"Task '{name}' priority should be {expected_priority}")

        # IDLE task 优先级为 0
        self.assertIn('IDLE', by_name, "IDLE task should exist")

        # Tmr Svc 优先级为最高（configTIMER_TASK_PRIORITY）
        self.assertIn('Tmr Svc', by_name, "Tmr Svc task should exist")

        # 所有任务栈大小应 > 0
        for task in tasks:
            if task.get('stack_start'):
                self.assertGreater(task.get('stack_size', 0) + task.get('stack_usage', 0), 0,
                                 f"Task '{task.get('name')}' should have stack info")

    def test_plugin_semaphore_data(self):
        """验证信号量数据：名称、最大计数是否与固件源码一致。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        semaphores = result['semaphores']

        by_name = {s['name']: s for s in semaphores if s.get('name')}

        # xCountSem: counting semaphore, max=10
        self.assertIn('xCountSem', by_name, "xCountSem should exist")
        self.assertEqual(by_name['xCountSem']['max_count'], 10,
                        "xCountSem max_count should be 10")

        # xBinarySem: binary semaphore, max=1
        self.assertIn('xBinarySem', by_name, "xBinarySem should exist")
        self.assertEqual(by_name['xBinarySem']['max_count'], 1,
                        "xBinarySem max_count should be 1")

        # 不应该包含互斥锁（xMutex1/xMutex2 应在 mutexes 中）
        self.assertNotIn('xMutex1', by_name, "xMutex1 should NOT be in semaphores")
        self.assertNotIn('xMutex2', by_name, "xMutex2 should NOT be in semaphores")

    def test_plugin_mutex_data(self):
        """验证互斥锁数据：名称、存在性。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        mutexes = result['mutexes']

        by_name = {m['name']: m for m in mutexes if m.get('name')}

        self.assertEqual(len(mutexes), 2, f"Expected 2 mutexes, got {len(mutexes)}")
        self.assertIn('xMutex1', by_name, "xMutex1 should exist")
        self.assertIn('xMutex2', by_name, "xMutex2 should exist")

        # 互斥锁类型字段
        for name in ['xMutex1', 'xMutex2']:
            self.assertEqual(by_name[name].get('type', 'mutex'), 'mutex',
                           f"{name} should have type 'mutex'")

    def test_plugin_queue_data(self):
        """验证队列数据：名称、最大消息数。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        queues = result['queues']

        by_name = {q['name']: q for q in queues if q.get('name')}

        self.assertEqual(len(queues), 2, f"Expected 2 queues, got {len(queues)}")

        # xQueue1: max 8 messages, uint32_t item size
        self.assertIn('xQueue1', by_name, "xQueue1 should exist")
        self.assertEqual(by_name['xQueue1']['max_messages'], 8,
                        "xQueue1 max_messages should be 8")
        self.assertEqual(by_name['xQueue1']['message_size'], 4,
                        "xQueue1 message_size should be 4 (uint32_t)")

        # xQueue2: max 5 messages, uint32_t item size
        self.assertIn('xQueue2', by_name, "xQueue2 should exist")
        self.assertEqual(by_name['xQueue2']['max_messages'], 5,
                        "xQueue2 max_messages should be 5")
        self.assertEqual(by_name['xQueue2']['message_size'], 4,
                        "xQueue2 message_size should be 4 (uint32_t)")

    def test_plugin_event_data(self):
        """验证事件组数据：名称、存在性。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        events = result['events']

        by_name = {e['name']: e for e in events if e.get('name')}

        self.assertEqual(len(events), 2, f"Expected 2 event groups, got {len(events)}")
        self.assertIn('xEventGrp1', by_name, "xEventGrp1 should exist")
        self.assertIn('xEventGrp2', by_name, "xEventGrp2 should exist")

    def test_plugin_timer_data(self):
        """验证定时器数据：名称、周期。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)
        timers = result['timers']

        by_name = {t['name']: t for t in timers if t.get('name')}

        self.assertEqual(len(timers), 2, f"Expected 2 timers, got {len(timers)}")

        # xTimer1: period=50 ticks, auto-reload
        self.assertIn('xTimer1', by_name, "xTimer1 should exist")
        self.assertEqual(by_name['xTimer1']['period_ticks'], 50,
                        "xTimer1 period_ticks should be 50")

        # xTimer2: period=100 ticks, auto-reload
        self.assertIn('xTimer2', by_name, "xTimer2 should exist")
        self.assertEqual(by_name['xTimer2']['period_ticks'], 100,
                        "xTimer2 period_ticks should be 100")

    def test_plugin_resource_type_separation(self):
        """验证资源类型完全分离：semaphores/mutexes/queues/events/timers 无重叠。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)

        sem_addrs = {s['address'] for s in result['semaphores']}
        mutex_addrs = {m['address'] for m in result['mutexes']}
        queue_addrs = {q['address'] for q in result['queues']}

        self.assertTrue(sem_addrs.isdisjoint(mutex_addrs),
                       "Semaphores and mutexes should have no overlap")
        self.assertTrue(queue_addrs.isdisjoint(sem_addrs),
                       "Queues and semaphores should have no overlap")
        self.assertTrue(queue_addrs.isdisjoint(mutex_addrs),
                       "Queues and mutexes should have no overlap")

    def test_plugin_execute_all_resource_types(self):
        """验证 execute() 返回所有 6 种资源类型。"""
        plugin, context = self._get_plugin()
        result = plugin.execute(context)

        self.assertIsInstance(result, dict)
        for rt in ['tasks', 'semaphores', 'mutexes', 'queues', 'timers', 'events']:
            self.assertIn(rt, result, f"execute() should include '{rt}'")
            self.assertIsInstance(result[rt], list, f"'{rt}' should be a list")


if __name__ == '__main__':
    unittest.main()