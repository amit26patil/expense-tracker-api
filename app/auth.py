import json
import logging

import boto3
import requests
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

S3_BUCKET = "expense-tracker-db-dev"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

security = HTTPBearer()


class UserModel(BaseModel):
    email: str
    name: str
    picture: str = ""


def _validate_google_token(token: str) -> dict:
    """Validate the Google OAuth2 access token via Google's tokeninfo endpoint."""
    try:
        resp = requests.get(GOOGLE_TOKENINFO_URL, params={"access_token": token}, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to reach Google tokeninfo endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to validate token with Google",
        )


def _get_or_create_user_in_s3(user_info: dict) -> UserModel:
    """Fetch user from S3; create if not present."""
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    user = UserModel(email=email, name=name, picture=picture)
    s3_key = f"{email}/user.json"

    s3 = boto3.client("s3")

    try:
        s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            try:
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=json.dumps(user.model_dump(), indent=2).encode("utf-8"),
                    ContentType="application/json",
                )
                logger.info("Created user profile in S3: %s", s3_key)
            except ClientError as put_err:
                logger.error("Failed to write user to S3: %s", put_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile",
                )
        else:
            logger.error("S3 error reading user profile: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read user profile",
            )

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserModel:
    """FastAPI dependency: validate token and return the authenticated user."""
    token_info = _validate_google_token(credentials.credentials)
    return _get_or_create_user_in_s3(token_info)
