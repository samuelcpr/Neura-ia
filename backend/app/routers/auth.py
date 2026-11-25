from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    usuario: str
    senha: str


@router.post("/login")
def login(req: LoginRequest):
    if req.usuario != auth.ADMIN_USER or req.senha != auth.ADMIN_PASSWORD:
        raise HTTPException(401, "Usuário ou senha incorretos")
    return {"token": auth.create_token(req.usuario), "usuario": req.usuario}


@router.get("/me")
def me(user: str = Depends(auth.require_auth)):
    return {"usuario": user}
