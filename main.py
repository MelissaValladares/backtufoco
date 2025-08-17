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

# Rutas “básicas” para que no veas 404
@app.get("/")
def root():
    return {"status": "running", "health": "/healthz", "docs": "/docs"}

@app.get("/favicon.ico")
def favicon():
    return Response(content=b"", media_type="image/x-icon", status_code=204)

# Modelos
class RegisterIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

class LoginIn(BaseModel):
    correo: EmailStr
    password: str = Field(min_length=8, max_length=100)

# Endpoints
@app.get("/healthz")
def healthz():
    try:
        ok = q("SELECT 1 AS ok")
        return {"ok": bool(ok and ok[0].get("ok") == 1)}
    except Exception as e:
        # útil en local si la DB no está lista
        return {"ok": False, "db_error": str(e)}

# db.py
from dotenv import load_dotenv
load_dotenv(override=True)

import os, time, pyodbc

SQL_SERVER   = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
USE_MSI      = os.getenv("USE_MSI", "false").lower() == "true"  # DEFAULT FALSE EN LOCAL
SQL_USER     = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

_CONN_BASE = (
    "Driver={{ODBC Driver 18 for SQL Server}};"
    "Server=tcp:{server},1433;Database={db};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

def _connect_msi():
    # Importa azure-identity SOLO si realmente usas MSI
    from azure.identity import DefaultAzureCredential
    token = DefaultAzureCredential().get_token("https://database.windows.net/.default").token
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    cs = _CONN_BASE.format(server=SQL_SERVER, db=SQL_DATABASE)
    return pyodbc.connect(cs, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token.encode("utf-16-le")})

def _connect_sqlauth():
    if not (SQL_USER and SQL_PASSWORD):
        raise RuntimeError("Faltan SQL_USER/SQL_PASSWORD con USE_MSI=false")
    cs = (_CONN_BASE.format(server=SQL_SERVER, db=SQL_DATABASE)
          + f"UID={SQL_USER};PWD={SQL_PASSWORD};")
    return pyodbc.connect(cs)

_conn = None
def _get_conn(retries=3):
    global _conn
    for i in range(retries):
        try:
            if _conn:
                with _conn.cursor() as c: c.execute("SELECT 1"); c.fetchone()
                return _conn
        except Exception:
            try: _conn.close()
            except Exception: pass
            _conn = None
        try:
            _conn = _connect_msi() if USE_MSI else _connect_sqlauth()
            return _conn
        except Exception as e:
            if i == retries-1: raise
            time.sleep(1.2*(i+1))

def q(sql, params=()):
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]

def x(sql, params=()):
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()

@app.post("/api/register")
def register(p: RegisterIn):
    try:
        if q("SELECT 1 FROM Usuarios WHERE Correo = ?", (p.correo,)):
            raise HTTPException(409, "Correo ya registrado")
        x("INSERT INTO dbo.Usuarios (Nombre, Correo, PasswordHash) VALUES (?, ?, ?)",
          (p.nombre, p.correo, bcrypt.hash(p.password)))
        return {"message": "Usuario creado"}
    except Exception as e:
        raise HTTPException(500, detail=f"DB error: {e}")
    

@app.post("/api/login")
def login(p: LoginIn):
    rows = q("SELECT ID_Usuario, Nombre, Correo, PasswordHash FROM dbo.Usuarios WHERE Correo = ?",
             (p.correo,))
    if not rows or not bcrypt.verify(p.password, rows[0]["PasswordHash"]):
        raise HTTPException(401, "Credenciales inválidas")
    u = rows[0]
    return {"message": "Login OK", "user": {"id": u["ID_Usuario"], "nombre": u["Nombre"], "correo": u["Correo"]}}
