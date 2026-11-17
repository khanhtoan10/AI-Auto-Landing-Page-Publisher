from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.auth import router as auth_router
from api.health import router as health_router
from api.projects import router as projects_router
from api.versions import router as versions_router
from core.config import settings

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nhúng các Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(versions_router)

# Projects router hỗ trợ cả 2 tiền tố: /projects/{id} và /api/v1/projects/{id}
app.include_router(projects_router)
app.include_router(projects_router, prefix="/api/v1")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "AI Publisher Dashboard"},
    )


# Phục vụ trực tiếp giao diện frontend từ backend (ví dụ /pages/edit-project.html?id=1).
# Mount được khai báo sau cùng để không che các route API phía trên.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
