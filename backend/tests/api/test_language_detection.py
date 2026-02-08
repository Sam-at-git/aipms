"""
测试语言检测功能 (SPEC-12)
"""
import pytest
from app.services.llm_service import detect_language


class TestDetectLanguage:
    """测试 detect_language 函数"""

    def test_chinese_text(self):
        """纯中文文本应返回 zh"""
        assert detect_language("你好，请帮我查一下房间") == "zh"

    def test_english_text(self):
        """纯英文文本应返回 en"""
        assert detect_language("Hello, can you check the room?") == "en"

    def test_mixed_mostly_chinese(self):
        """中文为主的混合文本应返回 zh"""
        assert detect_language("请查一下room 101的状态") == "zh"

    def test_mixed_mostly_english(self):
        """英文为主的混合文本应返回 en"""
        assert detect_language("Check room status for 客人 Zhang") == "en"

    def test_empty_string(self):
        """空字符串默认返回 zh"""
        assert detect_language("") == "zh"

    def test_numbers_only(self):
        """纯数字应返回 en（无中文字符）"""
        assert detect_language("12345") == "en"

    def test_chinese_with_numbers(self):
        """中文夹杂数字"""
        assert detect_language("请查101房间的账单") == "zh"

    def test_single_chinese_char(self):
        """单个中文字符"""
        assert detect_language("好") == "zh"

    def test_single_english_word(self):
        """单个英文单词"""
        assert detect_language("hello") == "en"
