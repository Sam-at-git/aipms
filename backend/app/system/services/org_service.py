"""
组织机构 Service — 部门树 CRUD + 岗位 CRUD
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.system.models.org import SysDepartment, SysPosition


class OrgService:
    def __init__(self, db: Session):
        self.db = db

    # =============== Department ===============

    def get_departments(self, is_active: Optional[bool] = None) -> List[SysDepartment]:
        query = self.db.query(SysDepartment)
        if is_active is not None:
            query = query.filter(SysDepartment.is_active == is_active)
        return query.order_by(SysDepartment.sort_order, SysDepartment.id).all()

    def get_department_by_id(self, dept_id: int) -> Optional[SysDepartment]:
        return self.db.query(SysDepartment).filter(SysDepartment.id == dept_id).first()

    def get_department_by_code(self, code: str) -> Optional[SysDepartment]:
        return self.db.query(SysDepartment).filter(SysDepartment.code == code).first()

    def create_department(
        self, code: str, name: str, parent_id: Optional[int] = None,
        leader_id: Optional[int] = None, sort_order: int = 0,
        dept_type: Optional[str] = None,
    ) -> SysDepartment:
        if self.get_department_by_code(code):
            raise ValueError(f"部门编码 '{code}' 已存在")
        if parent_id is not None:
            parent = self.get_department_by_id(parent_id)
            if not parent:
                raise ValueError(f"父部门 ID {parent_id} 不存在")

        kwargs = dict(
            code=code, name=name, parent_id=parent_id,
            leader_id=leader_id, sort_order=sort_order,
        )
        if dept_type:
            from app.system.models.org import DeptType
            kwargs["dept_type"] = DeptType(dept_type)
        dept = SysDepartment(**kwargs)
        self.db.add(dept)
        self.db.commit()
        self.db.refresh(dept)
        return dept

    def update_department(self, dept_id: int, **kwargs) -> SysDepartment:
        dept = self.get_department_by_id(dept_id)
        if not dept:
            raise ValueError("部门不存在")

        if "code" in kwargs and kwargs["code"] != dept.code:
            if self.get_department_by_code(kwargs["code"]):
                raise ValueError(f"部门编码 '{kwargs['code']}' 已存在")

        # Prevent circular parent
        if "parent_id" in kwargs and kwargs["parent_id"] is not None:
            if kwargs["parent_id"] == dept_id:
                raise ValueError("不能将自身设为父部门")

        for key, value in kwargs.items():
            if hasattr(dept, key):
                setattr(dept, key, value)

        self.db.commit()
        self.db.refresh(dept)
        return dept

    def delete_department(self, dept_id: int) -> bool:
        dept = self.get_department_by_id(dept_id)
        if not dept:
            raise ValueError("部门不存在")
        # Check for children
        children = self.db.query(SysDepartment).filter(
            SysDepartment.parent_id == dept_id
        ).count()
        if children > 0:
            raise ValueError("该部门下有子部门，无法删除")

        self.db.delete(dept)
        self.db.commit()
        return True

    def get_department_tree(self) -> List[dict]:
        """Build department tree from flat list"""
        all_depts = self.get_departments(is_active=True)
        dept_map = {}
        for d in all_depts:
            dept_map[d.id] = {
                "id": d.id, "code": d.code, "name": d.name,
                "parent_id": d.parent_id,
                "dept_type": d.dept_type.value if d.dept_type else "DEPARTMENT",
                "leader_id": d.leader_id,
                "sort_order": d.sort_order, "is_active": d.is_active,
                "created_at": d.created_at, "updated_at": d.updated_at,
                "children": [],
            }
        roots = []
        for d in dept_map.values():
            pid = d["parent_id"]
            if pid and pid in dept_map:
                dept_map[pid]["children"].append(d)
            else:
                roots.append(d)
        return roots

    # =============== Position ===============

    def get_positions(
        self, department_id: Optional[int] = None, is_active: Optional[bool] = None
    ) -> List[SysPosition]:
        query = self.db.query(SysPosition)
        if department_id is not None:
            query = query.filter(SysPosition.department_id == department_id)
        if is_active is not None:
            query = query.filter(SysPosition.is_active == is_active)
        return query.order_by(SysPosition.sort_order, SysPosition.id).all()

    def get_position_by_id(self, pos_id: int) -> Optional[SysPosition]:
        return self.db.query(SysPosition).filter(SysPosition.id == pos_id).first()

    def get_position_by_code(self, code: str) -> Optional[SysPosition]:
        return self.db.query(SysPosition).filter(SysPosition.code == code).first()

    def create_position(
        self, code: str, name: str, department_id: Optional[int] = None, sort_order: int = 0,
    ) -> SysPosition:
        if self.get_position_by_code(code):
            raise ValueError(f"岗位编码 '{code}' 已存在")
        if department_id is not None:
            dept = self.get_department_by_id(department_id)
            if not dept:
                raise ValueError(f"部门 ID {department_id} 不存在")

        pos = SysPosition(
            code=code, name=name, department_id=department_id, sort_order=sort_order,
        )
        self.db.add(pos)
        self.db.commit()
        self.db.refresh(pos)
        return pos

    def update_position(self, pos_id: int, **kwargs) -> SysPosition:
        pos = self.get_position_by_id(pos_id)
        if not pos:
            raise ValueError("岗位不存在")

        if "code" in kwargs and kwargs["code"] != pos.code:
            if self.get_position_by_code(kwargs["code"]):
                raise ValueError(f"岗位编码 '{kwargs['code']}' 已存在")

        for key, value in kwargs.items():
            if hasattr(pos, key):
                setattr(pos, key, value)

        self.db.commit()
        self.db.refresh(pos)
        return pos

    def delete_position(self, pos_id: int) -> bool:
        pos = self.get_position_by_id(pos_id)
        if not pos:
            raise ValueError("岗位不存在")

        self.db.delete(pos)
        self.db.commit()
        return True
