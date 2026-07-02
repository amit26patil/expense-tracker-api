from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, meta, transactions, transactions_summary, upload

app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    description="API for managing expense transactions, summaries, and bank statement uploads.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "health", "description": "Health check"},
        {"name": "transactions", "description": "CRUD operations on transactions"},
        {"name": "transaction_summary", "description": "Monthly summaries and details"},
        {"name": "meta", "description": "Categories and currencies"},
        {"name": "upload", "description": "Upload and parse bank statement Excel files"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(transactions_summary.summary_router)
app.include_router(transactions.router) 
app.include_router(meta.router)
app.include_router(upload.router)



@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

