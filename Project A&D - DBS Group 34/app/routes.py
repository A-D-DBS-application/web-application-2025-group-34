from flask import Blueprint, render_template, request, session, redirect, url_for, g, flash, jsonify  # Added: jsonify for API responses
from functools import wraps
from sqlalchemy import or_
from datetime import datetime
import yfinance as yf  # Added: for company info and financial ratios
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

# Exchange rates voor currency conversie (approximatieve rates)
# Deze rates worden gebruikt om transacties te sorteren op grootte, rekening houdend met wisselkoersen
EXCHANGE_RATES = {
    "USD": 0.92,    # 1 USD = 0.92 EUR (approximate rate)
    "CAD": 0.68,    # 1 CAD = 0.68 EUR (approximate rate)
    "DKK": 0.1339,  # 1 DKK = 0.1339 EUR (5.397,86 DKK = 722,78 EUR)
    "EUR": 1.0,     # 1 EUR = 1 EUR
}

def convert_to_eur(amount, from_currency):
    """Converteer een bedrag naar EUR"""
    if not amount or amount == 0:
        return 0.0
    
    from_currency = (from_currency or "EUR").upper()
    
    # Als al EUR, return direct
    if from_currency == "EUR":
        return float(amount)
    
    # Zoek exchange rate
    rate = EXCHANGE_RATES.get(from_currency, 1.0)
    
    # Converteer naar EUR
    return float(amount) * rate

def format_transaction_date(date_obj):
    """Formats a date to 'd-m-Y' format without leading zeros (e.g., '1-9-2022')"""
    if date_obj is None:
        return datetime.now().strftime("%d-%m-%Y").lstrip('0').replace('-0', '-')
    if hasattr(date_obj, 'strftime'):
        date_str = date_obj.strftime("%d-%m-%Y")
        # Remove leading zeros from day and month
        parts = date_str.split('-')
        day = str(int(parts[0]))
        month = str(int(parts[1]))
        year = parts[2]
        return f"{day}-{month}-{year}"
    if isinstance(date_obj, str):
        # Probeer ISO format te parsen
        try:
            if 'T' in date_obj or '-' in date_obj:
                dt = datetime.fromisoformat(date_obj.replace("Z", "+00:00"))
                date_str = dt.strftime("%d-%m-%Y")
                parts = date_str.split('-')
                day = str(int(parts[0]))
                month = str(int(parts[1]))
                year = parts[2]
                return f"{day}-{month}-{year}"
        except:
            pass
    return str(date_obj)

# Mapping van tickers naar asset namen, exchanges en sectoren (uit de Supabase data)
TICKER_TO_ASSET = {
    "VOW3": {"name": "Volkswagen AG", "exchange": "XFRA", "sector": "Automotive"},
    "WDP": {"name": "Warehouses de Pauw NV", "exchange": "XBRU", "sector": "Real Estate"},
    "GIMB": {"name": "GIMV NV", "exchange": "XBRU", "sector": "Financial Services"},
    "PRX": {"name": "Proximus NV", "exchange": "XBRU", "sector": "Telecommunications"},
    "AMD": {"name": "ADVANCED MICRO DEVICES, INC.", "exchange": "XNAS", "sector": "Tech"},
    "MSFT": {"name": "MICROSOFT CORPORATION", "exchange": "XNAS", "sector": "Tech"},
    "DIS": {"name": "Walt Disney Company", "exchange": "XNYS", "sector": "Entertainment"},
    "PKK": {"name": "Tenet Fintech Group Inc.", "exchange": "XCNQ", "sector": "Financial Services"},
    "XFAB": {"name": "X-FAB Silicon Foundries SE", "exchange": "XBRU", "sector": "Tech"},
    "BABA": {"name": "Alibaba Group Holding Limited", "exchange": "XNYS", "sector": "Tech"},
    "WM": {"name": "Waste Management, Inc.", "exchange": "XNYS", "sector": "Utilities"},
    "ADBE": {"name": "ADOBE INC.", "exchange": "XNAS", "sector": "Tech"},
    "ADYEN": {"name": "Adyen NV", "exchange": "XAMS", "sector": "Tech"},
    "SU": {"name": "Suncor Energy Inc.", "exchange": "XTSE", "sector": "Energy"},
    "XIOR": {"name": "Xior Student Housing NV", "exchange": "XBRU", "sector": "Real Estate"},
    "AEHR": {"name": "Aehr Test Systems", "exchange": "XNAS", "sector": "Tech"},
    "ABI": {"name": "Anheuser-Busch InBev SA/NV", "exchange": "XBRU", "sector": "Consumer Staples"},
    "NVDA": {"name": "NVIDIA Corporation", "exchange": "XNAS", "sector": "Tech"},
    "GOOGL": {"name": "ALPHABET INC.", "exchange": "XNAS", "sector": "Tech"},
}

