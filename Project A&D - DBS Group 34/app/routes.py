from flask import Blueprint, render_template, request, session, redirect, url_for
from . import supabase

main = Blueprint("main", __name__)
DUMMY_USER = {"id": "12345", "name": "John Doe", "email": "example@ugent.be", "password": "password"}


@main.route("/investments")
def investments():
    if supabase is None:
        return render_template("investments.html", investments=[])
    data = supabase.table("investments").select("*").execute()
    return render_template("investments.html", investments=data.data)
# Dashboard pagina
@main.route("/dashboard")
def dashboard():
    # TEMP: fake data (later vervangen door Supabase)
    announcements = [
        {"title": "Welkom bij de VIC!", "body": "Dit is onze nieuwe dashboardpagina.", "date": "20/11/2025", "author": "Admin"},
        {"title": "Vergadering", "body": "Teammeeting om 19u.", "date": "18/11/2025", "author": "Jens"},
    ]

    upcoming_events = [
        {"title": "Pitch Night", "date": "25/11/2025", "time": "19:00", "location": "UGent"},
        {"title": "Beursgame Finale", "date": "30/11/2025", "time": "20:30", "location": "Campus Kortrijk"},
    ]

    return render_template(
        "dashboard.html",
        announcements=announcements,
        upcoming=upcoming_events
    )

# Home redirect → dashboard
@main.route("/")
def home():
    return render_template("login.html")  # of redirect naar dashboard
    # Login POST
@main.route("/login", methods=["POST"])
def login_post():
    user_id = request.form.get("id")
    password = request.form.get("password")

    if user_id == DUMMY_USER["id"] and password == DUMMY_USER["password"]:
        session["user"] = DUMMY_USER
        return redirect(url_for("main.dashboard"))
    else:
        return render_template("login.html", error="Ongeldige ID of wachtwoord")
