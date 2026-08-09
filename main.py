from fastapi import FastAPI

app = FastAPI(title="SGSKBackend")

@app.get("/")
def read_root():
    return {"message": "Welcome to SGSKBackend!"}
