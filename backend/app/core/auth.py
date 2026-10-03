import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
bearer = HTTPBearer(auto_error=False)
def current_user(request: Request, credential: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credential:
        for token, user in request.app.state.services.settings.user_tokens.items():
            if secrets.compare_digest(token, credential.credentials):
                return user
    raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate":"Bearer"})
