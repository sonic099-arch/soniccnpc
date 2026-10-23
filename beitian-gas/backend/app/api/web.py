"""已构建网页的同源静态托管；仅内网启动器显式启用。"""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html


def mount_web(app, dist: Path):
    dist = dist.resolve()
    if not all((dist / p).is_file() for p in ['index.html', 'docs-assets/swagger-ui-bundle.js', 'docs-assets/swagger-ui.css', 'docs-assets/favicon-32x32.png']):
        raise RuntimeError('缺少内网构建文件，请运行 python scripts/lan.py 完成构建')
    app.mount('/docs-assets', StaticFiles(directory=dist / 'docs-assets'), name='offline-doc-assets')

    @app.get('/docs', include_in_schema=False)
    def docs():
        return get_swagger_ui_html(openapi_url='/openapi.json', title=app.title+' · 接口文档',
            swagger_js_url='/docs-assets/swagger-ui-bundle.js', swagger_css_url='/docs-assets/swagger-ui.css',
            swagger_favicon_url='/docs-assets/favicon-32x32.png', swagger_ui_parameters={'validatorUrl': None})

    @app.get('/redoc', include_in_schema=False)
    def redoc():
        return RedirectResponse('/docs')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        target = (dist / path).resolve()
        if not target.is_relative_to(dist) or any(part.startswith('.') for part in Path(path).parts):
            raise HTTPException(404, '文件不存在')
        if target.is_file():
            return FileResponse(target)
        if path.split('/')[0] in {'api', 'assets', 'docs-assets'} or Path(path).suffix:
            raise HTTPException(404, '页面或文件不存在')
        return FileResponse(dist / 'index.html', headers={'Cache-Control': 'no-cache'})
