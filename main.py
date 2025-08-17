# main.py
import os
from fastapi import FastAPI, HTTPException # type: ignore
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
from db import query, execute
from auth import hash_password, verify_password

load_dotenv()

app = FastAPI(title="API Azure SQL (FastAPI)")

# CORS: ajusta los orígenes (para tu front)
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

class LoginIn(BaseModel):
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

@app.get("/healthz")
def healthz():
    r = query("SELECT 1 AS ok")
    return {"ok": bool(r and r[0].get("ok") == 1)}

@app.post("/api/register")
def register(p: RegisterIn):
    if query("SELECT 1 FROM dbo.Usuarios WHERE Correo = ?", (p.correo,)):
        raise HTTPException(status_code=409, detail="Correo ya registrado")
    execute(
        "INSERT INTO dbo.Usuarios (Nombre, Correo, PasswordHash) VALUES (?, ?, ?)",
        (p.nombre, p.correo, hash_password(p.password))
    )
    return {"message": "Usuario creado"}

@app.post("/api/login")
def login(p: LoginIn):
    rows = query(
        "SELECT ID_Usuario, Nombre, Correo, PasswordHash FROM dbo.Usuarios WHERE Correo = ?",
        (p.correo,)
    )
    if not rows or not verify_password(p.password, rows[0]["PasswordHash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    u = rows[0]
    # Si luego quieres JWT/cookies HttpOnly, aquí es donde se emiten
    return {"message": "Login OK", "user": {"id": u["ID_Usuario"], "nombre": u["Nombre"], "correo": u["Correo"]}}
