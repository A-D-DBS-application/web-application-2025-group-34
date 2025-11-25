from flask import Blueprint, render_template, request, session, redirect, url_for, g, flash
from functools import wraps
from sqlalchemy import or_
from datetime import datetime
from . import supabase, db
from .models import Member

main = Blueprint("main", __name__)

# --- MOCK DATA UIT FIGMA (App.tsx) ---
MOCK_CASH_AMOUNT = 16411.22

MOCK_POSITIONS = [
  {"asset": "Adyen NV", "sector": "Tech", "ticker": "ADYEN", "day_change": "+0.66%", "share_price": 1504.0, "quantity": 1, "market_value": 1504.0, "unrealizedGain": 187.4, "unrealizedPL": 14.23},
  {"asset": "ALPHABET INC.", "sector": "Tech", "ticker": "GOOGL", "day_change": "+0.55%", "share_price": 217.85, "quantity": 7, "market_value": 1524.95, "unrealizedGain": -92.8, "unrealizedPL": -6.02},
  {"asset": "BERKSHIRE HATHAWAY", "sector": "RE, F. & Hold.", "ticker": "BRK. B", "day_change": "-0.34%", "share_price": 421.93, "quantity": 8, "market_value": 3375.44, "unrealizedGain": 393.38, "unrealizedPL": 11.15},
  {"asset": "MICROSOFT CORP.", "sector": "Tech", "ticker": "MSFT", "day_change": "+0.02%", "share_price": 448.1, "quantity": 3, "market_value": 1344.3, "unrealizedGain": 833.28, "unrealizedPL": 114.4},
]

MOCK_ANNOUNCEMENTS = [
    {"title": "Stemresultaten Banca Sistema", "body": "De stemming over Banca Sistema verliep als volgt: 75,00% akkoord. De aankoop is goedgekeurd.", "date": "04/11/2025", "author": "Milan Van Nuffel"},
    {"title": "Reminder: AV 3 vanavond", "body": "Een korte reminder dat deze avond AV 3 op de planning staat.", "date": "05/11/2025", "author": "Casper Bekaert"},
]

MOCK_UPCOMING_EVENTS = [
    {"title": "Algemene vergadering 6", "date": "12/12/2025", "time": "19:30", "location": "Gent, Belgium"},
    {"title": "Algemene vergadering 5", "date": "28/11/2025", "time": "19:30", "location": "Gent, Belgium"},
]

MOCK_TRANSACTIONS = [
    {"number": 1, "date": "1-9-2022", "type": "BUY", "asset": "Volkswagen AG", "ticker": "VOW3", "units": 4, "price": 129.72, "total": 518.88, "currency": "EUR", "profitLoss": None},
    {"number": 2, "date": "1-9-2022", "type": "SELL", "asset": "ADVANCED MICRO DEVICES", "ticker": "AMD", "units": 10, "price": 66.64, "total": -666.4, "currency": "USD", "profitLoss": 80.5},
]

MOCK_VOTES = [
    {"title": "Algemene Vergadering 2", "stockName": "Stock XYZ", "deadline": "November 20th", "totalVotes": 0, "forVotes": 0, "againstVotes": 0, "abstainVotes": 0, "isPending": True},
    {"title": "Algemene Vergadering 1", "stockName": "Stock XYZ", "deadline": "October 15th", "totalVotes": 17, "forVotes": 12, "againstVotes": 5, "abstainVotes": 0, "isPending": False},
]


# --- HELPER FUNCTIES ---

def format_currency(value):
    """Formats a float to a European currency string (e.g., 1.234,56)"""
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")

def _normalize_transactions(records):
    normalized = []
    for record in records:
        if isinstance(record, dict):
            normalized.append({
                "number": record.get("number") or record.get("transaction_id"),
                "date": record.get("date") or record.get("transaction_date"),
                "type": record.get("type") or record.get("transaction_type"),
                "asset": record.get("asset") or record.get("name"),
                "ticker": record.get("ticker") or record.get("symbol"),
                "units": record.get("units") or record.get("quantity") or record.get("transaction_quantity"),
                "price": record.get("price") or record.get("unit_price") or record.get("transaction_price"),
                "total": record.get("total") or record.get("transaction_amount"),
                "profitLoss": record.get("profitLoss") or record.get("profit_loss"),
            })
        else:
            normalized.append(record)
    return normalized

