#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


def test_threadx_parsing():
    print("=" * 70)
    print("ThreadX v6.5.1 解析演示")
    print("=" * 70)
    
    firmware_dir = os.path.join(os.path.dirname(__file__), 'tests', 'qemu_m4_threadx', 'firmware')
    elf_path = os.path.join(firmware_dir, 'output', 'img', 'sample_threadx.elf')
    dump_path = os.path.join(firmware_dir, 'output', 'img', 'threadx_ram_dump.bin')
    
    loader = ProfileLoader()
    profile = loader.load_profile('qemu/mps2_an386_threadx')
    regions = loader.get_memory_regions(profile)
    
    elf_parser = ELFParser(elf_path)
    dump_reader = DumpReader(dump_path, regions)
    
    from plugins.rtos.threadx.threadx_v6p5p1 import ThreadXV6Plugin
    rtos_plugin = ThreadXV6Plugin()
    
    context = {
        'elf_parser': elf_parser,
        'dump_reader': dump_reader,
        'profile': profile,
    }
    
    rtos_plugin.initialize(context)
    result = rtos_plugin.execute(context)
    
    print(f"\n[任务列表] 共 {len(result.get('tasks', []))} 个任务")
    for task in result.get('tasks', [])[:5]:
        print(f"  - {task.get('name', ''):<20} 状态:{task.get('state_name', ''):<25} "
              f"优先级:{task.get('priority', 0):<3} 栈使用率:{task.get('stack_usage', 0):.1f}%")
    
    print(f"\n[信号量] 共 {len(result.get('semaphores', []))} 个")
    for sem in result.get('semaphores', []):
        print(f"  - {sem.get('name', ''):<20} count:{sem.get('count', 0):<3}")
    
    print(f"\n[互斥锁] 共 {len(result.get('mutexes', []))} 个")
    for mutex in result.get('mutexes', []):
        owner_info = mutex.get('owner_info')
        owner_name = owner_info.get('name', 'None') if owner_info else 'None'
        print(f"  - {mutex.get('name', ''):<20} 所有者:{owner_name:<15}")
    
    print(f"\n[队列] 共 {len(result.get('queues', []))} 个")
    for queue in result.get('queues', []):
        print(f"  - {queue.get('name', ''):<20} 消息数:{queue.get('enqueued_count', 0):<3}/"
              f"{queue.get('max_entries', 0)}")
    
    print(f"\n[定时器] 共 {len(result.get('timers', []))} 个")
    for timer in result.get('timers', []):
        print(f"  - {timer.get('name', ''):<20} 周期:{timer.get('period_ticks', 0):<6} "
              f"激活:{timer.get('active', False)}")


def test_freertos_parsing():
    print("\n" + "=" * 70)
    print("FreeRTOS v11.3.0 解析演示")
    print("=" * 70)
    
    firmware_dir = os.path.join(os.path.dirname(__file__), 'tests', 'qemu_r52_freertos', 'firmware')
    elf_path = os.path.join(firmware_dir, 'output', 'img', 'test_firmware_freertos.elf')
    dump_path = os.path.join(firmware_dir, 'output', 'img', 'test_dump_freertos.bin')
    
    if not os.path.exists(elf_path) or not os.path.exists(dump_path):
        print("FreeRTOS 固件不存在，跳过")
        return
    
    loader = ProfileLoader()
    profile = loader.load_profile('qemu/mps3_an536_freertos')
    regions = loader.get_memory_regions(profile)
    
    elf_parser = ELFParser(elf_path)
    dump_reader = DumpReader(dump_path, regions)
    
    from plugins.rtos.freertos.freertos_v11p3p0 import FreeRTOSV11Plugin
    rtos_plugin = FreeRTOSV11Plugin()
    
    context = {
        'elf_parser': elf_parser,
        'dump_reader': dump_reader,
        'profile': profile,
    }
    
    rtos_plugin.initialize(context)
    result = rtos_plugin.execute(context)
    
    print(f"\n[任务列表] 共 {len(result.get('tasks', []))} 个任务")
    for task in result.get('tasks', []):
        print(f"  - {task.get('name', ''):<20} 状态:{task.get('state', ''):<15} "
              f"优先级:{task.get('priority', 0):<3} 栈使用率:{task.get('stack_usage', 0):.1f}%")
    
    print(f"\n[信号量] 共 {len(result.get('semaphores', []))} 个")
    for sem in result.get('semaphores', []):
        print(f"  - {sem.get('name', ''):<20} count:{sem.get('count', 0):<3} "
              f"类型:{sem.get('type', '')}")
    
    print(f"\n[互斥锁] 共 {len(result.get('mutexes', []))} 个")
    for mutex in result.get('mutexes', []):
        print(f"  - {mutex.get('name', ''):<20} count:{mutex.get('count', 0):<3} "
              f"所有者:{mutex.get('owner_name', 'None'):<15}")
    
    print(f"\n[队列] 共 {len(result.get('queues', []))} 个")
    for queue in result.get('queues', []):
        print(f"  - {queue.get('name', ''):<20} 消息数:{queue.get('messages_count', 0):<3}/"
              f"{queue.get('messages_max', 0)}")
    
    print(f"\n[定时器] 共 {len(result.get('timers', []))} 个")
    for timer in result.get('timers', []):
        print(f"  - {timer.get('name', ''):<20} 周期:{timer.get('period_ticks', 0):<6} "
              f"激活:{timer.get('active', False)}")


if __name__ == '__main__':
    test_threadx_parsing()
    test_freertos_parsing()
