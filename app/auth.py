import bcrypt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
import os
import secrets

def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    # bcrypt.checkpw requires bytes
    try:
        # bcrypt.checkpw requires bytes
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        print(f"Bcrypt Error: {e}")
        return False

def get_password_hash(password):
    # bcrypt.hashpw requires bytes and returns bytes. We store as string.
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

# dependency
def get_current_admin(request: Request):
    user = request.session.get("user")
    if not user:
        return None
    return user

def require_admin(request: Request):
    user = get_current_admin(request)
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    return user
