# 1yunpan GPT Action API

A small FastAPI + boto3 proxy that exposes a 1yunpan.com S3-compatible bucket to a custom GPT through GPT Actions.

## Architecture

```text
Custom GPT
   │ HTTPS + X-API-Key
   ▼
FastAPI proxy
   │ AWS S3 Signature V4
   ▼
1yunpan S3
```

The 1yunpan S3 credentials stay on the server. They are never placed in the OpenAPI schema or GPT instructions.

## Supported operations

- List files/directories
- Search filenames
- Get object metadata
- Generate temporary download URLs
- Upload UTF-8 text
- Create folder markers
- Copy
- Move / rename
- Delete

## Docker

Build:

```bash
docker build -t 1yunpan-gpt-action .
```

Run:

```bash
docker run --rm -p 8080:8080 --env-file .env 1yunpan-gpt-action
```

The container also honors a platform-provided `PORT` environment variable.

Health check:

```text
GET /health
```

## Environment variables

Copy `.env.example` to `.env` and fill in:

```text
S3_ENDPOINT=https://s3.1yunpan.com
S3_REGION=auto
S3_BUCKET=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
PLUGIN_API_KEY=...
```

Generate a proxy API key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit `.env`.

## Connect to a custom GPT

1. Deploy this service to a public HTTPS URL.
2. Replace `https://YOUR-DOMAIN.example.com` in `openapi.yaml` with that URL.
3. In the GPT editor, add an Action and import `openapi.yaml`.
4. Configure API-key authentication using:
   - Header name: `X-API-Key`
   - Value: the same value as `PLUGIN_API_KEY`
5. Add the contents of `GPT_INSTRUCTIONS.txt` to the GPT instructions.

The service must be reachable over HTTPS by the GPT Action.

## Security

The proxy API key and the 1yunpan S3 credentials are separate secrets.

Do not put any real secret in:
- `openapi.yaml`
- `GPT_INSTRUCTIONS.txt`
- GitHub
- Dockerfile
- README

If an S3 secret has ever been exposed publicly, rotate/regenerate it before deployment.

## Notes

This project uses path-style S3 addressing and AWS Signature V4 because the 1yunpan endpoint is S3-compatible.

The API intentionally exposes text upload rather than arbitrary multipart file upload in this version. This keeps the GPT Action schema simple and predictable.
