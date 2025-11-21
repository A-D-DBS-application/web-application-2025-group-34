from flask import Blueprint, render_template, request, session, redirect, url_for, g, flash
from functools import wraps
from . import supabase

main = Blueprint("main", __name__)
DUMMY_USER = {"id": "12345", "name": "John Doe", "email": "example@ugent.be", "password": "password"}

# --- NIEUW: Middleware om Gebruiker in Context te Laden ---
@main.before_app_request
def load_logged_in_user():
    """Plaatst de ingelogde user in het 'g'-object voor toegang in templates en routes."""
    g.user = session.get('user')

# --- NIEUW: Decorator voor Beveiliging ---
def login_required(view):
    """Decorator: vereist dat een gebruiker is ingelogd om de route te bezoeken."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Je moet ingelogd zijn om deze pagina te bekijken.", "info") 
            return redirect(url_for('main.home'))
        return view(*args, **kwargs)
    return wrapped_view

# --- Bestaande routes met beveiliging ---

@main.route("/investments")
@login_required # Beveiligd!
def investments():
    if supabase is None:
        # Foutafhandeling als Supabase niet is geconfigureerd
        return render_template("investments.html", investments=[], error="Supabase is niet geconfigureerd.") 
    try:
        # De .execute() roep is correct
        data = supabase.table("investments").select("*").execute()
        return render_template("investments.html", investments=data.data) 
    except Exception as e:
        print(f"Error fetching investments: {e}")
        return render_template("investments.html", investments=[], error="Fout bij het ophalen van investeringsgegevens.")

# Dashboard pagina
@main.route("/dashboard")
@login_required # Beveiligd!
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

# --- NIEUW: Portfolio Route ---
@main.route("/portfolio")
@login_required # Beveiligd!
def portfolio():
    # Helper functie voor EUR-notatie
    def format_currency(value):
        return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")
        
    # TEMP: Mock data voor de portfolio-pagina
    portfolio_value = 150000.55
    pnl = 12500.25
    position_value = 137500.30

    portfolio_data = [
        {"asset": "Tesla Inc", "sector": "Technology", "ticker": "TSLA", "day_change": "+1.5%", "share_price": 200.00, "quantity": 100, "market_value": 20000.00, "weight": 14.5, "pnl_percent": "+12.5%", "pnl_value": 2500.00},
        {"asset": "ASML", "sector": "Tech", "ticker": "ASML", "day_change": "-0.5%", "share_price": 850.20, "quantity": 50, "market_value": 42510.00, "weight": 30.1, "pnl_percent": "+5.0%", "pnl_value": 2000.00},
        {"asset": "Coca Cola", "sector": "Consumer", "ticker": "KO", "day_change": "+0.1%", "share_price": 60.15, "quantity": 500, "market_value": 30075.00, "weight": 21.3, "pnl_percent": "-2.0%", "pnl_value": -601.50},
    ]
    
    # Formatteer de data
    p_data_formatted = []
    for p in portfolio_data:
        p_formatted = p.copy()
        p_formatted['share_price'] = format_currency(p['share_price'])
        p_formatted['market_value'] = format_currency(p['market_value'])
        p_formatted['pnl_value'] = format_currency(p['pnl_value'])
        p_data_formatted.append(p_formatted)
        
    return render_template(
        "portfolio.html",
        portfolio_value=format_currency(portfolio_value),
        pnl=format_currency(pnl),
        position_value=format_currency(position_value),
        portfolio=p_data_formatted,
    )


# Home redirect → login of dashboard
@main.route("/")
def home():
    if g.user is not None:
        return redirect(url_for('main.dashboard'))
    return render_template("login.html")

# Login POST
@main.route("/login", methods=["POST"])
def login_post():
    user_id = request.form.get("id")
    password = request.form.get("password")

    if user_id == DUMMY_USER["id"] and password == DUMMY_USER["password"]:
        session["user"] = DUMMY_USER
        flash(f"Welkom terug, {DUMMY_USER['name']}!", "success") 
        return redirect(url_for("main.dashboard"))
    else:
        # Gebruik flash i.p.v. een 'error' variabele
        flash("Ongeldige ID of wachtwoord", "error")
        return redirect(url_for('main.home'))

# --- NIEUW: Logout route ---
@main.route('/logout')
def logout():
    session.pop('user', None)
    flash("Je bent succesvol uitgelogd.", "info")
    return redirect(url_for('main.home'))

