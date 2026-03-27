"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import sqlite3
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")


def get_database_path() -> Path:
    configured_path = os.getenv("SCHOOL_DB_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return (current_dir / "school_activities.db").resolve()


DATABASE_PATH = get_database_path()
LATEST_SCHEMA_VERSION = 1

SEED_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_migrations(conn: sqlite3.Connection) -> None:
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]

    if current_version < 1:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                UNIQUE(activity_id, email),
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                due_date TEXT,
                is_completed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE SET NULL
            );
            """
        )
        conn.execute("PRAGMA user_version = 1")
        conn.commit()

    latest_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if latest_version != LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            "Database schema version mismatch: "
            f"expected {LATEST_SCHEMA_VERSION}, got {latest_version}"
        )


def seed_initial_data(conn: sqlite3.Connection) -> None:
    activity_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if activity_count > 0:
        return

    for activity_name, details in SEED_ACTIVITIES.items():
        cursor = conn.execute(
            """
            INSERT INTO activities (name, description, schedule, max_participants)
            VALUES (?, ?, ?, ?)
            """,
            (
                activity_name,
                details["description"],
                details["schedule"],
                details["max_participants"],
            ),
        )

        activity_id = cursor.lastrowid
        for email in details["participants"]:
            conn.execute(
                "INSERT INTO participants (activity_id, email) VALUES (?, ?)",
                (activity_id, email),
            )

    conn.commit()


def initialize_database() -> None:
    conn = get_db_connection()
    try:
        apply_migrations(conn)
        seed_initial_data(conn)
    finally:
        conn.close()


def get_activities_data() -> dict[str, dict]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                a.id,
                a.name,
                a.description,
                a.schedule,
                a.max_participants,
                p.email
            FROM activities a
            LEFT JOIN participants p ON p.activity_id = a.id
            ORDER BY a.name, p.email
            """
        ).fetchall()

        activities: dict[str, dict] = {}
        for row in rows:
            name = row["name"]
            if name not in activities:
                activities[name] = {
                    "description": row["description"],
                    "schedule": row["schedule"],
                    "max_participants": row["max_participants"],
                    "participants": [],
                }

            if row["email"] is not None:
                activities[name]["participants"].append(row["email"])

        return activities
    finally:
        conn.close()


def get_activity_row(conn: sqlite3.Connection, activity_name: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, name, max_participants
        FROM activities
        WHERE name = ?
        """,
        (activity_name,),
    ).fetchone()


initialize_database()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return get_activities_data()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    conn = get_db_connection()
    try:
        activity = get_activity_row(conn, activity_name)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant_count = conn.execute(
            "SELECT COUNT(*) FROM participants WHERE activity_id = ?",
            (activity["id"],),
        ).fetchone()[0]
        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        is_already_registered = conn.execute(
            "SELECT 1 FROM participants WHERE activity_id = ? AND email = ?",
            (activity["id"], email),
        ).fetchone()
        if is_already_registered:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        conn.execute(
            "INSERT INTO participants (activity_id, email) VALUES (?, ?)",
            (activity["id"], email),
        )
        conn.commit()
    finally:
        conn.close()

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    conn = get_db_connection()
    try:
        activity = get_activity_row(conn, activity_name)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        delete_result = conn.execute(
            "DELETE FROM participants WHERE activity_id = ? AND email = ?",
            (activity["id"], email),
        )
        if delete_result.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        conn.commit()
    finally:
        conn.close()

    return {"message": f"Unregistered {email} from {activity_name}"}
