from flask import Flask, render_template, request, redirect, url_for, session
import joblib
import numpy as np
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"

model = joblib.load("fever_model.pkl")
DB_NAME = "users.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )""")
    conn.commit()
    # Create a demo account if it does not exist.
    existing = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@example.com",)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            ("Demo User", "demo@example.com", generate_password_hash("Fever@1234"))
        )
        conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = sqlite3.connect(DB_NAME)
        user = conn.execute("SELECT id, name, password FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect(url_for("home"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or not password:
            error = "Please fill in all fields."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must contain at least 6 characters."
        else:
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password))
                )
                conn.commit()
                conn.close()
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                error = "An account with this email already exists."
                try: conn.close()
                except: pass
    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("index.html", user_name=session.get("user_name"))


@app.route("/predict", methods=["POST"])
@login_required
def predict():
    cough = int(request.form["cough"])
    headache = int(request.form["headache"])
    bodypain = int(request.form["bodypain"])
    temperature = float(request.form["temperature"])

    input_data = np.array([[cough, headache, bodypain, temperature]])
    prediction = model.predict(input_data)[0]

    result = "Fever Detected" if prediction == 1 else "No Fever"
    return render_template("index.html", prediction=result, user_name=session.get("user_name"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
