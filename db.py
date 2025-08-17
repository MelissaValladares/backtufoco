import os, time, pyodbc
from azure.identity import DefaultAzureCredential

SQL_SERVER   = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
USE_MSI      = (os.getenv("USE_MSI", "true").lower() == "true")
SQL_USER     = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

_CONN_BASE = (
    "Driver={{ODBC Driver 18 for SQL Server}};"
    "Server=tcp:{server},1433;Database={db};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

_conn = None

def _aad_token_bytes():
    token = DefaultAzureCredential().get_token("https://database.windows.net/.default").token
    return token.encode("utf-16-le")

def _connect_msi():
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    return pyodbc.connect(
        _CONN_BASE.format(server=SQL_SERVER, db=SQL_DATABASE),
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: _aad_token_bytes()}
    )

def _connect_sqlauth():
    cs = _CONN_BASE.format(server=SQL_SERVER, db=SQL_DATABASE) + f"UID={SQL_USER};PWD={SQL_PASSWORD};"
    return pyodbc.connect(cs)

def _get_conn(retries=3):
    global _conn
    for i in range(retries):
        try:
            if _conn:
                with _conn.cursor() as c:
                    c.execute("SELECT 1")
                    c.fetchone()
                return _conn
        except Exception:
            try: _conn.close()
            except Exception: pass
            _conn = None
        try:
            _conn = _connect_msi() if USE_MSI else _connect_sqlauth()
            return _conn
        except Exception:
            if i == retries - 1: raise
            time.sleep(1.5 * (i + 1))

def q(sql_text: str, params: tuple = ()):
    """ SELECT → lista de dicts """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(sql_text, params)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]

def x(sql_text: str, params: tuple = ()):
    """ INSERT/UPDATE/DELETE """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(sql_text, params)
        conn.commit()
