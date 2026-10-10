from pathlib import Path
from secrets import token_hex
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from app.db import init_db
from app.routes.customers import router as customers_router
from app.routes.orders import router as orders_router
from app.routes.tickets import router as tickets_router
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


APP_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MiniBiz Benchmark",
    version="0.1.0",
    lifespan=lifespan,
)

# Benchmark local: phiên cũ hết hiệu lực khi server khởi động lại.
# Mỗi lượt baseline sau này phải dùng browser context mới.
app.add_middleware(
    SessionMiddleware,
    secret_key=token_hex(32),
    session_cookie="minibiz_session",
    same_site="lax",
)

app.include_router(customers_router)
# Đăng ký các trang và API của module đơn hàng.
app.include_router(orders_router)
# Đăng ký giao diện Support và API đọc dữ liệu phục vụ chấm task.
app.include_router(tickets_router)
app.mount(
    "/static",
    StaticFiles(directory=str(APP_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(
    directory=str(APP_DIR / "templates"),
)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page_title": "MiniBiz"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
