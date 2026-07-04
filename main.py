from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

from app.routes import auth, meta, transactions, transactions_summary, upload

S3_BUCKET_NAME = "expense-tracker-db-dev"
S3_FILE_KEY = "test_s3.txt"


class FileUpdate(BaseModel):
    content: str

app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    description="API for managing expense transactions, summaries, and bank statement uploads.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "health", "description": "Health check"},
        {"name": "s3", "description": "S3 file CRUD operations"},
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



@app.get("/api/health", tags=["health"])
def health() -> JSONResponse:
    try:
        s3 = boto3.client("s3")
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
        return JSONResponse(status_code=200, content={"status": "ok", "s3": "reachable"})
    except (ClientError, EndpointConnectionError, Exception) as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not ok", "s3": "unreachable", "error": str(e)},
        )


@app.post("/api/s3/file", tags=["s3"])
def create_file() -> dict[str, str]:
    try:
        s3 = boto3.client("s3")
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=S3_FILE_KEY, Body=b"Hello World")
        return {"message": f"'{S3_FILE_KEY}' created successfully"}
    except (ClientError, EndpointConnectionError, Exception) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/s3/file", tags=["s3"])
def read_file() -> dict[str, str]:
    try:
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=S3_FILE_KEY)
        content = response["Body"].read().decode("utf-8")
        return {"file": S3_FILE_KEY, "content": content}
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise HTTPException(status_code=404, detail=f"'{S3_FILE_KEY}' not found")
        raise HTTPException(status_code=500, detail=str(e))
    except (EndpointConnectionError, Exception) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/s3/file", tags=["s3"])
def update_file(payload: FileUpdate) -> dict[str, str]:
    try:
        s3 = boto3.client("s3")
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=S3_FILE_KEY, Body=payload.content.encode("utf-8"))
        return {"message": f"'{S3_FILE_KEY}' updated successfully"}
    except (ClientError, EndpointConnectionError, Exception) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/s3/file", tags=["s3"])
def delete_file() -> dict[str, str]:
    try:
        s3 = boto3.client("s3")
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=S3_FILE_KEY)
        return {"message": f"'{S3_FILE_KEY}' deleted successfully"}
    except (ClientError, EndpointConnectionError, Exception) as e:
        raise HTTPException(status_code=500, detail=str(e))

