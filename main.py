from dotenv import load_dotenv
load_dotenv(override=True)

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from passlib.hash import bcrypt
from db import q, x

app = FastAPI(title="Back (registro/login)")

# CORS
allow = os.getenv("ALLOW_ORIGINS", "http://localhost:5500").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[a.strip() for a in allow if a.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "running", "health": "/healthz", "docs": "/docs"}

@app.get("/favicon.ico")
def favicon():
    return Response(content=b"", media_type="image/x-icon", status_code=204)

class RegisterIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

class LoginIn(BaseModel):
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

@app.get("/healthz")
def healthz():
    try:
        ok = q("SELECT 1 AS ok")
        return {"ok": bool(ok and ok[0].get("ok") == 1)}
    except Exception as e:
        return {"ok": False, "db_error": str(e)}

@app.post("/api/register")
def register(p: RegisterIn):
    if q("SELECT 1 FROM dbo.Usuarios WHERE Correo = ?", (p.correo,)):
        raise HTTPException(409, "Correo ya registrado")
    pw_hash = bcrypt.hash(p.password)
    x("INSERT INTO dbo.Usuarios (Nombre, Correo, PasswordHash) VALUES (?, ?, ?)",
      (p.nombre, p.correo, pw_hash))
    return {"message": "Usuario creado"}

@app.post("/api/login")
def login(p: LoginIn):
    rows = q("SELECT ID_Usuario, Nombre, Correo, PasswordHash FROM dbo.Usuarios WHERE Correo = ?",
             (p.correo,))
    if not rows or not bcrypt.verify(p.password, rows[0]["PasswordHash"]):
        raise HTTPException(401, "Credenciales inválidas")
    u = rows[0]
    return {"message": "Login OK", "user": {"id": u["ID_Usuario"], "nombre": u["Nombre"], "correo": u["Correo"]}}
