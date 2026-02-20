"""
集中定义所有权限码常量

与前端 permissions.ts 保持一致。
"""

# 房间管理
ROOM_READ = "room:read"
ROOM_WRITE = "room:write"
ROOM_STATUS = "room:status"

# 客人管理
GUEST_READ = "guest:read"
GUEST_WRITE = "guest:write"

# 预订管理
RESERVATION_READ = "reservation:read"
RESERVATION_WRITE = "reservation:write"
RESERVATION_CANCEL = "reservation:cancel"

# 入住/退房
CHECKIN_EXECUTE = "checkin:execute"
CHECKOUT_EXECUTE = "checkout:execute"

# 账单
BILL_READ = "bill:read"
BILL_WRITE = "bill:write"
BILL_REFUND = "bill:refund"

# 任务
TASK_READ = "task:read"
TASK_WRITE = "task:write"
TASK_ASSIGN = "task:assign"

# 员工
EMPLOYEE_READ = "employee:read"
EMPLOYEE_WRITE = "employee:write"

# 价格
PRICE_READ = "price:read"
PRICE_WRITE = "price:write"

# 报表
REPORT_READ = "report:read"

# 系统管理
SYS_ROLE_MANAGE = "sys:role:manage"
SYS_PERMISSION_MANAGE = "sys:permission:manage"
SYS_DEPT_MANAGE = "sys:dept:manage"
SYS_USER_MANAGE = "sys:user:manage"
SYS_MENU_MANAGE = "sys:menu:manage"
SYS_DICT_MANAGE = "sys:dict:manage"
SYS_CONFIG_MANAGE = "sys:config:manage"
SYS_SCHEDULER_MANAGE = "sys:scheduler:manage"
SYS_MESSAGE_MANAGE = "sys:message:manage"

# 调试
DEBUG_READ = "debug:read"
DEBUG_REPLAY = "debug:replay"

# 安全审计
SECURITY_READ = "security:read"
AUDIT_READ = "audit:read"

# AI 聊天
AI_CHAT = "ai:chat"

# 本体查看
ONTOLOGY_READ = "ontology:read"

# 设置
SETTINGS_READ = "settings:read"
SETTINGS_WRITE = "settings:write"

# 基准测试
BENCHMARK_READ = "benchmark:read"
BENCHMARK_WRITE = "benchmark:write"

# 会话
CONVERSATION_READ = "conversation:read"
CONVERSATION_WRITE = "conversation:write"

# 撤销操作
UNDO_READ = "undo:read"
UNDO_EXECUTE = "undo:execute"
UNDO_HISTORY = "undo:history"
