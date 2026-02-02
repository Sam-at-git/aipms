# AIPMS - 智能酒店管理系统

基于 Palantir 架构思想的本体运行时酒店管理系统原型。

## 技术栈

### 后端
- **FastAPI** - 高性能 Python Web 框架
- **SQLAlchemy** - ORM 数据库操作
- **SQLite** - 轻量级数据库
- **Pydantic** - 数据验证
- **JWT** - 身份认证

### 前端
- **React 18** - 用户界面
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **Zustand** - 状态管理
- **Vite** - 构建工具
- **Recharts** - 图表库
- **Lucide React** - 图标库

## 项目结构

```
aihotel/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── models/         # 本体对象定义
│   │   ├── services/       # 业务服务层
│   │   ├── routers/        # API 路由
│   │   ├── security/       # 认证授权
│   │   ├── database.py     # 数据库配置
│   │   └── main.py         # 应用入口
│   ├── init_data.py        # 初始化数据脚本
│   └── requirements.txt
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # 通用组件
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API 服务
│   │   ├── store/          # 状态管理
│   │   ├── types/          # TypeScript 类型
│   │   └── App.tsx         # 应用入口
│   └── package.json
└── docs/                   # 文档
```

## 快速开始

### 1. 启动后端

```bash
cd backend

# 使用 uv 安装依赖并创建虚拟环境
uv sync

# 初始化数据
uv run python init_data.py

# 启动服务
uv run uvicorn app.main:app --reload --port 8000
```

> 如果没有安装 uv，请先安装：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 3. 访问系统

- 前端地址：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 经理 | manager | 123456 |
| 前台 | front1 | 123456 |
| 清洁员 | cleaner1 | 123456 |

## 核心功能

### 1. 房态管理
- 房态实时展示（数字孪生）
- 按楼层/状态筛选
- 手动修改房态

### 2. 预订管理
- 新建预订
- 预订查询/搜索
- 取消预订
- 今日预抵列表

### 3. 入住/退房
- 预订入住
- 散客入住（Walk-in）
- 续住、换房
- 退房结账
- 自动生成清洁任务

### 4. 账单管理
- 账单查看
- 支付记录
- 账单调整（经理权限）

### 5. 任务管理
- 自动创建清洁任务
- 任务分配
- 清洁员任务执行

### 6. 统计报表
- 入住率统计
- 营收统计
- 数据可视化

### 7. AI 智能助手
- 自然语言交互
- OODA 循环运行时
- 人类在环确认机制

## Palantir 架构原则

本系统遵循以下核心原则：

1. **语义驱动（Ontology-Driven）**
   - 所有操作通过本体对象进行
   - 定义了 Room、Guest、Reservation、StayRecord 等核心对象

2. **安全内嵌（Security-Embedded）**
   - 属性级访问控制
   - 角色权限隔离

3. **OODA 循环运行时**
   - Observe：捕获自然语言指令
   - Orient：意图识别和实体提取
   - Decide：业务规则检查
   - Act：执行状态变更

4. **人类在环（Human-in-the-loop）**
   - 关键操作需确认
   - AI 建议需人工审批

5. **配置即部署**
   - 业务规则元数据化
   - 退房联动、清洁联动等自动化

6. **AI 自然增强**
   - 智能助手对话交互
   - 自动生成操作建议

## 业务联动规则

- **退房联动**：退房 → 房间变脏房 → 自动创建清洁任务
- **清洁联动**：清洁完成 → 房间变空闲
- **价格联动**：价格策略优先级匹配

## 初始化数据

系统预置：
- 3 种房型：标间、大床房、豪华间
- 40 间房间（2-5 楼）
- 6 名员工
- 周末价格策略

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档。

主要接口：
- `/auth/*` - 认证相关
- `/rooms/*` - 房间管理
- `/reservations/*` - 预订管理
- `/checkin/*` - 入住管理
- `/checkout/*` - 退房管理
- `/tasks/*` - 任务管理
- `/billing/*` - 账单管理
- `/reports/*` - 统计报表
- `/ai/*` - AI 对话

## License

MIT