def _get_next_event_number():
    fallback = len(MOCK_UPCOMING_EVENTS) + 1
    if supabase is None:
        return fallback
    try:
        response = supabase.table("events").select("event_number").order("event_number", desc=True).limit(1).execute()
        latest = response.data[0]["event_number"] if response.data else 0
        return (latest or 0) + 1
    except Exception as exc:
        print(f"WARNING: Supabase event number fetch failed: {exc}")
        return fallback

def _format_event_date(date_str, time_str):
    if not date_str:
        return datetime.now().isoformat()
    parsed_date = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    if parsed_date is None:
        return f"{date_str} {time_str}".strip()
    if time_str:
        try:
            parsed_time = datetime.strptime(time_str, "%H:%M")
            parsed_date = parsed_date.replace(hour=parsed_time.hour, minute=parsed_time.minute)
        except ValueError:
            pass
    return parsed_date.isoformat()

def _persist_event_supabase(event_number, title, event_date_iso):
    if supabase is None:
        return None
    try:
        supabase.table("events").insert({
            "event_number": event_number,
            "event_name": title,
            "event_date": event_date_iso,
        }).execute()
        return True
    except Exception as exc:
        print(f"WARNING: Supabase event insert failed: {exc}")
        return False

def _format_supabase_date(ts):
    if not ts:
        return datetime.now().strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return ts

def _persist_announcement_supabase(title, body, author):
    if supabase is None:
        return None
    try:
        supabase.table("announcements").insert({
            "title": title,
            "body": body,
            "author": author
        }).execute()
        return True
    except Exception as exc:
        print(f"WARNING: Supabase announcement insert failed: {exc}")
        return False

def _fetch_announcements():
    if supabase is None:
        return MOCK_ANNOUNCEMENTS
    try:
        response = supabase.table("announcements").select("*").order("created_at", desc=True).execute()
        data = response.data or []
        normalized = []
        for row in data:
            normalized.append({
                "title": row.get("title"),
                "body": row.get("body"),
                "author": row.get("author", "Onbekend"),
                "date": _format_supabase_date(row.get("created_at"))
            })
        if normalized:
            return normalized
    except Exception as exc:
        print(f"WARNING: Supabase announcement fetch failed: {exc}")
    return MOCK_ANNOUNCEMENTS

# --- BEVEILIGING & CONTEXT ---

@main.before_app_request
def load_logged_in_user():
    member_id = session.get('user_id')
    
    if member_id is None:
        g.user = None
    else:
        g.user = db.session.get(Member, member_id)

