"""
数据字典 Service — 字典类型和字典项的 CRUD
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.system.models.dict import SysDictType, SysDictItem


class DictService:
    def __init__(self, db: Session):
        self.db = db

    # ---- DictType CRUD ----

    def get_dict_types(self, is_active: Optional[bool] = None) -> List[SysDictType]:
        query = self.db.query(SysDictType)
        if is_active is not None:
            query = query.filter(SysDictType.is_active == is_active)
        return query.order_by(SysDictType.id).all()

    def get_dict_type_by_id(self, type_id: int) -> Optional[SysDictType]:
        return self.db.query(SysDictType).filter(SysDictType.id == type_id).first()

    def get_dict_type_by_code(self, code: str) -> Optional[SysDictType]:
        return self.db.query(SysDictType).filter(SysDictType.code == code).first()

    def create_dict_type(
        self, code: str, name: str, description: str = "", is_system: bool = False
    ) -> SysDictType:
        existing = self.get_dict_type_by_code(code)
        if existing:
            raise ValueError(f"字典类型编码 '{code}' 已存在")

        dict_type = SysDictType(
            code=code, name=name, description=description, is_system=is_system
        )
        self.db.add(dict_type)
        self.db.commit()
        self.db.refresh(dict_type)
        return dict_type

    def update_dict_type(self, type_id: int, **kwargs) -> SysDictType:
        dict_type = self.get_dict_type_by_id(type_id)
        if not dict_type:
            raise ValueError("字典类型不存在")

        # Check code uniqueness if updating code
        if "code" in kwargs and kwargs["code"] != dict_type.code:
            existing = self.get_dict_type_by_code(kwargs["code"])
            if existing:
                raise ValueError(f"字典类型编码 '{kwargs['code']}' 已存在")

        for key, value in kwargs.items():
            if hasattr(dict_type, key):
                setattr(dict_type, key, value)

        self.db.commit()
        self.db.refresh(dict_type)
        return dict_type

    def delete_dict_type(self, type_id: int) -> bool:
        dict_type = self.get_dict_type_by_id(type_id)
        if not dict_type:
            raise ValueError("字典类型不存在")
        if dict_type.is_system:
            raise ValueError(f"系统内置字典类型 '{dict_type.code}' 不可删除")

        self.db.delete(dict_type)
        self.db.commit()
        return True

    # ---- DictItem CRUD ----

    def get_items_by_type_code(self, type_code: str) -> List[SysDictItem]:
        dict_type = self.get_dict_type_by_code(type_code)
        if not dict_type:
            raise ValueError(f"字典类型 '{type_code}' 不存在")
        return (
            self.db.query(SysDictItem)
            .filter(SysDictItem.dict_type_id == dict_type.id, SysDictItem.is_active == True)
            .order_by(SysDictItem.sort_order)
            .all()
        )

    def get_items_by_type_id(self, type_id: int) -> List[SysDictItem]:
        return (
            self.db.query(SysDictItem)
            .filter(SysDictItem.dict_type_id == type_id)
            .order_by(SysDictItem.sort_order)
            .all()
        )

    def get_dict_item_by_id(self, item_id: int) -> Optional[SysDictItem]:
        return self.db.query(SysDictItem).filter(SysDictItem.id == item_id).first()

    def create_dict_item(
        self,
        dict_type_id: int,
        label: str,
        value: str,
        color: str = "",
        extra: str = "",
        sort_order: int = 0,
        is_default: bool = False,
    ) -> SysDictItem:
        # Verify dict type exists
        dict_type = self.get_dict_type_by_id(dict_type_id)
        if not dict_type:
            raise ValueError("字典类型不存在")

        # Check duplicate value within same dict type
        existing = (
            self.db.query(SysDictItem)
            .filter(SysDictItem.dict_type_id == dict_type_id, SysDictItem.value == value)
            .first()
        )
        if existing:
            raise ValueError(f"字典项值 '{value}' 在该字典类型中已存在")

        item = SysDictItem(
            dict_type_id=dict_type_id,
            label=label,
            value=value,
            color=color,
            extra=extra,
            sort_order=sort_order,
            is_default=is_default,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_dict_item(self, item_id: int, **kwargs) -> SysDictItem:
        item = self.get_dict_item_by_id(item_id)
        if not item:
            raise ValueError("字典项不存在")

        # Check value uniqueness if updating value
        if "value" in kwargs and kwargs["value"] != item.value:
            existing = (
                self.db.query(SysDictItem)
                .filter(
                    SysDictItem.dict_type_id == item.dict_type_id,
                    SysDictItem.value == kwargs["value"],
                )
                .first()
            )
            if existing:
                raise ValueError(f"字典项值 '{kwargs['value']}' 在该字典类型中已存在")

        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_dict_item(self, item_id: int) -> bool:
        item = self.get_dict_item_by_id(item_id)
        if not item:
            raise ValueError("字典项不存在")

        self.db.delete(item)
        self.db.commit()
        return True
