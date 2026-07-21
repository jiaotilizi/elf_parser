import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParserFactory


class TestELFParserFactoryRegistration(unittest.TestCase):
    """测试 ELFParserFactory 的装饰器注册机制。"""

    def test_register_decorator(self):
        """装饰器注册机制能正确注册解析器类。"""
        @ELFParserFactory.register('test_parser')
        class TestParser:
            pass

        self.assertIn('test_parser', ELFParserFactory._parsers)
        self.assertEqual(ELFParserFactory._parsers['test_parser'], TestParser)

    def test_create_with_registered_parser(self):
        """create 方法能创建通过装饰器注册的解析器实例。"""
        @ELFParserFactory.register('test_create_parser')
        class TestCreateParser:
            def __init__(self, elf_path):
                self.elf_path = elf_path

        instance = ELFParserFactory.create('/fake/path.elf', 'test_create_parser')
        self.assertIsInstance(instance, TestCreateParser)
        self.assertEqual(instance.elf_path, '/fake/path.elf')

    def test_create_with_invalid_parser_name(self):
        """create 方法对无效的解析器名称抛出 ValueError。"""
        with self.assertRaises(ValueError):
            ELFParserFactory.create('/fake/path.elf', 'invalid_parser_name_xyz')

    def test_register_duplicate_name(self):
        """重复注册同一名称会覆盖之前的注册。"""
        @ELFParserFactory.register('duplicate_test')
        class FirstParser:
            pass

        @ELFParserFactory.register('duplicate_test')
        class SecondParser:
            pass

        self.assertEqual(ELFParserFactory._parsers['duplicate_test'], SecondParser)

    def test_list_parsers(self):
        """list_parsers 返回所有已注册的解析器名称。"""
        parsers = ELFParserFactory.list_parsers()
        self.assertIsInstance(parsers, list)
        self.assertIn('elftools', parsers)
        self.assertIn('dwarffi', parsers)
        self.assertIn('gimli', parsers)


if __name__ == '__main__':
    unittest.main()