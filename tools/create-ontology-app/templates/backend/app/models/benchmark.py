"""
Benchmark 测试模型
支持 AI 能力边界测试、回归测试、可视化调试
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class BenchmarkSuite(Base):
    __tablename__ = "benchmark_suites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    init_script = Column(String(100), nullable=True)  # Python script filename, NULL=default(init_data.py), "none"=skip
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cases = relationship("BenchmarkCase", back_populates="suite", cascade="all, delete-orphan",
                         order_by="BenchmarkCase.sequence_order")
    runs = relationship("BenchmarkRun", back_populates="suite", cascade="all, delete-orphan")


class BenchmarkCase(Base):
    __tablename__ = "benchmark_cases"

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("benchmark_suites.id", ondelete="CASCADE"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    input = Column(Text, nullable=False)
    run_as = Column(String(50), nullable=True)  # username to execute as (e.g. "front1"), NULL = current user
    assertions = Column(Text, nullable=False)  # JSON
    follow_up_fields = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suite = relationship("BenchmarkSuite", back_populates="cases")
    results = relationship("BenchmarkCaseResult", back_populates="case", cascade="all, delete-orphan")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    __table_args__ = (
        UniqueConstraint("suite_id", name="uq_benchmark_runs_suite_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("benchmark_suites.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)  # running, passed, failed, error
    total_cases = Column(Integer, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    suite = relationship("BenchmarkSuite", back_populates="runs")
    case_results = relationship("BenchmarkCaseResult", back_populates="run", cascade="all, delete-orphan")


class BenchmarkCaseResult(Base):
    __tablename__ = "benchmark_case_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("benchmark_cases.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)  # passed, failed, error, skipped
    debug_session_id = Column(String(100), nullable=True)
    actual_response = Column(Text, nullable=True)
    assertion_details = Column(Text, nullable=True)  # JSON
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    run = relationship("BenchmarkRun", back_populates="case_results")
    case = relationship("BenchmarkCase", back_populates="results")
