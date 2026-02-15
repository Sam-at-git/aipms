"""
系统配置 API 路由
前缀: /api/system/configs
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ontology import Employee
from app.security.auth import get_current_user, require_sysadmin
from app.system.services.config_service import ConfigService

router = APIRouter(prefix="/system/configs", tags=["系统配置"])


# ---- Pydantic schemas ----

class ConfigCreate(BaseModel):
    group: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(default="")
    value_type: str = Field(default="string")
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    is_public: bool = Field(default=False)


class ConfigUpdate(BaseModel):
    value: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None


class ConfigResponse(BaseModel):
    id: int
    group: str
    key: str
    value: str
    value_type: str
    name: str
    description: str
    is_public: bool
    is_system: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[int] = None


# ---- Endpoints ----

@router.get("", response_model=List[ConfigResponse])
def list_configs(
    group: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取配置列表（按分组过滤，需要 sysadmin 权限）"""
    service = ConfigService(db)
    configs = service.get_all(group=group)
    return [service.to_api_dict(c) for c in configs]


@router.get("/groups", response_model=List[str])
def list_config_groups(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取配置分组列表"""
    service = ConfigService(db)
    return service.get_groups()


@router.get("/public", response_model=List[ConfigResponse])
def list_public_configs(
    db: Session = Depends(get_db),
):
    """获取公开配置（无需认证）"""
    service = ConfigService(db)
    configs = service.get_public_configs()
    return [service.to_api_dict(c) for c in configs]


@router.get("/{config_key:path}", response_model=ConfigResponse)
def get_config(
    config_key: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取单个配置（按 key 查找）"""
    service = ConfigService(db)
    config = service.get_by_key(config_key)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"配置键 '{config_key}' 不存在")
    return service.to_api_dict(config)


@router.post("", response_model=ConfigResponse, status_code=status.HTTP_201_CREATED)
def create_config(
    data: ConfigCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """创建配置项（需要 sysadmin 权限）"""
    service = ConfigService(db)
    try:
        config = service.create(
            key=data.key, value=data.value, name=data.name,
            group=data.group, value_type=data.value_type,
            description=data.description, is_public=data.is_public,
            updated_by=current_user.id,
        )
        return service.to_api_dict(config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(
    config_id: int,
    data: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """更新配置项（需要 sysadmin 权限）"""
    service = ConfigService(db)
    try:
        kwargs = data.model_dump(exclude_unset=True)
        kwargs["updated_by"] = current_user.id
        config = service.update_by_id(config_id, **kwargs)
        return service.to_api_dict(config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{config_id}")
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """删除配置项（需要 sysadmin 权限，系统内置不可删除）"""
    service = ConfigService(db)
    try:
        service.delete(config_id)
        return {"success": True, "message": "配置项已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
