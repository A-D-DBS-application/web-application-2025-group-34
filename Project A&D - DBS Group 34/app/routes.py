from flask import Blueprint, render_template, request, session, redirect, url_for, g, flash
from functools import wraps
from sqlalchemy import or_
from datetime import datetime
from . import supabase, db
from .models import (
    Member, Announcement, Event, Position, Transaction, VotingProposal, Portfolio,
    generate_board_member_id, generate_analist_id, generate_lid_id, 
    generate_kapitaalverschaffer_id, convert_to_oud_id, get_next_available_id
)

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
    # Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        latest_event = db.session.query(Event).order_by(Event.event_number.desc()).first()
        if latest_event and latest_event.event_number:
            return latest_event.event_number + 1
        return 1
    except Exception as exc:
        print(f"WARNING: SQLAlchemy event number fetch failed: {exc}")
    
    # Fallback naar Supabase REST API
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

def _persist_event_supabase(title, event_date_iso, location=None):
    # Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        from datetime import datetime
        # Parse de ISO date string naar datetime object
        try:
            if isinstance(event_date_iso, str):
                # Handle verschillende datetime formats
                if 'T' in event_date_iso:
                    event_date = datetime.fromisoformat(event_date_iso.replace('Z', '+00:00'))
                else:
                    event_date = datetime.fromisoformat(event_date_iso)
            else:
                event_date = event_date_iso
        except (ValueError, AttributeError):
            event_date = datetime.now()
        
        # event_number wordt automatisch gegenereerd door de database (autoincrement)
        event = Event(
            event_name=title,
            event_date=event_date,
            location=location
        )
        db.session.add(event)
        db.session.commit()
        return True
    except Exception as exc:
        print(f"WARNING: SQLAlchemy event insert failed: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
    
    # Fallback naar Supabase REST API
    if supabase is None:
        return False
    try:
        # Voor Supabase REST API moeten we event_number wel handmatig bepalen
        event_number = _get_next_event_number()
        supabase.table("events").insert({
            "event_number": event_number,
            "event_name": title,
            "event_date": event_date_iso,
            "location": location
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
    # Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        announcement = Announcement(
            title=title,
            body=body,
            author=author
        )
        db.session.add(announcement)
        db.session.commit()
        return True
    except Exception as exc:
        print(f"WARNING: SQLAlchemy announcement insert failed: {exc}")
        db.session.rollback()
    
    # Fallback naar Supabase REST API
    if supabase is None:
        return False
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
    # Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        announcements = db.session.query(Announcement).order_by(Announcement.created_at.desc()).all()
        if announcements:
            normalized = []
            for ann in announcements:
                normalized.append({
                    "title": ann.title,
                    "body": ann.body,
                    "author": ann.author or "Onbekend",
                    "date": _format_supabase_date(ann.created_at.isoformat() if ann.created_at else None)
                })
            return normalized
    except Exception as exc:
        print(f"WARNING: SQLAlchemy announcement fetch failed: {exc}")
    
    # Fallback naar Supabase REST API
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

def _fetch_events():
    # Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        events = db.session.query(Event).order_by(Event.event_date.asc()).all()
        if events:
            normalized = []
            for evt in events:
                event_date = evt.event_date
                if event_date:
                    date_str = event_date.strftime("%d/%m/%Y")
                    time_str = event_date.strftime("%H:%M")
                else:
                    date_str = datetime.now().strftime("%d/%m/%Y")
                    time_str = "00:00"
                
                normalized.append({
                    "title": evt.event_name,
                    "date": date_str,
                    "time": time_str,
                    "location": evt.location or "Onbekende locatie"
                })
            return normalized
    except Exception as exc:
        print(f"WARNING: SQLAlchemy event fetch failed: {exc}")
    
    # Fallback naar Supabase REST API
    if supabase is None:
        return MOCK_UPCOMING_EVENTS
    try:
        response = supabase.table("events").select("*").order("event_date", desc=False).execute()
        data = response.data or []
        normalized = []
        for row in data:
            event_date_str = row.get("event_date")
            if event_date_str:
                try:
                    event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                    date_str = event_date.strftime("%d/%m/%Y")
                    time_str = event_date.strftime("%H:%M")
                except (ValueError, AttributeError):
                    date_str = _format_supabase_date(event_date_str)
                    time_str = "00:00"
            else:
                date_str = datetime.now().strftime("%d/%m/%Y")
                time_str = "00:00"
            
            normalized.append({
                "title": row.get("event_name", ""),
                "date": date_str,
                "time": time_str,
                "location": row.get("location", "Onbekende locatie")
            })
        if normalized:
            return normalized
    except Exception as exc:
        print(f"WARNING: Supabase event fetch failed: {exc}")
    return MOCK_UPCOMING_EVENTS

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

def role_required(*allowed_roles):
    """Decorator: vereist dat een gebruiker een specifieke rol heeft."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                flash("Je moet ingelogd zijn om deze pagina te bekijken.", "info")
                return redirect(url_for('main.home'))
            
            user_role = g.user.get_role()
            if user_role not in allowed_roles:
                role_names = {
                    'board': 'bestuurslid',
                    'analist': 'analist',
                    'lid': 'lid',
                    'kapitaalverschaffers': 'kapitaalverschaffer',
                    'oud_bestuur_analisten': 'oud-bestuurslid/analist'
                }
                allowed_names = [role_names.get(r, r) for r in allowed_roles]
                flash(f"Alleen {', '.join(allowed_names)} kunnen deze actie uitvoeren.", "error")
                return redirect(url_for('main.dashboard'))
            
            return view(*args, **kwargs)
        return wrapped_view
    return decorator

def board_required(view):
    """Decorator: vereist dat gebruiker board member is."""
    return role_required('board')(view)

def analist_required(view):
    """Decorator: vereist dat gebruiker analist is."""
    return role_required('analist')(view)

def board_or_analist_required(view):
    """Decorator: vereist dat gebruiker board member of analist is."""
    return role_required('board', 'analist')(view)

# --- ROUTES ---

# Dashboard pagina
@main.route("/dashboard")
@login_required 
def dashboard():
    return render_template(
        "dashboard.html",
        announcements=_fetch_announcements(),
        upcoming=_fetch_events()
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

    iso_date = _format_event_date(date, time)

    persisted = _persist_event_supabase(title, iso_date, location)
    if not persisted:
        flash("Event lokaal toegevoegd; database opslag mislukt.", "warning")
        MOCK_UPCOMING_EVENTS.insert(0, {
            "title": title,
            "date": date,
            "time": time,
            "location": location
        })
    else:
        flash(f"Event '{title}' toegevoegd.", "success")
    return redirect(url_for("main.dashboard"))

# Portfolio pagina
@main.route("/portfolio")
@login_required 
def portfolio():
    try:
        # Haal centrale portfolio op
        central_portfolio = db.session.query(Portfolio).first()
        
        # Haal alle positions op (met of zonder portfolio)
        if central_portfolio:
            positions = db.session.query(Position).filter(
                Position.portfolio_id == central_portfolio.portfolio_id
            ).all()
        else:
            positions = []
        
        # Als er geen positions zijn gekoppeld, probeer alle positions
        if not positions:
            positions = db.session.query(Position).all()
        
        # Als er nog steeds geen positions zijn, gebruik mock data als fallback
        if not positions:
            total_market_value = sum(p['market_value'] for p in MOCK_POSITIONS)
            total_unrealized_gain = sum(p['unrealizedGain'] for p in MOCK_POSITIONS)
            portfolio_value = total_market_value  # Portfolio Value = totale market value van alle posities
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
        
        # Gebruik gecachte prijzen uit de database (geüpdatet door scheduler elke 5 minuten)
        # Geen live API calls meer nodig - dit maakt de pagina veel sneller!
        
        # Bereken totale waarden met live prijzen
        total_market_value = 0.0
        total_cost = 0.0
        
        portfolio_data_formatted = []
        for p in positions:
            ticker = p.pos_ticker or p.pos_name  # Gebruik pos_ticker als die bestaat, anders pos_name
            quantity = p.pos_quantity or 0
            # Cost basis = wat ze hebben betaald (pos_value uit database)
            # Als pos_value None is, gebruik 0.0 (maar dit zou niet moeten voorkomen)
            cost_basis = float(p.pos_value) if p.pos_value is not None else 0.0
            
            # Gebruik gecachte prijzen uit database (geüpdatet door scheduler)
            if p.current_price is not None and quantity > 0:
                share_price = p.current_price
                market_value = share_price * quantity
                # Format dagverandering
                day_change_pct = p.day_change_pct if p.day_change_pct is not None else 0.0
                day_change = f"{'+' if day_change_pct >= 0 else ''}{day_change_pct:.2f}%"
            elif cost_basis > 0 and quantity > 0:
                # Fallback: gebruik cost basis per aandeel als geen gecachte prijs beschikbaar is
                share_price = cost_basis / quantity
                market_value = cost_basis  # Fallback: gebruik cost basis als market value
                day_change = '+0.00%'
            else:
                share_price = 0.0
                market_value = 0.0
                day_change = '+0.00%'
            
            # Bereken altijd P&L op basis van cost basis
            pnl_value = market_value - cost_basis
            pnl_percent = (pnl_value / cost_basis * 100) if cost_basis > 0 else 0.0
            
            total_market_value += market_value
            total_cost += cost_basis
            
            # Format percentage correct (geen currency formatting voor percentages)
            pnl_percent_str = f"{'+' if pnl_percent >= 0 else ''}{pnl_percent:.2f}%"
            
            portfolio_data_formatted.append({
                'asset': p.pos_name or 'Onbekend',
                'sector': p.pos_sector or p.pos_type or 'N/A',
                'ticker': ticker or 'N/A',
                'day_change': day_change,
                'share_price': format_currency(share_price),
                'quantity': quantity,
                'market_value': market_value,
                'pnl_percent': pnl_percent_str,
                'pnl_value': format_currency(pnl_value),
            })
        
        total_unrealized_gain = total_market_value - total_cost
        portfolio_value = total_market_value  # Portfolio Value = totale market value van alle posities
        
        # Bereken weight voor elke positie
        for p_data in portfolio_data_formatted:
            weight = (p_data['market_value'] / portfolio_value) * 100 if portfolio_value > 0 else 0
            p_data['weight'] = format_currency(weight)
            p_data['market_value'] = format_currency(p_data['market_value'])
        
    except Exception:
        # Fallback naar mock data
        total_market_value = sum(p['market_value'] for p in MOCK_POSITIONS)
        total_unrealized_gain = sum(p['unrealizedGain'] for p in MOCK_POSITIONS)
        portfolio_value = total_market_value  # Portfolio Value = totale market value van alle posities
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

# Deelnemers pagina
@main.route("/deelnemers")
@login_required
def deelnemers():
    # Haal alle members op en filter op basis van rol
    try:
        all_members = db.session.query(Member).order_by(Member.member_id.asc()).all()
        
        # Filter members op basis van rol
        board_members = [m for m in all_members if m.get_role() == 'board']
        analisten = [m for m in all_members if m.get_role() == 'analist']
        leden = [m for m in all_members if m.get_role() == 'lid']
        kapitaalverschaffers = [m for m in all_members if m.get_role() == 'kapitaalverschaffers']
        oud_bestuur_analisten = [m for m in all_members if m.get_role() == 'oud_bestuur_analisten']
        
    except Exception as exc:
        print(f"WARNING: Database fetch failed: {exc}")
        all_members = []
        board_members = []
        analisten = []
        leden = []
        kapitaalverschaffers = []
        oud_bestuur_analisten = []
    
    return render_template(
        "deelnemers.html",
        members=leden,  # Leden worden als 'members' doorgegeven voor backward compatibility
        board_members=board_members,
        analisten=analisten,
        kapitaalverschaffers=kapitaalverschaffers,
        oud_bestuur_analisten=oud_bestuur_analisten,
        all_members=all_members  # Voor eventuele andere doeleinden
    )

# Portfolio: Positie toevoegen
@main.route("/portfolio/add", methods=["POST"])
@login_required
def add_position():
    pos_name = request.form.get("pos_name", "").strip()
    pos_type = request.form.get("pos_type", "").strip()
    pos_quantity = request.form.get("pos_quantity", "").strip()
    pos_value = request.form.get("pos_value", "").strip()
    pos_ticker = request.form.get("pos_ticker", "").strip()
    pos_sector = request.form.get("pos_sector", "").strip()
    
    # Valideer alle verplichte velden
    if not pos_name:
        flash("Positie naam is verplicht.", "error")
        return redirect(url_for("main.portfolio"))
    if not pos_ticker:
        flash("Ticker is verplicht voor prijs updates.", "error")
        return redirect(url_for("main.portfolio"))
    if not pos_quantity:
        flash("Hoeveelheid is verplicht voor berekeningen.", "error")
        return redirect(url_for("main.portfolio"))
    if not pos_value:
        flash("Cost Basis is verplicht.", "error")
        return redirect(url_for("main.portfolio"))
    if not pos_sector:
        flash("Sector is verplicht.", "error")
        return redirect(url_for("main.portfolio"))
    
    try:
        # Valideer en converteer numerieke waarden
        try:
            quantity = int(float(pos_quantity))
            if quantity <= 0:
                flash("Hoeveelheid moet een positief getal zijn.", "error")
                return redirect(url_for("main.portfolio"))
        except (ValueError, TypeError):
            flash("Hoeveelheid moet een geldig getal zijn.", "error")
            return redirect(url_for("main.portfolio"))
        
        try:
            value = float(pos_value)
            if value <= 0:
                flash("Cost Basis moet een positief bedrag zijn.", "error")
                return redirect(url_for("main.portfolio"))
        except (ValueError, TypeError):
            flash("Cost Basis moet een geldig bedrag zijn.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Zoek of maak een portfolio (gebruik de eerste of maak een nieuwe)
        portfolio = db.session.query(Portfolio).first()
        if not portfolio:
            portfolio = Portfolio()
            db.session.add(portfolio)
            db.session.flush()  # Om portfolio_id te krijgen
        
        position = Position(
            pos_name=pos_name,
            pos_type=pos_type or None,
            pos_quantity=quantity,
            pos_value=value,  # Cost basis: wat ze hebben betaald
            pos_ticker=pos_ticker or None,
            pos_sector=pos_sector or None,
            portfolio_id=portfolio.portfolio_id
        )
        db.session.add(position)
        db.session.commit()
        flash(f"Positie '{pos_name}' toegevoegd.", "success")
    except Exception as exc:
        print(f"ERROR: Position insert failed: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij toevoegen van positie.", "error")
    
    return redirect(url_for("main.portfolio"))

# Transactions: Transactie toevoegen
@main.route("/transactions/add", methods=["POST"])
@login_required
def add_transaction():
    transaction_type = request.form.get("transaction_type", "").strip()
    transaction_quantity = request.form.get("transaction_quantity", "").strip()
    transaction_amount = request.form.get("transaction_amount", "").strip()
    transaction_date = request.form.get("transaction_date", "").strip()
    
    if not transaction_type:
        flash("Transactie type is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    
    try:
        # Parse datum
        if transaction_date:
            try:
                parsed_date = datetime.strptime(transaction_date, "%d/%m/%Y")
            except ValueError:
                parsed_date = datetime.now()
        else:
            parsed_date = datetime.now()
        
        # Converteer quantity en amount naar float
        quantity = float(transaction_quantity) if transaction_quantity else 0.0
        amount = float(transaction_amount) if transaction_amount else 0.0
        
        transaction = Transaction(
            transaction_type=transaction_type,
            transaction_quantity=quantity,
            transaction_amount=amount,
            transaction_date=parsed_date
        )
        db.session.add(transaction)
        db.session.commit()
        flash(f"Transactie '{transaction_type}' toegevoegd.", "success")
    except Exception as exc:
        print(f"ERROR: Transaction insert failed: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij toevoegen van transactie.", "error")
    
    return redirect(url_for("main.transactions"))

# Voting: Stemming toevoegen
@main.route("/voting/add", methods=["POST"])
@login_required
def add_voting_proposal():
    proposal_type = request.form.get("proposal_type", "").strip()
    minimum_requirements = request.form.get("minimum_requirements", "").strip()
    
    if not proposal_type:
        flash("Proposal type is verplicht.", "error")
        return redirect(url_for("main.voting"))
    
    try:
        proposal = VotingProposal(
            proposal_type=proposal_type,
            minimum_requirements=minimum_requirements or None
        )
        db.session.add(proposal)
        db.session.commit()
        flash(f"Stemming '{proposal_type}' toegevoegd.", "success")
    except Exception as exc:
        print(f"ERROR: Voting proposal insert failed: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij toevoegen van stemming.", "error")
    
    return redirect(url_for("main.voting"))

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