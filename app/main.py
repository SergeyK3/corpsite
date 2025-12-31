from fastapi import FastAPI
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/corpsite"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Corpsite MVP")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