def _get_asset_info(ticker):
    """Haal asset naam, exchange en sector op op basis van ticker"""
    if ticker and ticker in TICKER_TO_ASSET:
        return TICKER_TO_ASSET[ticker]
    return {"name": ticker or "Onbekend", "exchange": "", "sector": "Unknown"}

def _normalize_transactions(records):
    """Normalize transaction records from Supabase to a consistent format"""
    normalized = []
    if not records:
        print("DEBUG: _normalize_transactions received empty records list")
        return normalized
    
    print(f"DEBUG: Normalizing {len(records)} transaction records")
    
    # Debug: print eerste record om te zien welke velden beschikbaar zijn
    if records and isinstance(records[0], dict):
        print(f"DEBUG: First record keys: {list(records[0].keys())}")
        print(f"DEBUG: First record sample: {str(records[0])[:200]}")
    
    for idx, record in enumerate(records):
        try:
            if isinstance(record, dict):
                # Skip lege of ongeldige records
                if not record:
                    print(f"DEBUG: Skipping empty record at index {idx}")
                    continue
                # Supabase kolommen: transaction_date, transaction_quantity, transaction_type, 
                # transaction_ticker, transaction_currency, asset_type, transaction_share_price
                
                # Transaction ID (gebruik index als fallback)
                transaction_id = (record.get("transaction_id") or record.get("id") or 
                                 record.get("number") or idx + 1)
                
                # Parse transaction_date
                transaction_date = record.get("transaction_date")
                if transaction_date:
                    try:
                        if isinstance(transaction_date, str):
                            dt = datetime.fromisoformat(transaction_date.replace("Z", "+00:00"))
                        else:
                            dt = transaction_date
                        date_str = format_transaction_date(dt)
                    except:
                        date_str = format_transaction_date(datetime.now())
                else:
                    date_str = format_transaction_date(datetime.now())
                
                # Transaction type
                transaction_type = (record.get("transaction_type") or "").upper()
                
                # Quantity
                quantity = record.get("transaction_quantity") or 0
                try:
                    quantity = float(quantity) if quantity else 0.0
                except (ValueError, TypeError):
                    quantity = 0.0
                
                # Price per share
                price = record.get("transaction_share_price") or None
                try:
                    price = float(price) if price else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                
                # Ticker
                ticker = record.get("transaction_ticker") or ""
                
                # Currency (zorg dat het uppercase is)
                currency = (record.get("transaction_currency") or "EUR").upper()
                
                # Bereken Total Transaction Amount (quantity * price)
                total_amount = quantity * price if price else 0.0
                
                # Format prijs en totaal
                price_str = format_currency(price) if price else "0,00"
                total_str = format_currency(abs(total_amount)) if total_amount else "0,00"
                
                # Converteer naar EUR voor sortering (maar behoud originele currency)
                # Gebruik absolute waarde voor sortering om grootte te vergelijken
                total_amount_eur_for_sorting = convert_to_eur(abs(total_amount), currency)
                
                # Debug output voor eerste paar transacties
                if idx < 3:
                    print(f"DEBUG: Transaction {idx + 1}: {currency} {total_amount} -> EUR {total_amount_eur_for_sorting:.2f}")
                
                # Asset class/type - probeer eerst asset_class, dan asset_type, anders default
                asset_class = record.get("asset_class") or record.get("asset_type") or "Stock"
                
                # Asset naam, exchange en sector - gebruik mapping op basis van ticker
                asset_info = _get_asset_info(ticker)
                asset_name = asset_info["name"]
                exchange = asset_info["exchange"]
                sector = asset_info.get("sector", "Unknown")  # Haal sector uit mapping of uit Supabase
                
                # Probeer sector ook uit Supabase record te halen (als die bestaat)
                sector = record.get("sector") or asset_info.get("sector") or "Unknown"
                
                # Realized profit/loss - niet beschikbaar in huidige Supabase schema
                realized_pl = None
                
                # Format asset display (gebruik naam met exchange:ticker indien beschikbaar)
                if exchange and ticker:
                    asset_display = f"{asset_name} ({exchange}:{ticker})"
                else:
                    asset_display = asset_name
                
                normalized.append({
                    "number": transaction_id,
                    "date": date_str,
                    "type": transaction_type,
                    "asset": asset_display,
                    "asset_name": asset_name,
                    "ticker": ticker,
                    "exchange": exchange,
                    "currency": currency,  # Originele currency
                    "asset_class": asset_class,
                    "sector": sector,
                    "units": quantity,
                    "price": price_str,
                    "price_value": price,  # Originele prijs
                    "total": f"{'-' if total_amount < 0 else ''}{total_str}",
                    "total_value": float(total_amount),  # Originele total amount
                    "total_value_eur": float(total_amount_eur_for_sorting),  # In EUR voor sortering
                    "profitLoss": float(realized_pl) if realized_pl is not None else None,
                })
            else:
                # Voor SQLAlchemy objecten (fallback)
                quantity_sql = float(getattr(record, 'transaction_quantity', 0)) or 0.0
                amount_sql = float(getattr(record, 'transaction_amount', 0)) or 0.0
                currency_sql = (getattr(record, 'currency', 'EUR') or 'EUR').upper()
                
                # Bereken prijs per share
                price_sql = amount_sql / quantity_sql if quantity_sql > 0 else 0.0
                
                # Converteer naar EUR voor sortering (maar behoud originele currency)
                # Gebruik absolute waarde voor sortering om grootte te vergelijken
                total_eur_sql = convert_to_eur(abs(amount_sql), currency_sql)
                
                # Haal sector op - eerst uit database, anders uit ticker mapping
                ticker_sql = getattr(record, 'ticker', '') or ''
                asset_info_sql = _get_asset_info(ticker_sql)
                sector_sql = getattr(record, 'sector', None) or asset_info_sql.get("sector", "Unknown")
                
                normalized.append({
                    "number": getattr(record, 'transaction_id', None) or idx + 1,
                    "date": format_transaction_date(getattr(record, 'transaction_date', None)),
                    "type": (getattr(record, 'transaction_type', '') or '').upper(),
                    "asset": getattr(record, 'asset_name', '') or getattr(record, 'ticker', '') or 'Onbekend',
                    "asset_name": getattr(record, 'asset_name', '') or getattr(record, 'ticker', '') or 'Onbekend',
                    "ticker": ticker_sql,
                    "exchange": getattr(record, 'exchange', '') or asset_info_sql.get("exchange", ""),
                    "currency": currency_sql,  # Originele currency
                    "asset_class": getattr(record, 'asset_class', 'Stock') or 'Stock',
                    "sector": sector_sql,
                    "units": quantity_sql,
                    "price": format_currency(price_sql),
                    "price_value": price_sql,  # Originele prijs
                    "total": format_currency(abs(amount_sql)),
                    "total_value": float(amount_sql),  # Originele total amount
                    "total_value_eur": float(total_eur_sql),  # In EUR voor sortering
                    "profitLoss": float(getattr(record, 'realized_profit_loss', 0)) if getattr(record, 'realized_profit_loss', None) is not None else None,
                })
        except Exception as e:
            print(f"ERROR: Failed to normalize transaction record {idx}: {e}")
            print(f"ERROR: Record type: {type(record)}")
            if isinstance(record, dict):
                print(f"ERROR: Record keys: {list(record.keys())}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"DEBUG: Successfully normalized {len(normalized)} out of {len(records)} transaction records")
    if normalized:
        print(f"DEBUG: Sample normalized record: {normalized[0]}")
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

# ============================================================================
# COMPANY INFO MODAL FEATURE - START
# Deze route wordt gebruikt wanneer je op een asset naam klikt in portfolio
# Om terug te draaien: verwijder deze volledige functie (tot # COMPANY INFO MODAL FEATURE - END)
# ============================================================================
@main.route("/portfolio/company/<ticker>")
@login_required
def get_company_info(ticker):
    """Haal company info en financial ratios op via yfinance"""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        # Check if info is available (yfinance returns empty dict if ticker not found)
        if not info or len(info) == 0:
            return jsonify({
                'success': False,
                'error': f'Ticker "{ticker}" not found or no data available'
            }), 404
        
        # Haal portfolio positie op voor "Your Position" data
        position_data = {}
        try:
            position = db.session.query(Position).filter(
                or_(Position.pos_ticker == ticker, Position.pos_name == ticker)
            ).first()
            
            if position:
                quantity = position.pos_quantity or 0
                cost_basis = float(position.pos_value) if position.pos_value else 0.0
                current_price = position.current_price or 0.0
                market_value = current_price * quantity if current_price and quantity else 0.0
                pnl_value = market_value - cost_basis
                pnl_percent = (pnl_value / cost_basis * 100) if cost_basis > 0 else 0.0
                
                position_data = {
                    'quantity': quantity,
                    'average_cost': format_currency(cost_basis / quantity) if quantity > 0 else format_currency(0),
                    'total_cost': format_currency(cost_basis),
                    'current_price': format_currency(current_price),
                    'market_value': format_currency(market_value),
                    'pnl_value': format_currency(pnl_value),
                    'pnl_percent': f"{'+' if pnl_percent >= 0 else ''}{pnl_percent:.2f}%"
                }
        except Exception as e:
            print(f"Error fetching position data: {e}")
        
        # Format financial data
        def safe_get(key, default='N/A', format_func=None):
            value = info.get(key)
            if value is None or value == '':
                return default
            if format_func:
                try:
                    return format_func(value)
                except:
                    return default
            return value
        
        # Company info
        company_data = {
            'name': safe_get('longName', safe_get('shortName', ticker)),
            'sector': safe_get('sector', 'N/A'),
            'industry': safe_get('industry', 'N/A'),
            'country': safe_get('country', 'N/A'),
            'description': (lambda desc: (desc[:500] + '...' if len(desc) > 500 else desc) if desc and desc != 'No description available.' else 'No description available.')(safe_get('longBusinessSummary', 'No description available.')),
            'website': safe_get('website', 'N/A'),
            'employees': safe_get('fullTimeEmployees', 'N/A', lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else x),
            'market_cap': safe_get('marketCap', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) else x),
            'currency': safe_get('currency', 'EUR'),
        }
        
        # Financial Ratios
        ratios = {
            'pe_ratio': safe_get('trailingPE', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'forward_pe': safe_get('forwardPE', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'peg_ratio': safe_get('pegRatio', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'price_to_book': safe_get('priceToBook', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'price_to_sales': safe_get('priceToSalesTrailing12Months', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'dividend_yield': safe_get('dividendYield', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'dividend_rate': safe_get('dividendRate', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'payout_ratio': safe_get('payoutRatio', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'eps': safe_get('trailingEps', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) else x),
            'eps_forward': safe_get('forwardEps', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) else x),
            'return_on_equity': safe_get('returnOnEquity', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'return_on_assets': safe_get('returnOnAssets', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'profit_margin': safe_get('profitMargins', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'operating_margin': safe_get('operatingMargins', 'N/A', lambda x: f"{(float(x) * 100):.2f}%" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'debt_to_equity': safe_get('debtToEquity', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            'current_ratio': safe_get('currentRatio', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
            '52_week_high': safe_get('fiftyTwoWeekHigh', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) else x),
            '52_week_low': safe_get('fiftyTwoWeekLow', 'N/A', lambda x: format_currency(x) if isinstance(x, (int, float)) else x),
            'beta': safe_get('beta', 'N/A', lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) and x > 0 else 'N/A'),
        }
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'company': company_data,
            'ratios': ratios,
            'position': position_data
        })
        
    except Exception as e:
        print(f"Error fetching company info for {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
# ============================================================================
# COMPANY INFO MODAL FEATURE - END
# ============================================================================

def _fetch_transactions():
    """Fetch transactions from database - try direct SQL query first, then Supabase REST API, then mock data"""
    
    # Probeer eerst direct SQL query via SQLAlchemy (snelste methode)
    try:
        print("DEBUG: Attempting to fetch transactions via direct SQL query...")
        # Query direct uit de transactions tabel met raw SQL om alle velden te krijgen
        from sqlalchemy import text
        query = text("""
            SELECT 
                transaction_id,
                transaction_date,
                transaction_quantity,
                transaction_type,
                transaction_ticker,
                transaction_currency,
                asset_type,
                transaction_share_price,
                sector,
                asset_class
            FROM transactions
            ORDER BY transaction_date ASC
            LIMIT 1000
        """)
        result = db.session.execute(query)
        rows = result.fetchall()
        
        if rows:
            print(f"DEBUG: Fetched {len(rows)} transactions via direct SQL query")
            # Converteer rows naar dicts
            columns = ['transaction_id', 'transaction_date', 'transaction_quantity', 
                      'transaction_type', 'transaction_ticker', 'transaction_currency', 
                      'asset_type', 'transaction_share_price', 'sector', 'asset_class']
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i] if i < len(row) else None
                data.append(row_dict)
            
            if data and len(data) > 0:
                print(f"DEBUG: First record from SQL: {data[0]}")
                normalized = _normalize_transactions(data)
                if normalized:
                    print(f"DEBUG: Successfully normalized {len(normalized)} transactions from SQL")
                    return normalized
    except Exception as exc:
        print(f"WARNING: Direct SQL query failed: {exc}")
        import traceback
        traceback.print_exc()
    
    # Probeer via Supabase REST API
    if supabase is not None:
        try:
            print("DEBUG: Attempting to fetch transactions from Supabase REST API...")
            # Haal alle transacties op (geen limit, gebruik range queries als nodig)
            response = supabase.table("transactions").select("*").order("transaction_date", desc=False).limit(1000).execute()
            data = response.data if hasattr(response, 'data') else []
            
            if data:
                print(f"DEBUG: Fetched {len(data)} transactions from Supabase REST API")
                if len(data) > 0:
                    print(f"DEBUG: First record from Supabase: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
                    print(f"DEBUG: Sample data: {str(data[0])[:300] if data else 'no data'}")
                
                normalized = _normalize_transactions(data)
                if normalized:
                    print(f"DEBUG: Successfully normalized {len(normalized)} transactions from Supabase (expected ~75)")
                    return normalized
                else:
                    print(f"WARNING: Supabase returned {len(data)} records but normalization resulted in 0 records")
                    print(f"DEBUG: This suggests a problem in the normalization function")
        except Exception as exc:
            print(f"WARNING: Supabase REST API fetch failed: {exc}")
            import traceback
            traceback.print_exc()
    else:
        print("DEBUG: Supabase client is None, skipping Supabase REST API fetch")
    
    # Fallback naar SQLAlchemy ORM
    try:
        print("DEBUG: Attempting to fetch transactions via SQLAlchemy ORM...")
        transactions = db.session.query(Transaction).order_by(Transaction.transaction_date.asc()).all()
        if transactions:
            normalized = _normalize_transactions(transactions)
            print(f"DEBUG: Fetched {len(normalized)} transactions from SQLAlchemy ORM")
            return normalized
    except Exception as exc:
        print(f"WARNING: SQLAlchemy ORM fetch failed: {exc}")
        import traceback
        traceback.print_exc()
    
    # Laatste fallback: mock data
    print("DEBUG: Using mock data as final fallback")
    return _normalize_transactions(MOCK_TRANSACTIONS)

# Transactions pagina (Nu de centrale bron voor transactiegegevens)
@main.route("/transactions")
@login_required
def transactions():
    transactions_data = _fetch_transactions()
    
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
    # Haal alle form velden op
    transaction_date = request.form.get("transaction_date", "").strip()
    transaction_type = request.form.get("transaction_type", "").strip()
    asset_name = request.form.get("asset_name", "").strip()
    transaction_ticker = request.form.get("transaction_ticker", "").strip()
    transaction_quantity = request.form.get("transaction_quantity", "").strip()
    transaction_share_price = request.form.get("transaction_share_price", "").strip()
    transaction_currency = request.form.get("transaction_currency", "EUR").strip()
    asset_class = request.form.get("asset_class", "Stock").strip()
    sector = request.form.get("sector", "").strip()
    transaction_amount = request.form.get("transaction_amount", "").strip()
    
    # Validatie van verplichte velden
    if not transaction_type:
        flash("Transactie type is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not transaction_date:
        flash("Datum is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not asset_name:
        flash("Asset naam is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not transaction_ticker:
        flash("Ticker is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not transaction_quantity:
        flash("Hoeveelheid is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not transaction_share_price:
        flash("Prijs per aandeel is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    if not asset_class:
        flash("Asset class is verplicht.", "error")
        return redirect(url_for("main.transactions"))
    
    try:
        # Parse datum (ondersteun zowel dd/mm/yyyy als dd-mm-yyyy)
        parsed_date = None
        if transaction_date:
            for date_format in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    parsed_date = datetime.strptime(transaction_date, date_format)
                    break
                except ValueError:
                    continue
            if not parsed_date:
                parsed_date = datetime.now()
        else:
            parsed_date = datetime.now()
        
        # Converteer numerieke waarden
        try:
            quantity = float(transaction_quantity) if transaction_quantity else 0.0
            if quantity <= 0:
                flash("Hoeveelheid moet een positief getal zijn.", "error")
                return redirect(url_for("main.transactions"))
        except (ValueError, TypeError):
            flash("Hoeveelheid moet een geldig getal zijn.", "error")
            return redirect(url_for("main.transactions"))
        
        try:
            share_price = float(transaction_share_price) if transaction_share_price else 0.0
            if share_price <= 0:
                flash("Prijs per aandeel moet een positief getal zijn.", "error")
                return redirect(url_for("main.transactions"))
        except (ValueError, TypeError):
            flash("Prijs per aandeel moet een geldig getal zijn.", "error")
            return redirect(url_for("main.transactions"))
        
        # Bereken total amount (quantity * price)
        total_amount = quantity * share_price
        
        # Gebruik opgegeven amount als die bestaat, anders bereken
        if transaction_amount:
            try:
                calculated_amount = float(transaction_amount)
                # Gebruik de opgegeven waarde (voor geval van afronding verschillen)
                final_amount = calculated_amount
            except (ValueError, TypeError):
                final_amount = total_amount
        else:
            final_amount = total_amount
        
        # Probeer eerst via direct SQL insert (voor alle velden)
        try:
            from sqlalchemy import text
            sql_query = text("""
                INSERT INTO transactions (
                    transaction_type, transaction_quantity, transaction_amount,
                    transaction_date, transaction_ticker, transaction_currency,
                    transaction_share_price, asset_type, asset_class, sector
                ) VALUES (
                    :transaction_type, :transaction_quantity, :transaction_amount,
                    :transaction_date, :transaction_ticker, :transaction_currency,
                    :transaction_share_price, :asset_type, :asset_class, :sector
                )
            """)
            db.session.execute(sql_query, {
                "transaction_type": transaction_type.upper(),
                "transaction_quantity": quantity,
                "transaction_amount": final_amount,
                "transaction_date": parsed_date,
                "transaction_ticker": transaction_ticker,
                "transaction_currency": transaction_currency.upper(),
                "transaction_share_price": share_price,
                "asset_type": asset_class,
                "asset_class": asset_class,
                "sector": sector if sector else None
            })
            db.session.commit()
            print(f"DEBUG: Transaction saved to database via direct SQL")
        except Exception as sql_exc:
            print(f"WARNING: Direct SQL insert failed: {sql_exc}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
        
        # Probeer ook via Supabase REST API (als backup)
        if supabase is not None:
            try:
                supabase_data = {
                    "transaction_type": transaction_type.upper(),
                    "transaction_quantity": quantity,
                    "transaction_amount": final_amount,
                    "transaction_date": parsed_date.isoformat() + "+00:00",
                    "transaction_ticker": transaction_ticker,
                    "transaction_currency": transaction_currency.upper(),
                    "transaction_share_price": share_price,
                    "asset_type": asset_class,  # Voor backward compatibility
                    "asset_class": asset_class,
                    "sector": sector if sector else None
                }
                response = supabase.table("transactions").insert(supabase_data).execute()
                print(f"DEBUG: Transaction saved to Supabase: {response.data if hasattr(response, 'data') else 'success'}")
            except Exception as supabase_exc:
                print(f"WARNING: Supabase insert failed: {supabase_exc}")
                import traceback
                traceback.print_exc()
        
        flash(f"Transactie '{transaction_type}' voor {asset_name} ({transaction_ticker}) toegevoegd.", "success")
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