"""将明确的 ORM 列契约转换为有类型的 OpenAPI 模型，避免14套CRUD字段漂移。"""
from datetime import datetime, timezone
from typing import Any, get_type_hints, get_args
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, create_model, model_validator
from sqlalchemy import DateTime, String, Float, JSON

class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_ranges(self):
        values = self.model_dump(exclude_unset=True)
        for start, end in (("effective_start", "effective_end"), ("window_start", "window_end"), ("started_at", "ended_at")):
            if values.get(start) and values.get(end) and values[end] <= values[start]:
                raise ValueError("结束时间必须晚于开始时间")
        return self

def build_schemas(model):
    create_fields, patch_fields, read_fields = {}, {}, {}
    hints = get_type_hints(model)
    def column_type(col):
        return get_args(hints[col.name])[0] if isinstance(col.type, JSON) else col.type.python_type
    for col in model.__table__.columns:
        typ: Any = AwareDatetime if isinstance(col.type, DateTime) else column_type(col)
        if col.nullable:
            typ = typ | None
        options = {}
        if isinstance(col.type, String):
            options = {"max_length": col.type.length, "min_length": 1}
        if isinstance(col.type, Float):
            options = {"allow_inf_nan": False}
        read_fields[col.name] = (typ, ...)
        if col.name in ("id", "created_at"):
            continue
        if col.default is not None:
            if col.default.is_callable:
                default = Field(default_factory=lambda fn=col.default.arg: fn(None), **options)
            else:
                default = Field(default=col.default.arg, **options)
        elif col.nullable:
            default = Field(default=None, **options)
        else:
            default = Field(**options)
        create_fields[col.name] = (typ, default)
        patch_fields[col.name] = (typ, Field(default=None, **options))
    create = create_model(model.__name__ + "Create", __base__=InputModel, **create_fields)
    patch = create_model(model.__name__ + "Update", __base__=InputModel, **patch_fields)
    # 返回值不再次限定时间带时区：SQLite 隔离测试不保留时区，生产 PG 使用 timestamptz。
    read_fields = {c.name: ((column_type(c) | None) if c.nullable else column_type(c), ...) for c in model.__table__.columns}
    read = create_model(model.__name__ + "Read", __config__=ConfigDict(from_attributes=True), **read_fields)
    return create, patch, read

def normalize_times(values):
    return {k: v.astimezone(timezone.utc) if isinstance(v, datetime) else v for k, v in values.items()}
