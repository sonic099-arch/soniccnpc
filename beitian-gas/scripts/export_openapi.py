"""导出接口契约；不建立数据库连接。运行前需安装后端包。"""
import json
import os
from pathlib import Path
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg:///documentation_only")
from app.main import app
root = Path(__file__).resolve().parents[1]
(root / "docs" / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("已生成 docs/openapi.json")
