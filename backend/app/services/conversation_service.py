"""
会话服务 - 管理聊天历史的持久化存储

功能：
- JSONL 文件读写（路径：backend/data/conversations/{user_id}/{YYYY-MM-DD}.jsonl）
- 消息分页查询（支持跨天）
- 上下文消息获取（按 topic_id 或最近 N 轮）
- 关键词搜索（支持日期范围）
"""
import json
import os
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date and datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


@dataclass
class MessageContext:
    """消息上下文"""
    topic_id: Optional[str] = None
    is_followup: bool = False
    parent_message_id: Optional[str] = None


@dataclass
class ConversationMessage:
    """会话消息"""
    id: str
    timestamp: str  # ISO 格式
    role: str  # 'user' | 'assistant'
    content: str
    actions: Optional[List[Dict]] = None
    context: Optional[MessageContext] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'id': self.id,
            'timestamp': self.timestamp,
            'role': self.role,
            'content': self.content,
        }
        if self.actions:
            result['actions'] = self.actions
        if self.context:
            result['context'] = asdict(self.context)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        """从字典创建"""
        context_data = data.get('context')
        context = None
        if context_data:
            context = MessageContext(
                topic_id=context_data.get('topic_id'),
                is_followup=context_data.get('is_followup', False),
                parent_message_id=context_data.get('parent_message_id')
            )
        return cls(
            id=data['id'],
            timestamp=data['timestamp'],
            role=data['role'],
            content=data['content'],
            actions=data.get('actions'),
            context=context
        )