def login_required(view):
    """Decorator: vereist dat een gebruiker is ingelogd om de route te bezoeken."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Je moet ingelogd zijn om deze pagina te bekijken.", "info") 
            return redirect(url_for('main.home'))
        return view(*args, **kwargs)
    return wrapped_view

# --- ROUTES ---

# Dashboard pagina
@main.route("/dashboard")
@login_required 
def dashboard():
    return render_template(
        "dashboard.html",
        announcements=_fetch_announcements(),
        upcoming=MOCK_UPCOMING_EVENTS
    )

@main.route("/dashboard/announcements", methods=["POST"])
@login_required
def add_announcement():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    author = g.user.member_name if g.user else "Onbekend"
    date_str = datetime.now().strftime("%d/%m/%Y")

    if not title or not body:
        flash("Titel en bericht zijn verplicht.", "error")
        return redirect(url_for("main.dashboard"))

    persisted = _persist_announcement_supabase(title, body, author)
    if not persisted:
        flash("Bericht lokaal toegevoegd; Supabase opslag mislukt.", "warning")
        MOCK_ANNOUNCEMENTS.insert(0, {
            "title": title,
            "body": body,
            "date": date_str,
            "author": author
        })
    flash("Bericht toegevoegd.", "success")
    return redirect(url_for("main.dashboard"))

@main.route("/dashboard/events", methods=["POST"])
@login_required
def add_event():
    title = request.form.get("title", "").strip()
    date = request.form.get("date", "").strip()
    time = request.form.get("time", "").strip()
    location = request.form.get("location", "").strip() or "Onbekende locatie"

    if not title:
        flash("Titel is verplicht voor een event.", "error")
        return redirect(url_for("main.dashboard"))

    if not date:
        date = datetime.now().strftime("%d/%m/%Y")
    if not time:
        time = "00:00"

    event_number = _get_next_event_number()
    iso_date = _format_event_date(date, time)

    if _persist_event_supabase(event_number, title, iso_date) is False:
        flash("Event lokaal toegevoegd; Supabase opslag mislukt.", "warning")

    MOCK_UPCOMING_EVENTS.insert(0, {
        "title": title,
        "date": date,
        "time": time,
        "location": location
    })
    flash(f"Event '{title}' toegevoegd.", "success")
    return redirect(url_for("main.dashboard"))

# Portfolio pagina
@main.route("/portfolio")
@login_required 
def portfolio():
    # 1. Bereken de totale waarden
    total_market_value = sum(p['market_value'] for p in MOCK_POSITIONS)
    total_unrealized_gain = sum(p['unrealizedGain'] for p in MOCK_POSITIONS)
    portfolio_value = total_market_value + MOCK_CASH_AMOUNT
    
    # 2. Formatteer de portfolio data voor de template
    portfolio_data_formatted = []
    for p in MOCK_POSITIONS:
        weight = (p['market_value'] / portfolio_value) * 100 if portfolio_value > 0 else 0
        
        day_change_str = f"{'+' if p['day_change'].startswith('+') else ''}{p['day_change']}"
        pnl_percent_str = f"{'+' if p['unrealizedPL'] >= 0 else ''}{format_currency(p['unrealizedPL'])}%"
        
        portfolio_data_formatted.append({
            'asset': p['asset'],
            'sector': p['sector'],
            'ticker': p['ticker'],
            'day_change': day_change_str,
            'share_price': format_currency(p['share_price']),
            'quantity': p['quantity'],
            'market_value': format_currency(p['market_value']),
            'weight': format_currency(weight),
            'pnl_percent': pnl_percent_str,
            'pnl_value': format_currency(p['unrealizedGain']),
        })

    return render_template(
        "portfolio.html",
        portfolio_value=format_currency(portfolio_value),
        pnl=format_currency(total_unrealized_gain),
        position_value=format_currency(total_market_value),
        portfolio=portfolio_data_formatted
    )

# Transactions pagina (Nu de centrale bron voor transactiegegevens)
@main.route("/transactions")
@login_required
def transactions():
    transactions_data = MOCK_TRANSACTIONS  # Standaard fallback is mock data
    
    if supabase is not None:
        try:
            # FIX: Gebruik de correcte tabelnaam 'transactions'
            data = supabase.table("transactions").select("*").execute()
            transactions_data = data.data # Gebruik DB data indien succesvol
        except Exception as e:
            print(f"WARNING: Supabase transactie fetch failed: {e}. Falling back to mock data.")
            flash("Kon transactiedata niet ophalen van Supabase. Toon mock data.", "warning")

    transactions_data = _normalize_transactions(transactions_data)
    return render_template("transactions.html", transactions=transactions_data)
    
# Voting pagina
@main.route("/voting")
@login_required
def voting():
    return render_template("voting.html", votes=MOCK_VOTES)

# Investments pagina: VERWIJDERD OMDAT DEZE REDUNDANT EN KAPOT IS

# Home redirect → login of dashboard
@main.route("/")
def home():
    if g.user is not None:
        return redirect(url_for('main.dashboard'))
    return render_template("login.html")

# Login POST
@main.route("/login", methods=["POST"])
def login_post():
    login_id = request.form.get("id")
    password = request.form.get("password")

    member = db.session.execute(
        db.select(Member).where(
            or_(
                Member.member_id == login_id,
                Member.email == login_id
            )
        )
    ).scalar_one_or_none()

    if member and member.check_password(password):
        session["user_id"] = member.member_id 
        flash(f"Welkom terug, {member.member_name}!", "success")
        return redirect(url_for("main.dashboard"))
    else:
        flash("Ongeldige ID of wachtwoord", "error")
        return redirect(url_for('main.home'))

# Logout route
@main.route('/logout')
def logout():
    session.pop('user_id', None) 
    flash("Je bent succesvol uitgelogd.", "info")
    return redirect(url_for('main.home'))