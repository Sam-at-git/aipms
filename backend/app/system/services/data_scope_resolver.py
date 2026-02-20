"""
分店数据作用域解析器

根据用户所属部门和角色的 data_scope 配置，解析出该用户可见的分店集合。
"""
import logging
from typing import Optional, Set
from sqlalchemy.orm import Session

from core.security.data_scope import (
    DataScopeContext, DataScopeLevel, IDataScopeResolver
)
from app.system.models.org import SysDepartment, DeptType

logger = logging.getLogger(__name__)


class BranchDataScopeResolver(IDataScopeResolver):
    """分店数据作用域解析器"""

    def __init__(self, db: Session):
        self.db = db

    def resolve_scope(self, user_id: int, role_data_scope: str, **kwargs) -> DataScopeContext:
        """
        根据用户的部门归属和角色的 data_scope 配置，解析可见分店集合。

        role_data_scope 取值:
        - ALL           → DataScopeLevel.ALL (不过滤)
        - DEPT_AND_BELOW → 本分店
        - DEPT          → 本分店
        - SELF          → 仅自己的数据
        """
        branch_id = kwargs.get("branch_id")
        department_id = kwargs.get("department_id")

        if role_data_scope == "ALL":
            return DataScopeContext(level=DataScopeLevel.ALL)

        if role_data_scope == "SELF":
            return DataScopeContext(
                level=DataScopeLevel.SELF_ONLY,
                user_id=user_id,
                owner_column="created_by",
            )

        # DEPT_AND_BELOW or DEPT → 找到所属分店
        scope_ids: Set[int] = set()

        if branch_id:
            scope_ids.add(branch_id)
        elif department_id:
            found = self.find_branch_for_department(department_id)
            if found:
                scope_ids.add(found)

        level = (
            DataScopeLevel.SCOPE_AND_BELOW
            if role_data_scope == "DEPT_AND_BELOW"
            else DataScopeLevel.SCOPE_ONLY
        )
        return DataScopeContext(level=level, scope_ids=scope_ids, user_id=user_id)

    def find_branch_for_department(self, dept_id: int) -> Optional[int]:
        """沿组织树向上查找所属分店的 ID"""
        dept = self.db.query(SysDepartment).get(dept_id)
        visited = set()
        while dept and dept.id not in visited:
            visited.add(dept.id)
            if dept.dept_type == DeptType.BRANCH:
                return dept.id
            if dept.dept_type == DeptType.GROUP:
                return None
            if dept.parent_id:
                dept = self.db.query(SysDepartment).get(dept.parent_id)
            else:
                break
        return None

    def get_entity_scope_column(self, entity_name: str) -> Optional[str]:
        """获取实体的作用域列名"""
        from core.ontology.registry import OntologyRegistry
        registry = OntologyRegistry()
        entity_meta = registry.get_entity(entity_name)
        if entity_meta and entity_meta.data_scope_type == "scoped":
            return entity_meta.scope_column
        return None

    @staticmethod
    def get_all_branches(db: Session):
        """获取所有分店节点"""
        return db.query(SysDepartment).filter(
            SysDepartment.dept_type == DeptType.BRANCH,
            SysDepartment.is_active == True,
        ).order_by(SysDepartment.sort_order).all()
