"""
core/ai/query_keywords.py

通用查询关键词常量 - 框架层定义

这些是用于识别用户查询意图的通用动词/介词，
与具体领域无关，适用于所有业务领域。
"""

# 查询类关键词 - 用于识别用户是否在执行查询操作
QUERY_KEYWORDS = [
    '查看', '查询', '显示', '有多少', '哪些', '列表', '统计',
    '数量', '多少', '空闲', '搜索', '检索', '找', '列举',
    'show', 'list', 'get', 'find', 'search', 'query', 'count'
]

# 操作类关键词
ACTION_KEYWORDS = [
    '入住', '办理入住', 'checkin', 'check in',
    '退房', '结账', 'checkout', 'check out',
    '预订', '预约', '订房', 'reserve', 'booking',
    '换房', '转房', 'change',
    '续住', '延期', 'extend',
    '清洁', '打扫', 'cleaning',
    '创建', '新增', 'create', 'add',
    '修改', '更新', 'update', 'modify',
    '删除', '取消', 'delete', 'cancel',
]

# 帮助类关键词
HELP_KEYWORDS = [
    '帮助', '帮忙', '怎么', '如何', '你好', 'hello', 'hi',
    'help', 'how to', 'how do i'
]

__all__ = ['QUERY_KEYWORDS', 'ACTION_KEYWORDS', 'HELP_KEYWORDS']