class ConversationService:
    """会话服务"""

    def __init__(self, base_dir: str = None):
        """
        初始化会话服务

        Args:
            base_dir: 数据存储根目录，默认为 backend/data/conversations
        """
        if base_dir is None:
            # 获取 backend 目录
            current_file = Path(__file__)
            backend_dir = current_file.parent.parent.parent
            base_dir = backend_dir / 'data' / 'conversations'
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, user_id: int) -> Path:
        """获取用户目录"""
        user_dir = self.base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _get_file_path(self, user_id: int, date_str: str) -> Path:
        """获取特定日期的文件路径"""
        return self._get_user_dir(user_id) / f"{date_str}.jsonl"

    def _date_from_timestamp(self, timestamp: str) -> str:
        """从 ISO 时间戳提取日期字符串"""
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')

    def save_message(self, user_id: int, message: ConversationMessage) -> ConversationMessage:
        """
        保存单条消息

        Args:
            user_id: 用户 ID
            message: 消息对象

        Returns:
            保存的消息（含生成的 ID）
        """
        # 确保消息有 ID
        if not message.id:
            message.id = str(uuid.uuid4())

        # 确保消息有时间戳
        if not message.timestamp:
            message.timestamp = datetime.now().isoformat()

        # 获取日期并写入对应文件
        date_str = self._date_from_timestamp(message.timestamp)
        file_path = self._get_file_path(user_id, date_str)

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False, cls=DateTimeEncoder) + '\n')

        return message

    def save_message_pair(
        self,
        user_id: int,
        user_content: str,
        assistant_content: str,
        actions: Optional[List[Dict]] = None,
        topic_id: Optional[str] = None,
        is_followup: bool = False,
        parent_message_id: Optional[str] = None
    ) -> tuple[ConversationMessage, ConversationMessage]:
        """
        保存一对用户-助手消息

        Args:
            user_id: 用户 ID
            user_content: 用户消息内容
            assistant_content: 助手回复内容
            actions: AI 建议的操作
            topic_id: 话题 ID
            is_followup: 是否为追问回答
            parent_message_id: 父消息 ID

        Returns:
            (用户消息, 助手消息) 元组
        """
        now = datetime.now()

        # 创建用户消息
        user_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            timestamp=now.isoformat(),
            role='user',
            content=user_content,
            context=MessageContext(
                topic_id=topic_id,
                is_followup=is_followup,
                parent_message_id=parent_message_id
            )
        )

        # 创建助手消息（稍后一点）
        assistant_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            timestamp=(now + timedelta(milliseconds=100)).isoformat(),
            role='assistant',
            content=assistant_content,
            actions=actions,
            context=MessageContext(
                topic_id=topic_id,
                is_followup=False,
                parent_message_id=user_msg.id
            )
        )

        # 保存消息
        self.save_message(user_id, user_msg)
        self.save_message(user_id, assistant_msg)

        return user_msg, assistant_msg

    def get_messages(
        self,
        user_id: int,
        limit: int = 50,
        before: Optional[str] = None
    ) -> tuple[List[ConversationMessage], bool]:
        """
        获取最近的消息（支持分页）

        Args:
            user_id: 用户 ID
            limit: 返回数量限制
            before: 在此时间戳之前的消息

        Returns:
            (消息列表, 是否还有更多) 元组
        """
        user_dir = self._get_user_dir(user_id)

        # 获取所有日期文件，按日期倒序
        files = sorted(user_dir.glob('*.jsonl'), reverse=True)

        if not files:
            return [], False

        messages = []
        before_dt = None
        if before:
            before_dt = datetime.fromisoformat(before.replace('Z', '+00:00'))

        # 遍历文件收集消息
        for file_path in files:
            file_messages = self._read_file(file_path)

            for msg in reversed(file_messages):  # 从新到旧
                msg_dt = datetime.fromisoformat(msg.timestamp.replace('Z', '+00:00'))

                if before_dt and msg_dt >= before_dt:
                    continue

                messages.append(msg)

                if len(messages) >= limit + 1:  # 多取一条判断是否还有更多
                    break

            if len(messages) >= limit + 1:
                break

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # 按时间正序返回（旧的在前）
        messages.reverse()

        return messages, has_more

    def get_messages_by_date(self, user_id: int, date_str: str) -> List[ConversationMessage]:
        """
        获取指定日期的所有消息

        Args:
            user_id: 用户 ID
            date_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            消息列表
        """
        file_path = self._get_file_path(user_id, date_str)
        if not file_path.exists():
            return []
        return self._read_file(file_path)

    def get_context_messages(
        self,
        user_id: int,
        topic_id: Optional[str] = None,
        max_rounds: int = 3
    ) -> List[ConversationMessage]:
        """
        获取上下文消息（用于 LLM 对话）

        Args:
            user_id: 用户 ID
            topic_id: 话题 ID（如果有）
            max_rounds: 最大轮数（一轮 = 一问一答）

        Returns:
            上下文消息列表
        """
        messages, _ = self.get_messages(user_id, limit=max_rounds * 2 + 10)

        if not messages:
            return []

        if topic_id:
            # 按 topic_id 过滤
            topic_messages = [
                msg for msg in messages
                if msg.context and msg.context.topic_id == topic_id
            ]
            if topic_messages:
                return topic_messages[-max_rounds * 2:]

        # 返回最近的 N 轮对话
        return messages[-max_rounds * 2:]

    def search_messages(
        self,
        user_id: int,
        keyword: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ) -> List[ConversationMessage]:
        """
        搜索消息

        Args:
            user_id: 用户 ID
            keyword: 搜索关键词
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回数量限制

        Returns:
            匹配的消息列表
        """
        user_dir = self._get_user_dir(user_id)
        files = sorted(user_dir.glob('*.jsonl'), reverse=True)

        if not files:
            return []

        # 解析日期范围
        start_d = date.fromisoformat(start_date) if start_date else None
        end_d = date.fromisoformat(end_date) if end_date else None

        results = []
        keyword_lower = keyword.lower()

        for file_path in files:
            # 从文件名获取日期
            file_date_str = file_path.stem
            try:
                file_date = date.fromisoformat(file_date_str)
            except ValueError:
                continue

            # 日期范围过滤
            if start_d and file_date < start_d:
                continue
            if end_d and file_date > end_d:
                continue

            # 搜索文件内容
            file_messages = self._read_file(file_path)
            for msg in file_messages:
                if keyword_lower in msg.content.lower():
                    results.append(msg)
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        # 按时间倒序
        results.sort(key=lambda m: m.timestamp, reverse=True)

        return results[:limit]

    def get_available_dates(self, user_id: int) -> List[str]:
        """
        获取有历史记录的日期列表

        Args:
            user_id: 用户 ID

        Returns:
            日期字符串列表 (YYYY-MM-DD)，按日期倒序
        """
        user_dir = self._get_user_dir(user_id)
        files = sorted(user_dir.glob('*.jsonl'), reverse=True)

        dates = []
        for file_path in files:
            date_str = file_path.stem
            try:
                date.fromisoformat(date_str)  # 验证日期格式
                dates.append(date_str)
            except ValueError:
                continue

        return dates

    def _read_file(self, file_path: Path) -> List[ConversationMessage]:
        """读取 JSONL 文件"""
        messages = []
        if not file_path.exists():
            return messages

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    messages.append(ConversationMessage.from_dict(data))
                except (json.JSONDecodeError, KeyError) as e:
                    # 跳过无效行
                    continue

        return messages

    def get_last_message(self, user_id: int) -> Optional[ConversationMessage]:
        """
        获取最后一条消息

        Args:
            user_id: 用户 ID

        Returns:
            最后一条消息或 None
        """
        messages, _ = self.get_messages(user_id, limit=1)
        return messages[0] if messages else None

    def generate_topic_id(self) -> str:
        """生成新的话题 ID"""
        return str(uuid.uuid4())[:8]
