import os
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["auth"])

def read_auth_config() -> dict[str, str]:
    """Read the OAuth2 client config from the JSON file."""
    try:
        import json
        with open(os.path.join(Path(__file__).resolve().parent.parent.parent, "expense-tracker-client.json"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError("OAuth2 client config file not found. Please create 'expense-tracker-client.json' with the client ID and secret.")
@router.get(
    "/auth/config",
    summary="Get OAuth2 client config",
    description="Returns the Google OAuth2 client ID and client secret for the frontend.",
)
def get_auth_config() -> dict[str, str]:
    return read_auth_config()
