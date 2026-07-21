"""ELFParser 跨架构泛用性合成测试。

不依赖 QEMU 也不依赖外部工具链，通过构造合成 dump + 直接调用
`_read_typed_value` 验证：
  - 32 位指针返回 8 hex 宽的字符串
  - 64 位指针返回 16 hex 宽的字符串（验证 elf_parser.py L443-452 修复）
  - 64 位 char* 自动解引用为字符串
  - 0 值 char* 返回 None（而非 `<ptr 0x0...>`）
  - 异常 byte_size（如 2）走 fallback 路径不崩
  - _address_size 与 byte_size 一致性

这个测试是 Phase 1.1 修复（按指针 byte_size 选 4/8 字节读取）的回归保护：
如果有人误改回硬编码 read_uint32，64 位用例会立即失败。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParserFactory
from core.elf_parser.elftools_parser import ElftoolsParser
from core.dump_reader import DumpReader


class TestELFParserUniversality(unittest.TestCase):
    """跨架构指针解析的合成测试，无需真实 ELF/DWARF。"""

    def setUp(self):
        # 跳过 __init__ 的 ELF 解析，直接造一个空壳实例
        self.parser = ElftoolsParser.__new__(ElftoolsParser)
        # 默认按 32 位假设（多数现存场景），64 位用例会显式覆盖
        self.parser._address_size = 4

        # 临时目录 + 临时 dump 文件
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_dump_reader(self, data: bytes, ram_base: int = 0x20000000) -> DumpReader:
        """把字节序列写成 dump 文件，返回绑定到 ram_base 的 DumpReader。

        自动填充到 512 字节，避免 read_string(max_length=256) 越界返回 None。
        """
        if len(data) < 512:
            data = data + b'\x00' * (512 - len(data))
        dump_path = os.path.join(self.temp_dir, 'synth_dump.bin')
        with open(dump_path, 'wb') as f:
            f.write(data)
        regions = [{'name': 'ram', 'start_addr': ram_base, 'size': len(data)}]
        return DumpReader(dump_path, regions)

    @staticmethod
    def _hex_part(display_str: str) -> str:
        """从 display_value 提取 hex 部分。
        
        支持新旧格式:
        - 旧: '<ptr 0xdeadbeef>' → 'deadbeef'
        - 新: '→ long @ 0xdeadbeef' → 'deadbeef'
        """
        return display_str.split('0x')[1].rstrip('>')

    # ── 1. 32 位指针：8 hex 宽 ─────────────────────────────────
    def test_32bit_pointer_returns_8_hex_width(self):
        """4 字节指针 → kind='ptr_scalar', display_value 包含 8 hex 宽的地址。"""
        # 0xdeadbeef little-endian
        data = (0xdeadbeef).to_bytes(4, 'little')
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        # ptr_scalar 是叶子节点，不可展开
        self.assertEqual(result.kind, 'ptr_scalar')
        self.assertFalse(result.expandable)
        self.assertFalse(result.meta.get('is_null'))
        self.assertIn('0xdeadbeef', result.display_value)
        # 8 hex 字符（不含 0x 前缀）
        self.assertEqual(len(self._hex_part(result.display_value)), 8)

    # ── 2. 64 位指针：16 hex 宽（核心修复验证）─────────────────
    def test_64bit_pointer_returns_16_hex_width(self):
        """8 字节指针 → kind='ptr_scalar', display_value 包含 16 hex 宽的地址。

        这是 Phase 1.1 修复的关键回归测试：如果硬编码 read_uint32，
        会读到 0xfeedface（截断高 32 位），测试会立即失败。
        """
        # 0x00000000feedface little-endian = 8 字节
        data = (0x00000000feedface).to_bytes(8, 'little')
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8  # 64 位架构

        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 8},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_scalar')
        self.assertIn('0x00000000feedface', result.display_value)
        # 16 hex 字符（不含 0x 前缀）
        self.assertEqual(len(self._hex_part(result.display_value)), 16)

    # ── 3. 64 位 char* 惰性读取字符串 ────────────────────────
    def test_64bit_char_pointer_auto_derefs_string(self):
        """8 字节 char* → kind='ptr_string', to_dict() 惰性读取字符串。"""
        # 8 字节指针指向偏移 8（即 0x20000008），后面跟 'hello\0'
        ptr_val = 0x20000008
        data = ptr_val.to_bytes(8, 'little') + b'hello\x00'
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8

        # char* 类型：pointer → const → char
        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': 'char*',
            'ref_type': {
                'kind': 'const',
                'name': 'const char',
                'ref_type': {'kind': 'base', 'name': 'char', 'byte_size': 1},
            },
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        # ptr_string: display_value 是地址格式，不是字符串
        self.assertEqual(result.kind, 'ptr_string')
        self.assertIn('0x0000000020000008', result.display_value)
        # to_dict() with dump_reader 惰性读取字符串
        self.assertEqual(result.to_dict(dump_reader=reader), 'hello')

    # ── 4. 0 值 char* 返回 None ────────────────────────────────
    def test_null_char_pointer_returns_none(self):
        """0 值 char* 的 to_dict() 返回 None。"""
        data = b'\x00' * 32
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8

        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': 'char*',
            'ref_type': {'kind': 'base', 'name': 'char', 'byte_size': 1},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_string')
        self.assertTrue(result.meta.get('is_null'))
        self.assertIsNone(result.to_dict())
        self.assertEqual(result.raw_value, 0)

    # ── 5. 非 char* 的 0 值指针统一返回 None ───────────────────
    def test_null_non_char_pointer_returns_hex(self):
        """0 值指针（包括 long*、struct*、void*）的 to_dict() 返回 None。

        设计决策：空指针表示"未指向任何对象"，与有效指针的 hex 字符串
        区分开，便于调用方判断指针是否有效。
        """
        data = b'\x00' * 32
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_scalar')
        self.assertTrue(result.meta.get('is_null'))
        self.assertIsNone(result.to_dict(), "Null pointer should return None via to_dict()")

    # ── 5b. 非 0 值的非 char*/struct* 指针返回 hex 字符串 ──────
    def test_non_null_non_char_non_struct_pointer_returns_hex(self):
        """非 0 值的 long* → kind='ptr_scalar', display_value 包含 hex 地址。"""
        data = b'\x34\x12\x00\x00' + b'\x00' * 28  # ptr_val = 0x1234
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_scalar')
        self.assertIn('0x00001234', result.display_value)

    # ── 6. 异常 byte_size 走 fallback 不崩 ────────────────────
    def test_unusual_byte_size_fallback_no_crash(self):
        """byte_size=2 走 fallback 路径，不应抛异常。"""
        data = b'\xab\xcd' + b'\x00' * 30
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 2,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'short', 'byte_size': 2},
        }
        # 不应抛异常
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_scalar')
        # byte_size=2 走 else 分支，hex_width=8（非 8 字节都按 8 hex 宽格式化）
        self.assertIn('0x0000cdab', result.display_value)

    # ── 7. byte_size 缺失时回退到 _address_size ────────────────
    def test_missing_byte_size_uses_address_size(self):
        """type_info 无 byte_size 字段时，应使用 _address_size。"""
        # 8 字节 dump
        data = (0x12345678).to_bytes(4, 'little') + b'\x00' * 28
        reader = self._make_dump_reader(data)
        # _address_size=4，缺 byte_size 应按 4 字节读
        self.parser._address_size = 4

        type_info = {
            'kind': 'pointer',
            # 故意省略 byte_size
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result.kind, 'ptr_scalar')
        self.assertIn('0x12345678', result.display_value)

    # ── 8. DumpReader.read_pointer_by_size 一致性 ─────────────
    def test_dump_reader_pointer_by_size_helper(self):
        """DumpReader.read_pointer_by_size 与 _read_typed_value 行为一致。"""
        data = (0x00000000cafef00d).to_bytes(8, 'little') + b'\x00' * 24
        reader = self._make_dump_reader(data)

        # 8 字节读法
        v8 = reader.read_pointer_by_size(0x20000000, byte_size=8)
        self.assertEqual(v8, 0x00000000cafef00d)

        # 4 字节读法（只读低 32 位）
        v4 = reader.read_pointer_by_size(0x20000000, byte_size=4)
        self.assertEqual(v4, 0xcafef00d)

    # ── 9. struct 指针自动解引用 ────────────────────────────────
    def test_struct_pointer_auto_deref(self):
        """struct 指针 → kind='ptr_struct', to_dict() 自动解引用并展开字段为 dict。"""
        # 内存布局：
        #   0x20000000: ptr_val = 0x20000010  (指向结构体)
        #   0x20000010: field_a (uint32) = 0xAABBCCDD
        #   0x20000014: field_b (uint8)    = 0x42
        ptr_bytes = (0x20000010).to_bytes(4, 'little')
        field_a_bytes = (0xAABBCCDD).to_bytes(4, 'little')
        field_b_bytes = bytes([0x42])
        data = ptr_bytes + b'\x00' * 12 + field_a_bytes + field_b_bytes + b'\x00' * 7
        reader = self._make_dump_reader(data)

        struct_type = {
            'kind': 'struct',
            'name': 'MyStruct',
            'byte_size': 8,
            'type_offset': 0xDEAD,
            'members': [
                {'name': 'field_a', 'offset': 0,
                 'type': {'kind': 'base', 'name': 'uint32_t', 'byte_size': 4}},
                {'name': 'field_b', 'offset': 4,
                 'type': {'kind': 'base', 'name': 'uint8_t', 'byte_size': 1}},
            ],
        }
        ptr_type = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'type_offset': 0xBEEF,
            'ref_type': struct_type,
        }

        result = self.parser._read_typed_value(ptr_type, 0x20000000, reader)
        # ptr_struct 是叶子节点（指针永远不包含 children）
        self.assertEqual(result.kind, 'ptr_struct')
        self.assertFalse(result.children)
        self.assertFalse(result.meta.get('is_null'))

        # to_dict() with dump_reader auto-dereferences
        d = result.to_dict(dump_reader=reader, elf_parser=self.parser)
        self.assertIsInstance(d, dict, "struct* should auto-deref to dict via to_dict()")
        self.assertEqual(d['field_a'], 0xAABBCCDD)
        self.assertEqual(d['field_b'], 0x42)

    # ── 10. struct 指针 0 值返回 None ──────────────────────────
    def test_null_struct_pointer_returns_none(self):
        """0 值 struct 指针的 to_dict() 返回 None，不解引用。"""
        data = b'\x00' * 32
        reader = self._make_dump_reader(data)

        struct_type = {
            'kind': 'struct',
            'name': 'MyStruct',
            'byte_size': 8,
            'members': [],
        }
        ptr_type = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': struct_type,
        }
        result = self.parser._read_typed_value(ptr_type, 0x20000000, reader)
        self.assertIsNone(result.to_dict(), "Null struct pointer should return None")

    # ── 11. struct 指针指向无效地址时优雅返回 ─────────────────
    def test_struct_pointer_invalid_address(self):
        """struct 指针指向的地址不在 dump 范围内，to_dict() 返回错误 dict 而非崩溃。"""
        # ptr_val = 0xFFFFFFFF（不在 dump 范围内）
        data = (0xFFFFFFFF).to_bytes(4, 'little') + b'\x00' * 28
        reader = self._make_dump_reader(data)

        struct_type = {
            'kind': 'struct',
            'name': 'MyStruct',
            'byte_size': 8,
            'members': [
                {'name': 'field_a', 'offset': 0,
                 'type': {'kind': 'base', 'name': 'uint32_t', 'byte_size': 4}},
            ],
        }
        ptr_type = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': struct_type,
        }
        result = self.parser._read_typed_value(ptr_type, 0x20000000, reader)
        d = result.to_dict(dump_reader=reader, elf_parser=self.parser)
        self.assertIsInstance(d, dict)
        self.assertIn('error', d)
        self.assertEqual(d['error'], 'invalid pointer address')

    # ── 12. typedef 包装的 struct 指针也能解引用 ──────────────
    def test_typedef_wrapped_struct_pointer_deref(self):
        """typedef struct { ... } MyType; MyType* 通过 to_dict() 也能自动解引用。"""
        # 0x20000000: ptr_val = 0x20000010
        # 0x20000010: field = 0x12345678
        ptr_bytes = (0x20000010).to_bytes(4, 'little')
        field_bytes = (0x12345678).to_bytes(4, 'little')
        data = ptr_bytes + b'\x00' * 12 + field_bytes + b'\x00' * 12
        reader = self._make_dump_reader(data)

        struct_type = {
            'kind': 'struct',
            'name': 'MyStruct',
            'byte_size': 4,
            'members': [
                {'name': 'field', 'offset': 0,
                 'type': {'kind': 'base', 'name': 'uint32_t', 'byte_size': 4}},
            ],
        }
        typedef_type = {
            'kind': 'typedef',
            'name': 'MyType',
            'ref_type': struct_type,
        }
        ptr_type = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': typedef_type,
        }
        result = self.parser._read_typed_value(ptr_type, 0x20000000, reader)
        d = result.to_dict(dump_reader=reader, elf_parser=self.parser)
        self.assertIsInstance(d, dict)
        self.assertEqual(d['field'], 0x12345678)

    # ── 13. 循环引用 struct 指针不会无限递归 ──────────────────
    def test_struct_pointer_circular_reference_protection(self):
        """struct 指针形成循环引用时 to_dict() 不无限递归。

        模拟：节点 A.next -> 节点 B.next -> 节点 A.next ...
        """
        # 内存布局（节点 A 和节点 B 互相指向）：
        #   0x20000000: ptr_val = 0x20000010  (A = 节点A地址)
        #   0x20000010: value_a = 0x11, next_ptr = 0x20000020 (B = 节点B地址)
        #   0x20000020: value_b = 0x22, next_ptr = 0x20000010 (指回节点A)
        ptr_to_a = (0x20000010).to_bytes(4, 'little')
        node_a = (0x11).to_bytes(4, 'little') + (0x20000020).to_bytes(4, 'little')
        node_b = (0x22).to_bytes(4, 'little') + (0x20000010).to_bytes(4, 'little')
        # 在 node_a 和 node_b 之间插入 8 字节填充，让 node_b 起始在 0x20000020
        data = ptr_to_a + b'\x00' * 12 + node_a + b'\x00' * 8 + node_b
        reader = self._make_dump_reader(data)

        # Node 类型：{ uint32_t value; Node* next; }
        # 使用相同 type_offset 模拟递归类型
        node_struct = {
            'kind': 'struct',
            'name': 'Node',
            'byte_size': 8,
            'type_offset': 0xCAFE,
            'members': [
                {'name': 'value', 'offset': 0,
                 'type': {'kind': 'base', 'name': 'uint32_t', 'byte_size': 4}},
                # next 字段：指向同样的 Node，但用占位 type_offset
                {'name': 'next', 'offset': 4,
                 'type': {
                     'kind': 'pointer', 'byte_size': 4, 'name': None,
                     'type_offset': 0xCAFE,  # 循环引用的关键
                     'ref_type': None  # 自引用，会被 _visited 拦截
                 }},
            ],
        }
        # 填回 self-ref
        node_struct['members'][1]['type']['ref_type'] = node_struct

        ptr_type = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'type_offset': 0xBEEF,
            'ref_type': node_struct,
        }

        # 不应崩溃或无限递归
        result = self.parser._read_typed_value(ptr_type, 0x20000000, reader)
        d = result.to_dict(dump_reader=reader, elf_parser=self.parser)
        self.assertIsInstance(d, dict)
        self.assertEqual(d['value'], 0x11)
        # next 字段是另一个 Node*，解引用得到节点 B
        next_node = d['next']
        self.assertIsInstance(next_node, dict)
        self.assertEqual(next_node['value'], 0x22)
        # 节点 B 的 next 指回节点 A，应该被循环引用保护拦截
        # 期望返回包含 'error' 字段的 dict（避免无限递归）
        next_next = next_node['next']
        self.assertIsInstance(next_next, dict,
                            "Circular ref should return error dict, not crash")
        # 不能再次完整展开节点 A（否则就是无限递归）
        # 期望得到 circular reference 错误标记
        self.assertTrue(
            'error' in next_next or next_next.get('value') != 0x11,
            "Circular reference should be detected and stopped"
        )


if __name__ == '__main__':
    unittest.main()
