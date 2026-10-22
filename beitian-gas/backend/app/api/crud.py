from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError, create_model
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_session
from app.schemas.factory import build_schemas, normalize_times

SessionDep = Annotated[Session, Depends(get_session)]

def create_crud_router(slug, model, label):
    router = APIRouter(prefix="/" + slug, tags=[label])
    Create, Update, Read = build_schemas(model)
    Page = create_model(model.__name__ + "Page", items=(list[Read], ...), total=(int, ...), offset=(int, ...), limit=(int, ...))

    def commit(session):
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "记录冲突：请检查唯一值、关联记录、状态或数值和时间区间约束")

    def find(session, record_id):
        row = session.get(model, record_id)
        if row is None:
            raise HTTPException(404, "记录不存在")
        return row

    def checked_values(payload):
        return normalize_times(payload.model_dump())

    @router.get("", response_model=Page, summary=f"分页查询{label}")
    def list_records(session: SessionDep, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                     well_id: UUID | None = None, search: str | None = None, area: str | None = None):
        stmt = select(model)
        if well_id is not None:
            if not hasattr(model, "well_id"):
                raise HTTPException(422, "当前资源不支持按气井ID筛选")
            stmt = stmt.where(model.well_id == well_id)
        if search is not None or area is not None:
            if slug != "wells":
                raise HTTPException(422, "井号搜索及工区筛选仅适用于气井资源")
            if search is not None:
                stmt = stmt.where(model.well_number.contains(search, autoescape=True))
            if area is not None:
                stmt = stmt.where(model.area == area)
        total = session.scalar(select(func.count()).select_from(stmt.subquery()))
        items = session.scalars(stmt.order_by(model.created_at, model.id).offset(offset).limit(limit)).all()
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    @router.post("", response_model=Read, status_code=201, summary=f"新增{label}")
    def create_record(payload: Create, session: SessionDep):
        row = model(**checked_values(payload))
        session.add(row)
        commit(session)
        session.refresh(row)
        return row

    @router.get("/{record_id}", response_model=Read, summary=f"查询单条{label}")
    def get_record(record_id: UUID, session: SessionDep):
        return find(session, record_id)

    @router.patch("/{record_id}", response_model=Read, summary=f"更新{label}")
    def update_record(record_id: UUID, payload: Update, session: SessionDep):
        row = find(session, record_id)
        # 合并后再验证，保证只改结束时间也能检测非法区间，非空列不能被 PATCH 清空。
        values = {name: getattr(row, name) for name in Create.model_fields}
        values.update(payload.model_dump(exclude_unset=True))
        try:
            valid = Create.model_validate(values)
        except ValidationError:
            raise HTTPException(422, "更新无效：必填字段不得为空，结束时间必须晚于开始时间")
        for name, value in checked_values(valid).items():
            setattr(row, name, value)
        commit(session)
        session.refresh(row)
        return row

    @router.delete("/{record_id}", status_code=204, summary=f"删除{label}")
    def delete_record(record_id: UUID, session: SessionDep):
        session.delete(find(session, record_id))
        commit(session)
        return Response(status_code=204)
    return router
