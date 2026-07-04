import os
import tempfile
from pathlib import Path

import boto3
import xlrd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import UserModel, get_current_user

from google.adk.agents import Agent,LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams, StdioServerParameters
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

router = APIRouter(
    prefix="/api",
    tags=["upload"],
    dependencies=[Depends(get_current_user)],
)

HEADER_ROW = 12

os.environ["AWS_PROFILE"] = "bedrock-role" # tells the AWS SDK to use the "bedrock-role" profile you created in your AWS config file
os.environ["AWS_REGION"] = "us-east-1" # specifies which AWS region to use for API calls
#CLAUDE_SONNET_35 = "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_ID = "bedrock/openai.gpt-oss-120b-1:0"
APP_NAME = "agent_app"
bedrock_runtime = boto3.client('bedrock-runtime')



agent = LlmAgent(
        name="Agent",
        model=LiteLlm(model=MODEL_ID),
        description="Dedicated agent for logging personal thoughts, categorizing moods, and generating summaries.",
        instruction="You are expert in writting code in python",
        tools=[]
    )

session_service = InMemorySessionService() 
session: Session = None  # Global variable to hold the session
runner = Runner(
    agent=agent, 
    session_service=session_service,
    app_name=APP_NAME
)

async def get_or_create_session(user_id, session_id):
    # 1. Attempt to retrieve the session
    session = await session_service.get_session(
        app_name=APP_NAME, 
        user_id=user_id, 
        session_id=session_id
    )
    
    # 2. If it doesn't exist, create it
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        print(f"Created new session: {session_id}")
    else:
        print(f"Retrieved existing session: {session_id}")
        
    return session

class ExcelRecord(BaseModel):
    S_No: int | None = None
    Value_Date: str | None = None
    Transaction_Date: str | None = None
    Cheque_Number: str | None = None
    Transaction_Remarks: str | None = None
    Withdrawal_Amount_INR: float | None = None
    Deposit_Amount_INR: float | None = None
    Balance_INR: float | None = None


class ExcelUploadResponse(BaseModel):
    filename: str
    record_count: int
    records: list[dict]


def parse_xls(filepath: str) -> list[dict]:
    wb = xlrd.open_workbook(filepath)
    sh = wb.sheet_by_index(0)

    if sh.nrows <= HEADER_ROW:
        return []

    headers = [sh.cell_value(HEADER_ROW, c).strip() for c in range(sh.ncols)]

    records = []
    for r in range(HEADER_ROW + 1, sh.nrows):
        row_vals = [sh.cell_value(r, c) for c in range(sh.ncols)]
        sno_raw = row_vals[1]
        sno = str(sno_raw).strip()
        if not sno:
            continue
        try:
            int(sno)
        except ValueError:
            break

        record = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            val = row_vals[i]
            if h == "S No.":
                val = int(sno_raw)
            elif h in ("Withdrawal Amount(INR)", "Deposit Amount(INR)", "Balance(INR)"):
                val = float(val) if val else 0.0
            record[h] = val
        records.append(record)

    return records

@router.get("/test-agent", summary="Test API endpoint", description="Returns a simple JSON response to test the API.")
async def test_agent():
    await get_or_create_session(str("test_user"), str("test_session"))
    message = types.Content(
            role="user", 
            parts=[types.Part(text="Write a python function to add two numbers")],
        )
    events = runner.run(
        user_id=str("test_user"), 
        session_id=str("test_session"), 
        new_message=message
    )
    final_text = ""
    for event in events:
        if event.is_final_response():
            final_text = event.content.parts[0].text
            break
    return {"message": final_text}

@router.post(
    "/upload-excel",
    response_model=ExcelUploadResponse,
    summary="Upload bank statement Excel",
    description="Upload an ICICI bank statement (.xls) file. The file is parsed and all transaction rows are returned as JSON.",
    responses={
        400: {"description": "Invalid file type"},
        422: {"description": "Failed to parse Excel file"},
    },
)
async def upload_excel(file: UploadFile = File(..., description="Bank statement .xls file")):
    if not file.filename or not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xls and .xlsx files are supported")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        records = parse_xls(tmp_path)
    except xlrd.XLRDError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel file: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return ExcelUploadResponse(filename=file.filename, record_count=len(records), records=records)
