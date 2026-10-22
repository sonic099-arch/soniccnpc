from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.crud import create_crud_router
from app.api.resources import RESOURCES
from app.core.config import get_settings
from app.core.database import get_engine


def create_app():
    application = FastAPI(
        title="北田公司气井智能分析系统",
        description="第一阶段 · 任务1：数据模型和基础管理接口。当前不含生产异常分析能力，仅供本地开发。",
        version="0.1.0",
        openapi_tags=[{"name": label} for _, _, label in RESOURCES],
    )
    application.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                               allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "请求参数无效，请检查字段类型、必填项及时间格式（必须包含时区）", "fields": [".".join(map(str, e["loc"])) for e in exc.errors()]})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        # 不把 SQL、连接串和内部错误返回客户端。
        return JSONResponse(status_code=503, content={"detail": "数据库服务暂不可用，请检查连接和迁移状态"})

    @application.get("/health", tags=["运行状态"], summary="服务存活检查")
    def health():
        return {"status": "ok", "stage": "任务1"}

    @application.get("/ready", tags=["运行状态"], summary="数据库及迁移就绪检查")
    def ready():
        with get_engine().connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0001_initial":
            return JSONResponse(status_code=503, content={"detail": "数据库迁移未就绪"})
        return {"status": "ok", "revision": revision}

    for slug, model, label in RESOURCES:
        application.include_router(create_crud_router(slug, model, label), prefix="/api/v1")
    return application

app = create_app()
