"""Employee entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import EntityMetadata


def get_registration() -> EntityRegistration:
    from app.models.ontology import Employee

    metadata = EntityMetadata(
        name="Employee",
        description="员工 - 系统用户，按角色(sysadmin/manager/receptionist/cleaner)区分权限。负责执行各类酒店运营操作。",
        table_name="employees", category="master_data",
        extensions={
            "business_purpose": "员工管理与权限控制",
            "key_attributes": ["username", "name", "role", "is_active"],
            "smart_update": {
                "enabled": True,
                "identifier_fields": {"name_column": "name"},
                "editable_fields": ["name", "phone"],
                "update_schema": "EmployeeUpdate",
                "service_class": "app.services.employee_service.EmployeeService",
                "service_method": "update_employee",
                "allowed_roles": {"manager"},
                "display_name": "员工",
            },
        },
    )

    return EntityRegistration(
        metadata=metadata,
        model_class=Employee,
    )
