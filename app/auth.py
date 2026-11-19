import hmac

from fastapi import HTTPException, Request


def require_token(request: Request) -> None:
    expected = request.app.state.settings.api_token
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    ok = (
        bool(expected)
        and scheme.lower() == "bearer"
        and hmac.compare_digest(token.encode(), expected.encode())
    )
    if not ok:
        raise HTTPException(status_code=401, detail="unauthorized")
