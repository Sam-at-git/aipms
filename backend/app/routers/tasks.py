"""
任务管理路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, TaskType, TaskStatus, EmployeeRole
from app.models.schemas import TaskCreate, TaskAssign, TaskUpdate, TaskResponse
from app.services.task_service import TaskService
from app.security.auth import get_current_user, require_receptionist_or_manager, require_any_role, require_permission
from app.security.permissions import TASK_READ, TASK_WRITE, TASK_ASSIGN

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.get("", response_model=List[TaskResponse])
def list_tasks(
    task_type: Optional[TaskType] = None,
    status: Optional[TaskStatus] = None,
    assignee_id: Optional[int] = None,
    room_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取任务列表"""
    service = TaskService(db)
    tasks = service.get_tasks(task_type, status, assignee_id, room_id)
    return [TaskResponse(**service.get_task_detail(t.id)) for t in tasks]


@router.get("/my-tasks", response_model=List[TaskResponse])
def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_READ))
):
    """获取我的任务（清洁员）"""
    service = TaskService(db)
    tasks = service.get_my_tasks(current_user.id)
    return [TaskResponse(**service.get_task_detail(t.id)) for t in tasks]


@router.get("/pending", response_model=List[TaskResponse])
def get_pending_tasks(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """获取待分配任务"""
    service = TaskService(db)
    tasks = service.get_pending_tasks()
    return [TaskResponse(**service.get_task_detail(t.id)) for t in tasks]


@router.get("/cleaners")
def get_cleaners(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """获取清洁员列表"""
    service = TaskService(db)
    cleaners = service.get_cleaners()
    return [{"id": c.id, "name": c.name} for c in cleaners]


@router.get("/summary")
def get_task_summary(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取任务统计"""
    service = TaskService(db)
    return service.get_task_summary()


@router.delete("/batch")
def batch_delete_tasks(
    task_status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    room_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """批量删除任务（仅 pending/assigned 状态）"""
    if current_user.role not in [EmployeeRole.MANAGER, EmployeeRole.SYSADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可批量删除任务")
    service = TaskService(db)
    count = service.batch_delete_tasks(status=task_status, task_type=task_type, room_id=room_id)
    return {"message": f"已删除 {count} 条任务", "deleted_count": count}


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """删除单个任务（仅 pending/assigned 状态）"""
    service = TaskService(db)
    try:
        service.delete_task(task_id)
        return {"message": f"任务 {task_id} 已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取任务详情"""
    service = TaskService(db)
    detail = service.get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return TaskResponse(**detail)


@router.post("", response_model=TaskResponse)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """创建任务"""
    service = TaskService(db)
    try:
        task = service.create_task(data, current_user.id)
        return TaskResponse(**service.get_task_detail(task.id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{task_id}/assign")
def assign_task(
    task_id: int,
    data: TaskAssign,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """分配任务"""
    service = TaskService(db)
    try:
        task = service.assign_task(task_id, data)
        return {"message": "分配成功", "assignee_name": task.assignee.name}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{task_id}/start")
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_READ))
):
    """开始任务"""
    service = TaskService(db)
    try:
        task = service.start_task(task_id, current_user.id)
        return {"message": "任务已开始", "started_at": task.started_at}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{task_id}/complete")
def complete_task(
    task_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_READ))
):
    """完成任务"""
    service = TaskService(db)
    try:
        task = service.complete_task(task_id, current_user.id, notes)
        return {"message": "任务已完成", "completed_at": task.completed_at}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{task_id}")
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(TASK_WRITE))
):
    """更新任务"""
    service = TaskService(db)
    try:
        task = service.update_task(task_id, data)
        return TaskResponse(**service.get_task_detail(task.id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
