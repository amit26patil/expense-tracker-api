from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.routes import meta, transactions, transactions_summary

app = FastAPI(title="Expense Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions_summary.summary_router)
app.include_router(transactions.router)
app.include_router(meta.router)



@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

