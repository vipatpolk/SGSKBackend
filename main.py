from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import get_settings
from routers import nav, portfolio, price, share_lot
from utils.http_client import lifespan


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class DirectAccessBlockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        headers = request.headers
        host = (headers.get("host") or "").lower().split(":")[0]
        forwarded_host = (headers.get("x-forwarded-host") or "").lower().split(":")[0]
        app_source = headers.get("x-app-source") or headers.get("x-requested-with")
        sec_fetch_dest = headers.get("sec-fetch-dest") or ""
        sec_fetch_mode = headers.get("sec-fetch-mode") or ""
        accept = headers.get("accept") or ""

        # 1. Block direct browser navigation (e.g. typing URL in browser, opening new tab)
        is_browser_direct_navigation = (
            sec_fetch_dest == "document"
            or sec_fetch_mode == "navigate"
            or ("text/html" in accept and not app_source)
        )
        if is_browser_direct_navigation and not app_source:
            return Response(
                status_code=403,
                content='{"detail": "Direct browser access to backend is prohibited. Please access via the ShareLot web application."}',
                media_type="application/json",
            )

        # 2. Block direct access targeting sgsk-backend.vercel.app without proxy/app signature
        if host == "sgsk-backend.vercel.app" or (host.endswith(".vercel.app") and "backend" in host):
            is_forwarded_from_frontend = bool(forwarded_host and forwarded_host != host)
            has_valid_app_signature = app_source in ("ShareLot", "ShareLot-Client")

            if not is_forwarded_from_frontend and not has_valid_app_signature:
                return Response(
                    status_code=403,
                    content='{"detail": "Direct access to backend origin is prohibited. Requests must originate through the web application proxy."}',
                    media_type="application/json",
                )

        return await call_next(request)


settings = get_settings()
is_prod = settings.environment.lower() == "production"

app = FastAPI(
    title="SGSKBackend",
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(DirectAccessBlockMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(share_lot.router)
app.include_router(price.router)
app.include_router(nav.router)
app.include_router(portfolio.router)


from utils.auth import verify_api_key
from fastapi import Depends


@app.get("/")
def read_root(api_key: str = Depends(verify_api_key)):
    return {"message": "Welcome to SGSKBackend!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
