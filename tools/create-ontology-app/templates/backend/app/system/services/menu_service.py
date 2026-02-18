"""
菜单管理 Service
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from app.system.models.menu import SysMenu


class MenuService:
    """菜单管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_menus(self, include_inactive: bool = False) -> List[SysMenu]:
        q = self.db.query(SysMenu)
        if not include_inactive:
            q = q.filter(SysMenu.is_active == True)
        return q.order_by(SysMenu.sort_order, SysMenu.id).all()

    def get_menu_by_id(self, menu_id: int) -> Optional[SysMenu]:
        return self.db.query(SysMenu).filter(SysMenu.id == menu_id).first()

    def get_menu_by_code(self, code: str) -> Optional[SysMenu]:
        return self.db.query(SysMenu).filter(SysMenu.code == code).first()

    def create_menu(self, code: str, name: str, menu_type: str = "menu",
                    parent_id: Optional[int] = None, path: str = "",
                    icon: str = "", component: str = "",
                    permission_code: str = "", is_visible: bool = True,
                    sort_order: int = 0) -> SysMenu:
        existing = self.get_menu_by_code(code)
        if existing:
            raise ValueError(f"菜单编码 '{code}' 已存在")

        menu = SysMenu(
            code=code, name=name, menu_type=menu_type,
            parent_id=parent_id, path=path, icon=icon,
            component=component, permission_code=permission_code,
            is_visible=is_visible, sort_order=sort_order,
        )
        self.db.add(menu)
        self.db.flush()
        return menu

    def update_menu(self, menu_id: int, **kwargs) -> SysMenu:
        menu = self.get_menu_by_id(menu_id)
        if not menu:
            raise ValueError(f"菜单 ID {menu_id} 不存在")

        for key, value in kwargs.items():
            if key == "code" and value != menu.code:
                existing = self.get_menu_by_code(value)
                if existing:
                    raise ValueError(f"菜单编码 '{value}' 已存在")
            if hasattr(menu, key):
                setattr(menu, key, value)

        self.db.flush()
        return menu

    def delete_menu(self, menu_id: int) -> None:
        menu = self.get_menu_by_id(menu_id)
        if not menu:
            raise ValueError(f"菜单 ID {menu_id} 不存在")

        # Check for children
        child_count = self.db.query(SysMenu).filter(SysMenu.parent_id == menu_id).count()
        if child_count > 0:
            raise ValueError(f"菜单 '{menu.name}' 有 {child_count} 个子菜单，请先删除子菜单")

        self.db.delete(menu)
        self.db.flush()

    def get_menu_tree(self, include_buttons: bool = False) -> List[Dict]:
        """Build full menu tree for admin"""
        menus = self.get_menus()
        if not include_buttons:
            menus = [m for m in menus if m.menu_type != "button"]
        return self._build_tree(menus)

    def get_user_menu_tree(self, user_permissions: Set[str], is_sysadmin: bool = False) -> List[Dict]:
        """Build menu tree filtered by user permissions"""
        menus = self.get_menus()
        # Filter to visible menus only
        menus = [m for m in menus if m.is_visible and m.menu_type != "button"]

        if not is_sysadmin:
            # Keep menus that have no permission requirement OR user has the permission
            menus = [m for m in menus if not m.permission_code or m.permission_code in user_permissions]

        tree = self._build_tree(menus)

        # Remove empty directories
        return [node for node in tree if node["menu_type"] != "directory" or node.get("children")]

    def _build_tree(self, menus: List[SysMenu]) -> List[Dict]:
        """Build hierarchical tree from flat menu list"""
        menu_map = {}
        for m in menus:
            menu_map[m.id] = {
                "id": m.id, "name": m.name, "code": m.code,
                "path": m.path, "icon": m.icon, "component": m.component,
                "permission_code": m.permission_code, "menu_type": m.menu_type,
                "is_visible": m.is_visible, "sort_order": m.sort_order,
                "parent_id": m.parent_id, "children": [],
            }

        tree = []
        for item in menu_map.values():
            if item["parent_id"] and item["parent_id"] in menu_map:
                menu_map[item["parent_id"]]["children"].append(item)
            else:
                tree.append(item)

        return tree
