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

# Mapping van tickers naar asset namen en exchanges (uit de Supabase data)
TICKER_TO_ASSET = {
    "VOW3": {"name": "Volkswagen AG", "exchange": "XFRA"},
    "WDP": {"name": "Warehouses de Pauw NV", "exchange": "XBRU"},
    "GIMB": {"name": "GIMV NV", "exchange": "XBRU"},
    "PRX": {"name": "Proximus NV", "exchange": "XBRU"},
    "AMD": {"name": "ADVANCED MICRO DEVICES, INC.", "exchange": "XNAS"},
    "MSFT": {"name": "MICROSOFT CORPORATION", "exchange": "XNAS"},
    "DIS": {"name": "Walt Disney Company", "exchange": "XNYS"},
    "PKK": {"name": "Tenet Fintech Group Inc.", "exchange": "XCNQ"},
    "XFAB": {"name": "X-FAB Silicon Foundries SE", "exchange": "XBRU"},
    "BABA": {"name": "Alibaba Group Holding Limited", "exchange": "XNYS"},
    "WM": {"name": "Waste Management, Inc.", "exchange": "XNYS"},
    "ADBE": {"name": "ADOBE INC.", "exchange": "XNAS"},
    "ADYEN": {"name": "Adyen NV", "exchange": "XAMS"},
    "SU": {"name": "Suncor Energy Inc.", "exchange": "XTSE"},
    "XIOR": {"name": "Xior Student Housing NV", "exchange": "XBRU"},
    "AEHR": {"name": "Aehr Test Systems", "exchange": "XNAS"},
    "ABI": {"name": "Anheuser-Busch InBev SA/NV", "exchange": "XBRU"},
    "NVDA": {"name": "NVIDIA Corporation", "exchange": "XNAS"},
    "GOOGL": {"name": "ALPHABET INC.", "exchange": "XNAS"},
}

def _get_asset_info(ticker):
    """Haal asset naam en exchange op op basis van ticker"""
    if ticker and ticker in TICKER_TO_ASSET:
        return TICKER_TO_ASSET[ticker]
    return {"name": ticker or "Onbekend", "exchange": ""}

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
                
                # Bereken Total Transaction Amount (quantity * price)
                total_amount = quantity * price if price else 0.0
                
                # Format prijs en totaal
                price_str = format_currency(price) if price else "0,00"
                total_str = format_currency(abs(total_amount)) if total_amount else "0,00"
                
                # Ticker
                ticker = record.get("transaction_ticker") or ""
                
                # Currency
                currency = record.get("transaction_currency") or "EUR"
                
                # Asset class/type
                asset_class = record.get("asset_type") or "Stock"
                
                # Asset naam en exchange - gebruik mapping op basis van ticker
                asset_info = _get_asset_info(ticker)
                asset_name = asset_info["name"]
                exchange = asset_info["exchange"]
                
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
                    "currency": currency,
                    "asset_class": asset_class,
                    "units": quantity,
                    "price": price_str,
                    "price_value": price,
                    "total": f"{'-' if total_amount < 0 else ''}{total_str}",
                    "total_value": float(total_amount),
                    "profitLoss": float(realized_pl) if realized_pl is not None else None,
                })
            else:
                # Voor SQLAlchemy objecten (fallback)
                normalized.append({
                    "number": getattr(record, 'transaction_id', None) or idx + 1,
                    "date": format_transaction_date(getattr(record, 'transaction_date', None)),
                    "type": (getattr(record, 'transaction_type', '') or '').upper(),
                    "asset": getattr(record, 'asset_name', '') or getattr(record, 'ticker', '') or 'Onbekend',
                    "asset_name": getattr(record, 'asset_name', '') or getattr(record, 'ticker', '') or 'Onbekend',
                    "ticker": getattr(record, 'ticker', '') or '',
                    "exchange": getattr(record, 'exchange', '') or '',
                    "currency": getattr(record, 'currency', 'EUR') or 'EUR',
                    "asset_class": getattr(record, 'asset_class', 'Stock') or 'Stock',
                    "units": float(getattr(record, 'transaction_quantity', 0)) or 0.0,
                    "price": format_currency(float(getattr(record, 'transaction_amount', 0)) / float(getattr(record, 'transaction_quantity', 1)) if getattr(record, 'transaction_quantity', 0) else 0),
                    "price_value": float(getattr(record, 'transaction_amount', 0)) / float(getattr(record, 'transaction_quantity', 1)) if getattr(record, 'transaction_quantity', 0) else 0.0,
                    "total": format_currency(abs(float(getattr(record, 'transaction_amount', 0)))),
                    "total_value": float(getattr(record, 'transaction_amount', 0)) or 0.0,
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
                transaction_share_price
            FROM transactions
            ORDER BY transaction_date DESC
            LIMIT 1000
        """)
        result = db.session.execute(query)
        rows = result.fetchall()
        
        if rows:
            print(f"DEBUG: Fetched {len(rows)} transactions via direct SQL query")
            # Converteer rows naar dicts
            columns = ['transaction_id', 'transaction_date', 'transaction_quantity', 
                      'transaction_type', 'transaction_ticker', 'transaction_currency', 
                      'asset_type', 'transaction_share_price']
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
            response = supabase.table("transactions").select("*").order("transaction_date", desc=True).limit(1000).execute()
            data = response.data if hasattr(response, 'data') else []
            
            if data:
                print(f"DEBUG: Fetched {len(data)} transactions from Supabase REST API")
                if len(data) > 0:
                    print(f"DEBUG: First record from Supabase: {data[0]}")
                
                normalized = _normalize_transactions(data)
                if normalized:
                    print(f"DEBUG: Successfully normalized {len(normalized)} transactions from Supabase")
                    return normalized
                else:
                    print(f"WARNING: Supabase returned {len(data)} records but normalization resulted in 0 records")
        except Exception as exc:
            print(f"WARNING: Supabase REST API fetch failed: {exc}")
            import traceback
            traceback.print_exc()
    else:
        print("DEBUG: Supabase client is None, skipping Supabase REST API fetch")
    
    # Fallback naar SQLAlchemy ORM
    try:
        print("DEBUG: Attempting to fetch transactions via SQLAlchemy ORM...")
        transactions = db.session.query(Transaction).order_by(Transaction.transaction_date.desc()).all()
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
    
    # Bereken totaal realized profit/loss
    realized_total = 0.0
    for t in transactions_data:
        if t.get("profitLoss") is not None:
            realized_total += float(t["profitLoss"])
    
    return render_template("transactions.html", transactions=transactions_data, realized_total=realized_total)
    
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