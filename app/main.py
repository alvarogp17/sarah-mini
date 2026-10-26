import os
import time
import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

app = FastAPI(title="Sarah Mini API")


def get_connection():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=3,
        row_factory=dict_row,
    )


def initialize_database():
    # Reintentos limitados: útiles durante el arranque local.
    # No sustituyen una estrategia completa de recuperación.
    for attempt in range(10):
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checkins (
                        id SERIAL PRIMARY KEY,
                        mood TEXT NOT NULL,
                        activity TEXT NOT NULL,
                        note TEXT NOT NULL
                    )
                    """
                )
            return
        except psycopg.OperationalError:
            if attempt == 9:
                raise
            time.sleep(2)


@app.on_event("startup")
def startup():
    initialize_database()


class CheckInCreate(BaseModel):
    mood: str = Field(min_length=1, max_length=80)
    activity: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=1, max_length=500)


@app.get("/")
def root():
    return {"message": "Sarah Mini: registro de bienestar de demostración"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/checkins")
def list_checkins(
    mood: str | None = Query(default=None, description="Filtrar por estado de ánimo"),
    activity: str | None = Query(default=None, description="Filtrar por actividad"),
):
    try:
        with get_connection() as conn:
            query = "SELECT id, mood, activity, note FROM checkins"
            conditions = []
            params = []

            if mood is not None:
                conditions.append("mood = %s")
                params.append(mood)
            if activity is not None:
                conditions.append("activity = %s")
                params.append(activity)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY id"

            rows = conn.execute(query, params).fetchall()
            return rows
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible",
        )


@app.post("/checkins", status_code=201)
def create_checkin(checkin: CheckInCreate):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """INSERT INTO checkins (mood, activity, note)
                   VALUES (%s, %s, %s)
                   RETURNING id, mood, activity, note""",
                (checkin.mood, checkin.activity, checkin.note),
            ).fetchone()
            return row
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible",
        )
