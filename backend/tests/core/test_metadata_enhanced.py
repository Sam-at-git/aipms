"""
测试 core.ontology.metadata 增强属性 (SPEC-02.5.4)
"""
import pytest
from core.ontology.metadata import PropertyMetadata, ParamType


class TestPropertyMetadataEnhanced:
    """PropertyMetadata 增强字段测试"""

    def test_default_values(self):
        """测试新增字段的默认值"""
        prop = PropertyMetadata(
            name="test",
            type="VARCHAR",
            python_type="str",
        )
        assert prop.display_name == ""
        assert prop.searchable is False
        assert prop.indexed is False
        assert prop.validators == []
        assert prop.is_rich_text is False
        assert prop.pii is False
        assert prop.phi is False
        assert prop.mask_strategy is None

    def test_display_name(self):
        """测试 display_name 字段"""
        prop = PropertyMetadata(
            name="room_number",
            type="VARCHAR",
            python_type="str",
            display_name="房间号",
        )
        assert prop.display_name == "房间号"

    def test_searchable(self):
        """测试 searchable 字段"""
        prop = PropertyMetadata(
            name="guest_name",
            type="VARCHAR",
            python_type="str",
            searchable=True,
        )
        assert prop.searchable is True

    def test_indexed(self):
        """测试 indexed 字段"""
        prop = PropertyMetadata(
            name="phone",
            type="VARCHAR",
            python_type="str",
            indexed=True,
        )
        assert prop.indexed is True

    def test_validators(self):
        """测试 validators 字段"""
        def validate_phone(v):
            return isinstance(v, str) and len(v) == 11

        prop = PropertyMetadata(
            name="phone",
            type="VARCHAR",
            python_type="str",
            validators=[validate_phone],
        )
        assert len(prop.validators) == 1
        assert prop.validators[0]("13800138000") is True
        assert prop.validators[0]("123") is False

    def test_pii_marking(self):
        """测试 PII 标记"""
        prop = PropertyMetadata(
            name="id_number",
            type="VARCHAR",
            python_type="str",
            pii=True,
            mask_strategy="mask_middle",
        )
        assert prop.pii is True
        assert prop.mask_strategy == "mask_middle"

    def test_phi_marking(self):
        """测试 PHI 标记"""
        prop = PropertyMetadata(
            name="medical_note",
            type="TEXT",
            python_type="str",
            phi=True,
            security_level="RESTRICTED",
        )
        assert prop.phi is True
        assert prop.security_level == "RESTRICTED"

    def test_rich_text(self):
        """测试 rich_text 字段"""
        prop = PropertyMetadata(
            name="description",
            type="TEXT",
            python_type="str",
            is_rich_text=True,
        )
        assert prop.is_rich_text is True

    def test_backward_compatibility(self):
        """测试向后兼容性 - 旧代码创建的 PropertyMetadata 仍然有效"""
        prop = PropertyMetadata(
            name="id",
            type="INTEGER",
            python_type="int",
            is_primary_key=True,
            is_required=True,
            description="主键",
            security_level="INTERNAL",
        )
        assert prop.name == "id"
        assert prop.type == "INTEGER"
        assert prop.is_primary_key is True
        # 新字段应有默认值
        assert prop.display_name == ""
        assert prop.searchable is False
        assert prop.pii is False

    def test_validators_default_factory(self):
        """测试 validators 使用 field(default_factory=list)"""
        prop1 = PropertyMetadata(name="a", type="T", python_type="str")
        prop2 = PropertyMetadata(name="b", type="T", python_type="str")
        # 确保不共享同一个列表实例
        prop1.validators.append(lambda x: True)
        assert len(prop2.validators) == 0

    def test_full_property_with_all_fields(self):
        """测试所有字段同时设置"""
        def v1(x):
            return x > 0

        prop = PropertyMetadata(
            name="phone",
            type="VARCHAR",
            python_type="str",
            is_primary_key=False,
            is_foreign_key=False,
            is_required=True,
            is_unique=True,
            is_nullable=False,
            default_value=None,
            max_length=20,
            enum_values=None,
            description="手机号码",
            security_level="CONFIDENTIAL",
            foreign_key_target=None,
            display_name="手机号",
            searchable=True,
            indexed=True,
            validators=[v1],
            is_rich_text=False,
            pii=True,
            phi=False,
            mask_strategy="mask_middle",
        )
        assert prop.display_name == "手机号"
        assert prop.searchable is True
        assert prop.indexed is True
        assert prop.pii is True
        assert prop.mask_strategy == "mask_middle"
        assert len(prop.validators) == 1
