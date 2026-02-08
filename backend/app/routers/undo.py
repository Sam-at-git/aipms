"""
撤销操作路由
提供操作撤销的API接口
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.security.auth import get_current_user, require_receptionist_or_manager, require_manager
from app.services.undo_service import UndoService
from app.models.ontology import Employee

router = APIRouter(prefix="/undo", tags=["undo"])


class SnapshotResponse(BaseModel):
    """快照响应模型"""
    id: int
    snapshot_uuid: str
    operation_type: str
    operator_id: int
    operation_time: str
    entity_type: str
    entity_id: int
    is_undone: bool
    expires_at: str
    model_config = ConfigDict(from_attributes=True)


class UndoResult(BaseModel):
    """撤销结果模型"""
    success: bool
    message: str
    details: dict = {}


@router.get("/operations", response_model=List[SnapshotResponse])
async def list_undoable_operations(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    获取可撤销的操作列表

    - **entity_type**: 可选，筛选实体类型（stay_record, reservation, task）
    - **entity_id**: 可选，筛选特定实体
    - **limit**: 返回数量限制，默认20
    """
    # 权限检查：前台和管理员可以查看
    if current_user.role.value not in ['manager', 'receptionist']:
        raise HTTPException(status_code=403, detail="权限不足")

    undo_service = UndoService(db)
    snapshots = undo_service.get_undoable_operations(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit
    )

    return [
        SnapshotResponse(
            id=s.id,
            snapshot_uuid=s.snapshot_uuid,
            operation_type=s.operation_type,
            operator_id=s.operator_id,
            operation_time=s.operation_time.isoformat(),
            entity_type=s.entity_type,
            entity_id=s.entity_id,
            is_undone=s.is_undone,
            expires_at=s.expires_at.isoformat()
        )
        for s in snapshots
    ]


@router.post("/{snapshot_uuid}", response_model=UndoResult)
async def undo_operation(
    snapshot_uuid: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    执行撤销操作

    - **snapshot_uuid**: 要撤销的操作快照UUID
    """
    # 权限检查：前台和管理员可以撤销
    if current_user.role.value not in ['manager', 'receptionist']:
        raise HTTPException(status_code=403, detail="权限不足")

    undo_service = UndoService(db)

    try:
        result = undo_service.undo_operation(snapshot_uuid, current_user.id)
        db.commit()
        return UndoResult(
            success=True,
            message=result.get("message", "操作已撤销"),
            details=result
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"撤销失败: {str(e)}")


@router.get("/history", response_model=List[SnapshotResponse])
async def get_undo_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    获取撤销历史（仅管理员）

    - **limit**: 返回数量限制，默认50
    """
    if current_user.role.value != 'manager':
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可查看")

    undo_service = UndoService(db)
    snapshots = undo_service.get_undo_history(limit=limit)

    return [
        SnapshotResponse(
            id=s.id,
            snapshot_uuid=s.snapshot_uuid,
            operation_type=s.operation_type,
            operator_id=s.operator_id,
            operation_time=s.operation_time.isoformat(),
            entity_type=s.entity_type,
            entity_id=s.entity_id,
            is_undone=s.is_undone,
            expires_at=s.expires_at.isoformat()
        )
        for s in snapshots
    ]


@router.get("/{snapshot_uuid}")
async def get_snapshot_detail(
    snapshot_uuid: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    获取快照详情

    - **snapshot_uuid**: 快照UUID
    """
    if current_user.role.value not in ['manager', 'receptionist']:
        raise HTTPException(status_code=403, detail="权限不足")

    undo_service = UndoService(db)
    snapshot = undo_service.get_snapshot(snapshot_uuid)

    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")

    import json
    return {
        "id": snapshot.id,
        "snapshot_uuid": snapshot.snapshot_uuid,
        "operation_type": snapshot.operation_type,
        "operator_id": snapshot.operator_id,
        "operator_name": snapshot.operator.name if snapshot.operator else None,
        "operation_time": snapshot.operation_time.isoformat(),
        "entity_type": snapshot.entity_type,
        "entity_id": snapshot.entity_id,
        "before_state": json.loads(snapshot.before_state),
        "after_state": json.loads(snapshot.after_state),
        "is_undone": snapshot.is_undone,
        "undone_time": snapshot.undone_time.isoformat() if snapshot.undone_time else None,
        "undone_by": snapshot.undone_by,
        "expires_at": snapshot.expires_at.isoformat(),
        "can_undo": not snapshot.is_undone and snapshot.expires_at > __import__('datetime').datetime.now()
    }
