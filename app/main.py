import os
from typing import Optional

import boto3
from botocore.config import Config
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

ENDPOINT = os.getenv("S3_ENDPOINT", "https://s3.1yunpan.com")
REGION = os.getenv("S3_REGION", "auto")
BUCKET = os.environ["S3_BUCKET"]
ACCESS_KEY = os.environ["S3_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["S3_SECRET_ACCESS_KEY"]
PLUGIN_API_KEY = os.environ["PLUGIN_API_KEY"]

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 3, "mode": "standard"},
    ),
)

app = FastAPI(title="1yunpan GPT Action API", version="1.1.0")


def require_auth(x_api_key: Optional[str]) -> None:
    if not PLUGIN_API_KEY or x_api_key != PLUGIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def clean_key(value: str) -> str:
    return value.strip().lstrip("/")


class TextUpload(BaseModel):
    key: str
    content: str
    content_type: str = "text/plain; charset=utf-8"


class CopyMove(BaseModel):
    source: str
    destination: str


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True, "service": "1yunpan-gpt-action-api"}


@app.get("/files")
def list_files(
    prefix: str = "",
    recursive: bool = False,
    limit: int = 100,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    limit = max(1, min(limit, 500))
    args = {"Bucket": BUCKET, "Prefix": clean_key(prefix)}
    if not recursive:
        args["Delimiter"] = "/"

    results = []
    for page in s3.get_paginator("list_objects_v2").paginate(**args):
        for item in page.get("CommonPrefixes", []):
            results.append({"type": "directory", "key": item["Prefix"]})
            if len(results) >= limit:
                return results
        for item in page.get("Contents", []):
            results.append({
                "type": "file",
                "key": item["Key"],
                "size": item.get("Size", 0),
                "last_modified": (
                    item["LastModified"].isoformat()
                    if item.get("LastModified") else None
                ),
                "etag": item.get("ETag"),
            })
            if len(results) >= limit:
                return results
    return results


@app.get("/search")
def search_files(
    q: str,
    prefix: str = "",
    limit: int = 100,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    needle = q.lower()
    limit = max(1, min(limit, 500))
    results = []

    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=clean_key(prefix)
    ):
        for item in page.get("Contents", []):
            if needle in item["Key"].lower():
                results.append({
                    "key": item["Key"],
                    "size": item.get("Size", 0),
                    "last_modified": (
                        item["LastModified"].isoformat()
                        if item.get("LastModified") else None
                    ),
                })
                if len(results) >= limit:
                    return results
    return results


@app.get("/files/info")
def file_info(
    key: str,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    key = clean_key(key)
    response = s3.head_object(Bucket=BUCKET, Key=key)
    return {
        "key": key,
        "size": response.get("ContentLength"),
        "content_type": response.get("ContentType"),
        "etag": response.get("ETag"),
        "last_modified": (
            response["LastModified"].isoformat()
            if response.get("LastModified") else None
        ),
        "metadata": response.get("Metadata", {}),
    }


@app.get("/files/download-url")
def download_url(
    key: str,
    expires: int = 3600,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    expires = max(60, min(expires, 604800))
    key = clean_key(key)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires,
    )
    return {"url": url, "expires_in": expires, "key": key}


@app.post("/files/upload-text")
def upload_text(
    body: TextUpload,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    key = clean_key(body.key)
    raw = body.content.encode("utf-8")
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=raw,
        ContentType=body.content_type,
    )
    return {"ok": True, "key": key, "size": len(raw)}


@app.post("/files/folder")
def create_folder(
    prefix: str,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    key = clean_key(prefix)
    if not key.endswith("/"):
        key += "/"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=b"",
        ContentType="application/x-directory",
    )
    return {"ok": True, "folder": key}


@app.post("/files/copy")
def copy_file(
    body: CopyMove,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    source = clean_key(body.source)
    destination = clean_key(body.destination)
    s3.copy_object(
        Bucket=BUCKET,
        CopySource={"Bucket": BUCKET, "Key": source},
        Key=destination,
    )
    return {"ok": True, "source": source, "destination": destination}


@app.post("/files/move")
def move_file(
    body: CopyMove,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    source = clean_key(body.source)
    destination = clean_key(body.destination)
    s3.copy_object(
        Bucket=BUCKET,
        CopySource={"Bucket": BUCKET, "Key": source},
        Key=destination,
    )
    s3.delete_object(Bucket=BUCKET, Key=source)
    return {"ok": True, "source": source, "destination": destination}


@app.delete("/files")
def delete_file(
    key: str,
    x_api_key: Optional[str] = Header(default=None),
):
    require_auth(x_api_key)
    key = clean_key(key)
    s3.delete_object(Bucket=BUCKET, Key=key)
    return {"ok": True, "deleted": key}
