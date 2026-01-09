from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "school-bank-secret"

DB = "bank.db"

# ---------------- DB ----------------
def db():
    return sqlite3.connect(DB)

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account_number TEXT,
        balance REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        amount REAL,
        type TEXT,
        date TEXT
    )
    """)

    # create admin
    c.execute("SELECT * FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users VALUES(NULL,?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    conn.commit()
    conn.close()

init_db()

# ---------------- AUTH ----------------
@app.route("/", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (request.form["username"],))
        user = c.fetchone()
        conn.close()

        if not user or not check_password_hash(user[2], request.form["password"]):
            error = "Invalid credentials"
        else:
            session["uid"] = user[0]
            session["role"] = user[3]
            return redirect("/admin" if user[3] == "admin" else "/dashboard")

    return render_template("login.html", error=error)

@app.route("/signup", methods=["GET","POST"])
def signup():
    error = None
    if request.method == "POST":
        try:
            conn = db()
            c = conn.cursor()

            pw = generate_password_hash(request.form["password"])
            c.execute(
                "INSERT INTO users VALUES(NULL,?,?,?)",
                (request.form["username"], pw, "student")
            )
            uid = c.lastrowid

            acc = "SB" + str(random.randint(100000, 999999))
            c.execute(
                "INSERT INTO accounts VALUES(NULL,?,?,?)",
                (uid, acc, 0.0)
            )

            conn.commit()
            conn.close()
            return redirect("/")
        except:
            error = "Username already exists"

    return render_template("signup.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- STUDENT ----------------
@app.route("/dashboard")
def dashboard():
    if session.get("role") != "student":
        return redirect("/")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT account_number, balance FROM accounts WHERE user_id=?", (session["uid"],))
    acc = c.fetchone()
    conn.close()

    return render_template("dashboard.html", acc=acc)

@app.route("/transfer", methods=["GET","POST"])
def transfer():
    if session.get("role") != "student":
        return redirect("/")

    msg = None
    conn = db()
    c = conn.cursor()

    c.execute("SELECT account_number, balance FROM accounts WHERE user_id=?", (session["uid"],))
    sender_acc, sender_bal = c.fetchone()

    if request.method == "POST":
        to = request.form["to"]
        amt = float(request.form["amount"])

        if amt <= 0:
            msg = "Invalid amount"
        elif sender_bal < amt:
            msg = "Insufficient balance"
        else:
            c.execute("SELECT * FROM accounts WHERE account_number=?", (to,))
            if not c.fetchone():
                msg = "Account not found"
            else:
                c.execute(
                    "UPDATE accounts SET balance=balance-? WHERE account_number=?",
                    (amt, sender_acc)
                )
                c.execute(
                    "UPDATE accounts SET balance=balance+? WHERE account_number=?",
                    (amt, to)
                )
                c.execute(
                    "INSERT INTO transactions VALUES(NULL,?,?,?,?,?)",
                    (sender_acc, to, amt, "TRANSFER", datetime.now().isoformat())
                )
                conn.commit()
                msg = "Transfer successful"

    conn.close()
    return render_template("transfer.html", msg=msg)

@app.route("/transactions")
def transactions():
    if session.get("role") != "student":
        return redirect("/")

    conn = db()
    c = conn.cursor()

    c.execute("SELECT account_number FROM accounts WHERE user_id=?", (session["uid"],))
    acc = c.fetchone()[0]

    c.execute("""
        SELECT sender, receiver, amount, type, date
        FROM transactions
        WHERE sender=? OR receiver=?
        ORDER BY date DESC
    """, (acc, acc))

    rows = c.fetchall()
    conn.close()

    return render_template("transactions.html", transactions=rows)

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT u.username, a.account_number, a.balance
        FROM users u
        JOIN accounts a ON u.id = a.user_id
    """)
    users = c.fetchall()
    conn.close()

    return render_template("admin.html", users=users)

@app.route("/topup/<acc>", methods=["GET","POST"])
def topup(acc):
    if session.get("role") != "admin":
        return redirect("/")

    msg = None
    conn = db()
    c = conn.cursor()

    c.execute("SELECT account_number, balance FROM accounts WHERE account_number=?", (acc,))
    account = c.fetchone()

    if request.method == "POST":
        amt = float(request.form["amount"])
        if amt > 0:
            c.execute(
                "UPDATE accounts SET balance=balance+? WHERE account_number=?",
                (amt, acc)
            )
            c.execute(
                "INSERT INTO transactions VALUES(NULL,?,?,?,?,?)",
                ("ADMIN", acc, amt, "TOPUP", datetime.now().isoformat())
            )
            conn.commit()
            msg = "Top-up successful"

    conn.close()
    return render_template("topup.html", acc=account, msg=msg)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
