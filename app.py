"""
A mysterious little sanctuary where people record their dreams,
choose to keep them secret or set them free into the public feed,
and gather around public dreams to talk about what they might mean.
"""

import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "enchanted_dreams.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "a-very-mysterious-and-not-so-secret-key")
app.config["DATABASE"] = DATABASE

MOODS = ["Lucid", "Nightmare", "Peaceful", "Surreal", "Prophetic", "Recurring", "Fading"]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            sigil TEXT NOT NULL DEFAULT '\U0001F319',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dreams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            mood TEXT NOT NULL DEFAULT 'Surreal',
            is_public INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dream_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (dream_id) REFERENCES dreams (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("You must enter the circle first \u2014 please sign in.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    return {"current_user": user, "app_name": "Enchanted Dreams"}


def now_iso():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def time_ago(iso_str):
    try:
        then = datetime.fromisoformat(iso_str)
    except ValueError:
        return iso_str
    delta = datetime.now(timezone.utc).replace(tzinfo=None) - then
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = months // 12
    return f"{years}y ago"


app.jinja_env.filters["time_ago"] = time_ago


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        if not username or len(username) < 3:
            error = "Choose a name of at least 3 characters."
        elif not password or len(password) < 4:
            error = "Your passphrase should hold at least 4 characters."
        elif password != confirm:
            error = "Your passphrases do not match."

        db = get_db()
        if error is None:
            existing = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing is not None:
                error = f"The name '{username}' is already claimed by another dreamer."

        if error:
            flash(error, "error")
            return render_template("register.html")

        sigil = ["\U0001F319", "\u2728", "\U0001F52E", "\U0001F98B", "\U0001F311", "\u2604\uFE0F", "\U0001F30C"][
            len(username) % 7
        ]
        db.execute(
            "INSERT INTO users (username, password_hash, sigil, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), sigil, now_iso()),
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        session.clear()
        session["user_id"] = user["id"]
        flash(f"Welcome to Enchanted Dreams, {username}. Your journal awaits.", "success")
        return redirect(url_for("feed"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("That name and passphrase do not match our records.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        flash(f"The veil parts for you, {username}.", "success")
        next_url = request.args.get("next") or url_for("feed")
        return redirect(next_url)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have slipped back into the waking world. Until next time.", "success")
    return redirect(url_for("feed"))


# ---------------------------------------------------------------------------
# Dream routes
# ---------------------------------------------------------------------------

@app.route("/")
def feed():
    db = get_db()
    mood_filter = request.args.get("mood", "").strip()

    query = """
        SELECT dreams.*, users.username, users.sigil,
               (SELECT COUNT(*) FROM messages WHERE messages.dream_id = dreams.id) AS message_count
        FROM dreams
        JOIN users ON users.id = dreams.user_id
        WHERE is_public = 1
    """
    params = []
    if mood_filter and mood_filter in MOODS:
        query += " AND mood = ?"
        params.append(mood_filter)
    query += " ORDER BY dreams.created_at DESC"

    dreams = db.execute(query, params).fetchall()
    return render_template("feed.html", dreams=dreams, moods=MOODS, active_mood=mood_filter)


@app.route("/my-dreams")
@login_required
def my_dreams():
    db = get_db()
    dreams = db.execute(
        """
        SELECT dreams.*,
               (SELECT COUNT(*) FROM messages WHERE messages.dream_id = dreams.id) AS message_count
        FROM dreams
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return render_template("my_dreams.html", dreams=dreams)


@app.route("/dreams/new", methods=["GET", "POST"])
@login_required
def new_dream():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        mood = request.form.get("mood", "Surreal")
        visibility = request.form.get("visibility", "private")

        error = None
        if not title:
            error = "Your dream needs a title, even a fleeting one."
        elif not content:
            error = "Tell us what you saw, or what you remember of it."
        elif mood not in MOODS:
            mood = "Surreal"

        if error:
            flash(error, "error")
            return render_template("new_dream.html", moods=MOODS, form=request.form)

        db = get_db()
        db.execute(
            """
            INSERT INTO dreams (user_id, title, content, mood, is_public, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                content,
                mood,
                1 if visibility == "public" else 0,
                now_iso(),
            ),
        )
        db.commit()
        flash("Your dream has been sealed into the archive.", "success")
        return redirect(url_for("my_dreams"))

    return render_template("new_dream.html", moods=MOODS, form={})


@app.route("/dreams/<int:dream_id>")
def dream_detail(dream_id):
    db = get_db()
    dream = db.execute(
        """
        SELECT dreams.*, users.username, users.sigil
        FROM dreams JOIN users ON users.id = dreams.user_id
        WHERE dreams.id = ?
        """,
        (dream_id,),
    ).fetchone()

    if dream is None:
        flash("That dream has dissolved back into the mist.", "error")
        return redirect(url_for("feed"))

    is_owner = "user_id" in session and session["user_id"] == dream["user_id"]
    if not dream["is_public"] and not is_owner:
        flash("This dream is sealed \u2014 only its dreamer may enter.", "error")
        return redirect(url_for("feed"))

    messages = db.execute(
        """
        SELECT messages.*, users.username, users.sigil
        FROM messages JOIN users ON users.id = messages.user_id
        WHERE dream_id = ?
        ORDER BY messages.created_at ASC
        """,
        (dream_id,),
    ).fetchall()

    return render_template("dream_detail.html", dream=dream, messages=messages, is_owner=is_owner)


@app.route("/dreams/<int:dream_id>/delete", methods=["POST"])
@login_required
def delete_dream(dream_id):
    db = get_db()
    dream = db.execute("SELECT * FROM dreams WHERE id = ?", (dream_id,)).fetchone()
    if dream is None or dream["user_id"] != session["user_id"]:
        flash("You may only unmake your own dreams.", "error")
        return redirect(url_for("my_dreams"))
    db.execute("DELETE FROM dreams WHERE id = ?", (dream_id,))
    db.commit()
    flash("The dream has been released back into the dark.", "success")
    return redirect(url_for("my_dreams"))


# ---------------------------------------------------------------------------
# Chat API (polled by the dream detail page)
# ---------------------------------------------------------------------------

def _can_access_dream(db, dream_id, user_id):
    dream = db.execute("SELECT * FROM dreams WHERE id = ?", (dream_id,)).fetchone()
    if dream is None:
        return None
    if dream["is_public"] or (user_id is not None and dream["user_id"] == user_id):
        return dream
    return None


@app.route("/api/dreams/<int:dream_id>/messages")
def api_get_messages(dream_id):
    db = get_db()
    user_id = session.get("user_id")
    dream = _can_access_dream(db, dream_id, user_id)
    if dream is None:
        return jsonify({"error": "not found or sealed"}), 404

    after_id = request.args.get("after", 0, type=int)
    rows = db.execute(
        """
        SELECT messages.id, messages.content, messages.created_at,
               users.username, users.sigil
        FROM messages JOIN users ON users.id = messages.user_id
        WHERE dream_id = ? AND messages.id > ?
        ORDER BY messages.created_at ASC
        """,
        (dream_id, after_id),
    ).fetchall()

    return jsonify(
        {
            "messages": [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "username": r["username"],
                    "sigil": r["sigil"],
                    "created_at": r["created_at"],
                    "time_ago": time_ago(r["created_at"]),
                }
                for r in rows
            ]
        }
    )


@app.route("/api/dreams/<int:dream_id>/messages", methods=["POST"])
@login_required
def api_post_message(dream_id):
    db = get_db()
    dream = _can_access_dream(db, dream_id, session["user_id"])
    if dream is None:
        return jsonify({"error": "not found or sealed"}), 404

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "empty message"}), 400
    if len(content) > 1000:
        content = content[:1000]

    cursor = db.execute(
        "INSERT INTO messages (dream_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
        (dream_id, session["user_id"], content, now_iso()),
    )
    db.commit()
    msg_id = cursor.lastrowid
    row = db.execute(
        """
        SELECT messages.id, messages.content, messages.created_at, users.username, users.sigil
        FROM messages JOIN users ON users.id = messages.user_id
        WHERE messages.id = ?
        """,
        (msg_id,),
    ).fetchone()

    return jsonify(
        {
            "id": row["id"],
            "content": row["content"],
            "username": row["username"],
            "sigil": row["sigil"],
            "created_at": row["created_at"],
            "time_ago": "just now",
        }
    )


if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    else:
        # make sure tables exist even if the db file was created empty
        init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
