from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import share_lot, price, nav

app = FastAPI(title="SGSKBackend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(share_lot.router)
app.include_router(price.router)
app.include_router(nav.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to SGSKBackend!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
