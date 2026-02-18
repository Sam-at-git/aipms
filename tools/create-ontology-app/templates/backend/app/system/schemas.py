"""
系统管理 Pydantic 模型 — API 输入输出验证
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ---- DictType ----

class DictTypeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="字典类型编码")
    name: str = Field(..., min_length=1, max_length=200, description="字典类型名称")
    description: str = Field(default="", max_length=500)
    is_system: bool = Field(default=False)


class DictTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class DictTypeResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str
    is_system: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item_count: int = 0

    model_config = {"from_attributes": True}


# ---- DictItem ----

class DictItemCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200, description="显示文本")
    value: str = Field(..., min_length=1, max_length=200, description="存储值")
    color: str = Field(default="", max_length=50)
    extra: str = Field(default="", description="JSON 扩展属性")
    sort_order: int = Field(default=0)
    is_default: bool = Field(default=False)


class DictItemUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    value: Optional[str] = Field(None, min_length=1, max_length=200)
    color: Optional[str] = Field(None, max_length=50)
    extra: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class DictItemResponse(BaseModel):
    id: int
    dict_type_id: int
    label: str
    value: str
    color: str
    extra: str
    sort_order: int
    is_default: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Config schemas (referenced by config_router) ----

class ConfigCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(default="")
    name: str = Field(default="", max_length=200)
    group_code: str = Field(default="default", max_length=100)
    value_type: str = Field(default="string", max_length=50)
    is_sensitive: bool = Field(default=False)
    is_public: bool = Field(default=False)
    description: str = Field(default="", max_length=500)


class ConfigUpdate(BaseModel):
    value: Optional[str] = None
    name: Optional[str] = Field(None, max_length=200)
    group_code: Optional[str] = Field(None, max_length=100)
    value_type: Optional[str] = Field(None, max_length=50)
    is_sensitive: Optional[bool] = None
    is_public: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)


class ConfigResponse(BaseModel):
    id: int
    key: str
    value: str
    name: str
    group_code: str
    value_type: str
    is_sensitive: bool
    is_public: bool
    is_system: bool
    description: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Role ----

class RoleCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="角色编码")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: str = Field(default="", max_length=500)
    data_scope: str = Field(default="ALL", max_length=20)
    sort_order: int = Field(default=0)


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    data_scope: Optional[str] = Field(None, max_length=20)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str
    data_scope: str
    sort_order: int
    is_system: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permission_count: int = 0

    model_config = {"from_attributes": True}


class RoleDetailResponse(RoleResponse):
    permissions: List["PermissionResponse"] = []


# ---- Permission ----

class PermissionCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="权限编码")
    name: str = Field(..., min_length=1, max_length=200, description="权限名称")
    type: str = Field(default="api", max_length=20, description="类型: menu|button|api|data")
    resource: str = Field(default="", max_length=100)
    action: str = Field(default="", max_length=100)
    parent_id: Optional[int] = None
    sort_order: int = Field(default=0)


class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, max_length=20)
    resource: Optional[str] = Field(None, max_length=100)
    action: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PermissionResponse(BaseModel):
    id: int
    code: str
    name: str
    type: str
    resource: str
    action: str
    parent_id: Optional[int] = None
    sort_order: int
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- User-Role ----

class UserRoleAssign(BaseModel):
    role_ids: List[int] = Field(..., description="角色ID列表")


class UserRoleResponse(BaseModel):
    user_id: int
    roles: List[RoleResponse] = []


# ---- Menu ----

class MenuCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="菜单编码")
    name: str = Field(..., min_length=1, max_length=100, description="菜单名称")
    parent_id: Optional[int] = None
    path: str = Field(default="", max_length=200)
    icon: str = Field(default="", max_length=50)
    component: str = Field(default="", max_length=200)
    permission_code: str = Field(default="", max_length=100)
    menu_type: str = Field(default="menu", max_length=20)
    is_visible: bool = Field(default=True)
    sort_order: int = Field(default=0)


class MenuUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    path: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field(None, max_length=50)
    component: Optional[str] = Field(None, max_length=200)
    permission_code: Optional[str] = Field(None, max_length=100)
    menu_type: Optional[str] = Field(None, max_length=20)
    is_visible: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class MenuResponse(BaseModel):
    id: int
    name: str
    code: str
    parent_id: Optional[int] = None
    path: str
    icon: str
    component: str
    permission_code: str
    menu_type: str
    is_visible: bool
    sort_order: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Department ----

class DepartmentCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="部门编码")
    name: str = Field(..., min_length=1, max_length=100, description="部门名称")
    parent_id: Optional[int] = None
    leader_id: Optional[int] = None
    sort_order: int = Field(default=0)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    leader_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None
    leader_id: Optional[int] = None
    sort_order: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DepartmentTreeResponse(DepartmentResponse):
    children: List["DepartmentTreeResponse"] = []


# ---- Position ----

class PositionCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="岗位编码")
    name: str = Field(..., min_length=1, max_length=100, description="岗位名称")
    department_id: Optional[int] = None
    sort_order: int = Field(default=0)


class PositionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    department_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PositionResponse(BaseModel):
    id: int
    code: str
    name: str
    department_id: Optional[int] = None
    sort_order: int
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Message ----

class MessageSend(BaseModel):
    recipient_id: int = Field(..., description="接收人ID")
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    msg_type: str = Field(default="system", max_length=20)
    related_entity_type: Optional[str] = Field(None, max_length=50)
    related_entity_id: Optional[int] = None


class MessageResponse(BaseModel):
    id: int
    sender_id: Optional[int] = None
    recipient_id: int
    title: str
    content: str
    msg_type: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InboxResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    unread_count: int


# ---- Message Template ----

class TemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    channel: str = Field(default="internal", max_length=20)
    subject_template: str = Field(default="")
    content_template: str = Field(default="")
    variables: str = Field(default="")


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    channel: Optional[str] = Field(None, max_length=20)
    subject_template: Optional[str] = None
    content_template: Optional[str] = None
    variables: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: int
    code: str
    name: str
    channel: str
    subject_template: str
    content_template: str
    variables: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Announcement ----

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    status: str = Field(default="draft", max_length=20)
    is_pinned: bool = Field(default=False)


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    publisher_id: int
    status: str
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    is_pinned: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AnnouncementActiveResponse(BaseModel):
    id: int
    title: str
    content: str
    is_pinned: bool
    publish_at: Optional[str] = None
    is_read: bool
