"""
测试 ObjectProxy 安全访问控制和 PII 脱敏功能

SPEC-22: ObjectProxy security + PII masking
"""
import pytest
from core.ontology.base import BaseEntity, ObjectProxy
from core.ontology.metadata import EntityMetadata, PropertyMetadata, PIIType
from core.ontology.security import SecurityLevel
from core.security.context import SecurityContext


# ============================================================
# Test Fixtures: Entity with ontology metadata
# ============================================================

def _make_entity_class(properties: dict):
    """Create a BaseEntity subclass with ontology metadata including given properties."""

    class SecureEntity(BaseEntity):
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # Attach ontology metadata with properties
    SecureEntity._ontology_metadata = EntityMetadata(
        name="SecureEntity",
        description="Test entity with security metadata",
        table_name="secure_entities",
        properties=properties,
    )
    return SecureEntity


def _make_context(level: SecurityLevel, should_mask_pii: bool = False) -> SecurityContext:
    """Create a SecurityContext with the given level."""
    return SecurityContext(
        user_id=1,
        username="testuser",
        role="staff",
        security_level=level,
        should_mask_pii=should_mask_pii,
    )


# ============================================================
# Tests: Public field access
# ============================================================

class TestPublicFieldAccess:

    def test_proxy_allows_public_fields(self):
        """Public fields should be accessible by any context, including low clearance."""
        props = {
            "room_number": PropertyMetadata(
                name="room_number",
                type="string",
                python_type="str",
                security_level="PUBLIC",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(room_number="101")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        assert proxy.room_number == "101"

    def test_proxy_no_context_allows_public(self):
        """When no context is provided, PUBLIC fields should still be accessible."""
        props = {
            "room_number": PropertyMetadata(
                name="room_number",
                type="string",
                python_type="str",
                security_level="PUBLIC",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(room_number="101")
        proxy = ObjectProxy(entity, context=None)

        assert proxy.room_number == "101"


# ============================================================
# Tests: Restricted field access control
# ============================================================

class TestSecurityLevelAccess:

    def test_proxy_blocks_restricted_fields_without_clearance(self):
        """Accessing a RESTRICTED field with insufficient clearance raises PermissionError."""
        props = {
            "salary": PropertyMetadata(
                name="salary",
                type="number",
                python_type="float",
                security_level="RESTRICTED",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(salary=50000.0)
        ctx = _make_context(SecurityLevel.INTERNAL)  # INTERNAL < RESTRICTED
        proxy = ObjectProxy(entity, context=ctx)

        with pytest.raises(PermissionError, match="requires RESTRICTED clearance"):
            _ = proxy.salary

    def test_proxy_allows_restricted_fields_with_clearance(self):
        """Accessing a RESTRICTED field with RESTRICTED clearance succeeds."""
        props = {
            "salary": PropertyMetadata(
                name="salary",
                type="number",
                python_type="float",
                security_level="RESTRICTED",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(salary=50000.0)
        ctx = _make_context(SecurityLevel.RESTRICTED)
        proxy = ObjectProxy(entity, context=ctx)

        assert proxy.salary == 50000.0

    def test_proxy_blocks_confidential_field_for_public_user(self):
        """CONFIDENTIAL field should be blocked for PUBLIC clearance."""
        props = {
            "internal_notes": PropertyMetadata(
                name="internal_notes",
                type="string",
                python_type="str",
                security_level="CONFIDENTIAL",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(internal_notes="secret info")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        with pytest.raises(PermissionError, match="requires CONFIDENTIAL clearance"):
            _ = proxy.internal_notes

    def test_proxy_no_context_allows_restricted_without_check(self):
        """When no context is provided, non-PUBLIC fields should still be accessible
        (no context means no user to deny)."""
        props = {
            "salary": PropertyMetadata(
                name="salary",
                type="number",
                python_type="float",
                security_level="RESTRICTED",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(salary=50000.0)
        proxy = ObjectProxy(entity, context=None)

        # No context means security check is skipped (no user to deny)
        assert proxy.salary == 50000.0


# ============================================================
# Tests: PII Masking
# ============================================================

class TestPIIMasking:

    def test_proxy_masks_phone_pii(self):
        """PHONE PII type should mask as 138****1234 pattern."""
        props = {
            "phone": PropertyMetadata(
                name="phone",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.PHONE,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(phone="13800138000")
        # PUBLIC clearance user -> below CONFIDENTIAL -> should mask
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        result = proxy.phone
        assert result == "138****8000"

    def test_proxy_masks_name_pii(self):
        """NAME PII type should mask as 张* pattern."""
        props = {
            "guest_name": PropertyMetadata(
                name="guest_name",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.NAME,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(guest_name="张三丰")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        result = proxy.guest_name
        assert result == "张**"

    def test_proxy_masks_id_number_pii(self):
        """ID_NUMBER PII type should mask as 310***1234 pattern."""
        props = {
            "id_number": PropertyMetadata(
                name="id_number",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.ID_NUMBER,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(id_number="310101199001011234")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        result = proxy.id_number
        # 310 + 11 stars (18-3-4=11) + 1234
        assert result == "310" + "*" * 11 + "1234"

    def test_proxy_masks_email_pii(self):
        """EMAIL PII type should mask as a***@example.com pattern."""
        props = {
            "email": PropertyMetadata(
                name="email",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.EMAIL,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(email="alice@example.com")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        result = proxy.email
        assert result == "a***@example.com"

    def test_proxy_no_mask_with_high_clearance(self):
        """CONFIDENTIAL or higher clearance should see unmasked PII data."""
        props = {
            "phone": PropertyMetadata(
                name="phone",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.PHONE,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(phone="13800138000")
        ctx = _make_context(SecurityLevel.CONFIDENTIAL)
        proxy = ObjectProxy(entity, context=ctx)

        # CONFIDENTIAL clearance -> no masking
        assert proxy.phone == "13800138000"

    def test_proxy_masks_pii_when_should_mask_pii_set(self):
        """Even high clearance should mask if should_mask_pii is True."""
        props = {
            "phone": PropertyMetadata(
                name="phone",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.PHONE,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(phone="13800138000")
        ctx = _make_context(SecurityLevel.RESTRICTED, should_mask_pii=True)
        proxy = ObjectProxy(entity, context=ctx)

        # should_mask_pii overrides clearance level
        assert proxy.phone == "138****8000"

    def test_proxy_masks_pii_without_context(self):
        """Without context, PII should be masked."""
        props = {
            "guest_name": PropertyMetadata(
                name="guest_name",
                type="string",
                python_type="str",
                security_level="PUBLIC",
                pii_type=PIIType.NAME,
                pii=True,
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(guest_name="张三")
        proxy = ObjectProxy(entity, context=None)

        assert proxy.guest_name == "张*"


# ============================================================
# Tests: setattr permission check
# ============================================================

class TestSetAttrPermission:

    def test_proxy_setattr_checks_permission(self):
        """Writing to a RESTRICTED field with insufficient clearance raises PermissionError."""
        props = {
            "salary": PropertyMetadata(
                name="salary",
                type="number",
                python_type="float",
                security_level="RESTRICTED",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(salary=50000.0)
        ctx = _make_context(SecurityLevel.INTERNAL)
        proxy = ObjectProxy(entity, context=ctx)

        with pytest.raises(PermissionError, match="Write access denied"):
            proxy.salary = 60000.0

        # Original value unchanged
        assert entity.salary == 50000.0

    def test_proxy_setattr_allows_with_clearance(self):
        """Writing to a RESTRICTED field with sufficient clearance succeeds."""
        props = {
            "salary": PropertyMetadata(
                name="salary",
                type="number",
                python_type="float",
                security_level="RESTRICTED",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(salary=50000.0)
        ctx = _make_context(SecurityLevel.RESTRICTED)
        proxy = ObjectProxy(entity, context=ctx)

        proxy.salary = 60000.0
        assert entity.salary == 60000.0

    def test_proxy_setattr_public_field_any_clearance(self):
        """Writing to a PUBLIC field should work with any clearance."""
        props = {
            "room_number": PropertyMetadata(
                name="room_number",
                type="string",
                python_type="str",
                security_level="PUBLIC",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(room_number="101")
        ctx = _make_context(SecurityLevel.PUBLIC)
        proxy = ObjectProxy(entity, context=ctx)

        proxy.room_number = "202"
        assert entity.room_number == "202"


# ============================================================
# Tests: _get_property_metadata fallback
# ============================================================

class TestGetPropertyMetadataFallback:

    def test_proxy_get_property_metadata_fallback(self):
        """When entity has no _ontology_metadata, _get_property_metadata returns None."""

        class PlainEntity(BaseEntity):
            def __init__(self, name):
                self.name = name

        entity = PlainEntity(name="Test")
        proxy = ObjectProxy(entity, context=None)

        # Access should work normally without metadata
        assert proxy.name == "Test"

        # _get_property_metadata should return None for entities without metadata
        result = proxy._get_property_metadata("name")
        assert result is None

    def test_proxy_get_property_metadata_with_empty_properties(self):
        """When entity metadata has empty properties dict, returns None."""

        class EmptyPropsEntity(BaseEntity):
            def __init__(self, name):
                self.name = name

        EmptyPropsEntity._ontology_metadata = EntityMetadata(
            name="EmptyPropsEntity",
            description="Entity with no properties metadata",
            table_name="empty_entities",
            properties={},
        )

        entity = EmptyPropsEntity(name="Test")
        proxy = ObjectProxy(entity, context=None)

        result = proxy._get_property_metadata("name")
        assert result is None

    def test_proxy_get_property_metadata_caches_result(self):
        """Metadata lookup should be cached for performance."""
        props = {
            "room_number": PropertyMetadata(
                name="room_number",
                type="string",
                python_type="str",
                security_level="PUBLIC",
            ),
        }
        EntityCls = _make_entity_class(props)
        entity = EntityCls(room_number="101")
        proxy = ObjectProxy(entity, context=None)

        # First call populates cache
        meta1 = proxy._get_property_metadata("room_number")
        # Second call uses cache
        meta2 = proxy._get_property_metadata("room_number")

        assert meta1 is meta2
        assert meta1 is not None
        assert meta1.name == "room_number"
