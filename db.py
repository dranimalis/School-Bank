import sqlite3

def get_db():
    return sqlite3.connect("bank.db", check_same_thread=False)
