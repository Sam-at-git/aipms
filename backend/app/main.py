"""
AIPMS 主应用入口
基于 Palantir 架构思想的酒店管理系统
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, rooms, reservations, checkin, checkout, tasks, billing, employees, reports, ai, prices, settings, audit_logs, guests, conversations

# 创建应用
app = FastAPI(
    title="AIPMS - 智能酒店管理系统",
    description="基于 Palantir 架构思想的本体运行时酒店管理系统",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(guests.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(checkin.router)
app.include_router(checkout.router)
app.include_router(tasks.router)
app.include_router(billing.router)
app.include_router(employees.router)
app.include_router(reports.router)
app.include_router(prices.router)
app.include_router(audit_logs.router)
app.include_router(ai.router)
app.include_router(conversations.router)
app.include_router(settings.router)


@app.on_event("startup")
def startup():
    """应用启动时初始化数据库"""
    init_db()


@app.get("/")
def root():
    """根路径"""
    return {
        "name": "AIPMS - 智能酒店管理系统",
        "version": "1.0.0",
        "description": "基于 Palantir 架构思想的本体运行时"
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}
