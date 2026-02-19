"""
Benchmark 测试管理 API
Suite + Case CRUD, 执行, 导入/导出
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.benchmark import BenchmarkSuite, BenchmarkCase, BenchmarkRun, BenchmarkCaseResult
from app.hotel.models.ontology import Employee
from app.models.schemas import (
    BenchmarkSuiteCreate, BenchmarkSuiteUpdate, BenchmarkSuiteResponse,
    BenchmarkSuiteDetailResponse,
    BenchmarkCaseCreate, BenchmarkCaseUpdate, BenchmarkCaseResponse,
    BenchmarkCaseReorderRequest,
    BenchmarkGenerateAssertionsRequest,
    BenchmarkRunRequest, BenchmarkRunResponse, BenchmarkRunDetailResponse,
    BenchmarkCaseResultResponse,
)
from app.security.auth import require_manager

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


# ============== Init Scripts ==============

@router.get("/init-scripts")
def list_init_scripts_endpoint(
    current_user: Employee = Depends(require_manager),
):
    from app.services.benchmark_runner import list_init_scripts

    scripts = list_init_scripts()
    return {"scripts": scripts}


# ============== Suite CRUD ==============

@router.get("/suites", response_model=List[BenchmarkSuiteResponse])
def list_suites(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    query = db.query(BenchmarkSuite)
    if category:
        query = query.filter(BenchmarkSuite.category == category)
    suites = query.order_by(BenchmarkSuite.id).all()

    results = []
    for s in suites:
        resp = BenchmarkSuiteResponse.model_validate(s)
        resp.case_count = len(s.cases)
        results.append(resp)
    return results


@router.post("/suites", response_model=BenchmarkSuiteResponse, status_code=201)
def create_suite(
    data: BenchmarkSuiteCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = BenchmarkSuite(**data.model_dump())
    db.add(suite)
    db.commit()
    db.refresh(suite)
    resp = BenchmarkSuiteResponse.model_validate(suite)
    resp.case_count = 0
    return resp


@router.get("/suites/{suite_id}", response_model=BenchmarkSuiteDetailResponse)
def get_suite(
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = db.query(BenchmarkSuite).filter(BenchmarkSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    cases = [BenchmarkCaseResponse.model_validate(c) for c in suite.cases]
    resp = BenchmarkSuiteDetailResponse.model_validate(suite)
    resp.case_count = len(cases)
    resp.cases = cases
    return resp


@router.put("/suites/{suite_id}", response_model=BenchmarkSuiteResponse)
def update_suite(
    suite_id: int,
    data: BenchmarkSuiteUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = db.query(BenchmarkSuite).filter(BenchmarkSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(suite, field, value)
    db.commit()
    db.refresh(suite)

    resp = BenchmarkSuiteResponse.model_validate(suite)
    resp.case_count = len(suite.cases)
    return resp


@router.delete("/suites/{suite_id}")
def delete_suite(
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = db.query(BenchmarkSuite).filter(BenchmarkSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    db.delete(suite)
    db.commit()
    return {"message": "已删除"}


# ============== Case CRUD ==============

@router.post("/suites/{suite_id}/cases", response_model=BenchmarkCaseResponse, status_code=201)
def create_case(
    suite_id: int,
    data: BenchmarkCaseCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = db.query(BenchmarkSuite).filter(BenchmarkSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    # Auto-assign sequence_order if not provided
    if data.sequence_order is None:
        max_order = max((c.sequence_order for c in suite.cases), default=0)
        data.sequence_order = max_order + 1

    case = BenchmarkCase(suite_id=suite_id, **data.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    return BenchmarkCaseResponse.model_validate(case)


@router.put("/cases/{case_id}", response_model=BenchmarkCaseResponse)
def update_case(
    case_id: int,
    data: BenchmarkCaseUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    case = db.query(BenchmarkCase).filter(BenchmarkCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case 不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return BenchmarkCaseResponse.model_validate(case)


@router.delete("/cases/{case_id}")
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    case = db.query(BenchmarkCase).filter(BenchmarkCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case 不存在")

    db.delete(case)
    db.commit()
    return {"message": "已删除"}


@router.put("/suites/{suite_id}/cases/reorder")
def reorder_cases(
    suite_id: int,
    data: BenchmarkCaseReorderRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    suite = db.query(BenchmarkSuite).filter(BenchmarkSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    case_map = {c.id: c for c in suite.cases}
    for order, case_id in enumerate(data.case_ids, start=1):
        if case_id not in case_map:
            raise HTTPException(status_code=400, detail=f"Case {case_id} 不属于此 Suite")
        case_map[case_id].sequence_order = order

    db.commit()
    return {"message": "排序已更新"}


# ============== AI Assertion Generation ==============

@router.post("/generate-assertions")
def generate_assertions_endpoint(
    data: BenchmarkGenerateAssertionsRequest,
    current_user: Employee = Depends(require_manager),
):
    from app.services.benchmark_service import generate_assertions

    try:
        result = generate_assertions(data.input, data.case_type)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成断言失败: {str(e)}")


# ============== Execution ==============

@router.post("/run", response_model=List[BenchmarkRunResponse])
def run_benchmark(
    data: BenchmarkRunRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    from app.services.benchmark_runner import run_suites

    if not data.suite_ids:
        raise HTTPException(status_code=400, detail="suite_ids 不能为空")

    runs = run_suites(data.suite_ids, db, current_user)
    return [BenchmarkRunResponse.model_validate(r) for r in runs]


@router.get("/runs", response_model=List[BenchmarkRunResponse])
def list_runs(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    runs = db.query(BenchmarkRun).order_by(BenchmarkRun.suite_id).all()
    return [BenchmarkRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{suite_id}", response_model=BenchmarkRunDetailResponse)
def get_run_detail(
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    run = db.query(BenchmarkRun).filter_by(suite_id=suite_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="该 Suite 无执行记录")

    case_results = [BenchmarkCaseResultResponse.model_validate(cr) for cr in run.case_results]
    resp = BenchmarkRunDetailResponse.model_validate(run)
    resp.case_results = case_results
    return resp


@router.post("/reset-db")
def reset_db_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    from init_data import reset_business_data

    reset_business_data(db)
    return {"message": "业务数据已重置"}


# ============== YAML Import/Export ==============

@router.get("/export")
def export_all(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    from app.services.benchmark_service import export_suites

    yaml_content = export_suites(db)
    from fastapi.responses import Response as RawResponse
    return RawResponse(content=yaml_content, media_type="text/yaml")


@router.get("/export/{suite_id}")
def export_suite(
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    from app.services.benchmark_service import export_suites

    suite = db.query(BenchmarkSuite).filter_by(id=suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite 不存在")

    yaml_content = export_suites(db, suite_ids=[suite_id])
    from fastapi.responses import Response as RawResponse
    return RawResponse(content=yaml_content, media_type="text/yaml")


@router.post("/import")
async def import_suites_from_yaml(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
    mode: str = Query("merge"),
):
    """Import suites from YAML. Send YAML content as request body."""
    from app.services.benchmark_service import import_suites

    body = await request.body()
    yaml_content = body.decode("utf-8")

    if not yaml_content.strip():
        raise HTTPException(status_code=400, detail="请求体不能为空")

    try:
        result = import_suites(db, yaml_content, mode=mode)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败: {str(e)}")
