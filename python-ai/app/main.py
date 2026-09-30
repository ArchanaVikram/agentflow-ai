import logging

from fastapi import Depends, FastAPI

from app.routes import router
from app.security import verify_api_key

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AgentFlow AI - Agent Service", version="0.1.0")
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/secure-test", dependencies=[Depends(verify_api_key)])
async def secure_test():
    return {"message": "You are authorized"}