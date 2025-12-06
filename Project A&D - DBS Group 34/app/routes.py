from flask import Blueprint, render_template, request, session, redirect, url_for, g, flash, jsonify, Response, current_app, send_from_directory, send_file, abort  # Added: Response for iCal downloads, send_file for downloads
from functools import wraps
from sqlalchemy import or_
from datetime import datetime, timedelta
import yfinance as yf  # Added: for company info and financial ratios
import pytz  # Added: for Europe/Brussels timezone handling
import zipfile
import os
from pathlib import Path
from . import supabase, db
from .models import (
    Member, Announcement, Event, Position, Transaction, VotingProposal, Vote, Portfolio, FileItem,
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

# Weekdag-namen in het Nederlands voor de "Vandaag:"-sectie van de agenda
WEEKDAY_NAMES_NL = [
    "maandag",
    "dinsdag",
    "woensdag",
    "donderdag",
    "vrijdag",
    "zaterdag",
    "zondag",
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
                    "transaction_id": transaction_id,  # Add transaction_id for edit/delete functionality
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
                
                transaction_id_sql = getattr(record, 'transaction_id', None) or idx + 1
                normalized.append({
                    "number": transaction_id_sql,
                    "transaction_id": transaction_id_sql,  # Add transaction_id for edit/delete functionality
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
    """
    Haal alle events op en normaliseer naar een rijk formaat met datetime,
    zodat we ze kunnen groeperen in toekomstige, vandaag en voorbije events.
    Dit verandert niets aan het onderliggende Event-model/Supabase-schema.
    """
    tz = pytz.timezone("Europe/Brussels")

    def _ensure_datetime(date_str, time_str):
        """Helper: parse datum + tijd strings naar timezone-aware datetime."""
        if not date_str:
            return datetime.now(tz)
        # Ondersteun dd/mm/YYYY (huidige UI) en ISO formats als fallback
        parsed = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                parsed = datetime.now()
        if time_str:
            try:
                t = datetime.strptime(time_str, "%H:%M")
                parsed = parsed.replace(hour=t.hour, minute=t.minute)
            except ValueError:
                pass
        # Zorg dat datetime timezone-aware is in Europe/Brussels
        if parsed.tzinfo is None:
            parsed = tz.localize(parsed)
        else:
            parsed = parsed.astimezone(tz)
        return parsed

    normalized = []

    # 1) Probeer eerst via SQLAlchemy (PostgreSQL direct)
    try:
        events = db.session.query(Event).order_by(Event.event_date.asc()).all()
        if events:
            for evt in events:
                event_dt = evt.event_date or datetime.now(tz)
                # Zorg dat event_dt timezone-aware is
                if event_dt.tzinfo is None:
                    event_dt = tz.localize(event_dt)
                else:
                    event_dt = event_dt.astimezone(tz)

                normalized.append({
                    "id": evt.event_number,
                    "title": evt.event_name,
                    "datetime": event_dt,
                    "date": event_dt.strftime("%d/%m/%Y"),
                    "time": event_dt.strftime("%H:%M"),
                    "location": evt.location or "Onbekende locatie",
                })
            return normalized
    except Exception as exc:
        print(f"WARNING: SQLAlchemy event fetch failed: {exc}")

    # 2) Fallback naar Supabase REST API
    if supabase is not None:
        try:
            response = supabase.table("events").select("*").order("event_date", desc=False).execute()
            data = response.data or []
            for row in data:
                event_date_str = row.get("event_date")
                dt = _ensure_datetime(event_date_str, None) if event_date_str else datetime.now(tz)
                normalized.append({
                    "id": row.get("event_number"),
                    "title": row.get("event_name", ""),
                    "datetime": dt,
                    "date": dt.strftime("%d/%m/%Y"),
                    "time": dt.strftime("%H:%M"),
                    "location": row.get("location", "Onbekende locatie"),
                })
            if normalized:
                return normalized
        except Exception as exc:
            print(f"WARNING: Supabase event fetch failed: {exc}")

    # 3) Laatste fallback naar mock-data (gebruikt dezelfde normalisatie)
    for row in MOCK_UPCOMING_EVENTS:
        dt = _ensure_datetime(row.get("date"), row.get("time"))
        normalized.append({
            "id": None,
            "title": row.get("title", ""),
            "datetime": dt,
            "date": dt.strftime("%d/%m/%Y"),
            "time": dt.strftime("%H:%M"),
            "location": row.get("location", "Onbekende locatie"),
        })
    return normalized


def _group_events_by_date(events):
    """
    Groepeer events in toekomstige, vandaag en voorbije secties.
    - Toekomstige Events: event_date > vandaag (asc)
    - Vandaag: zelfde dag als vandaag (asc)
    - Voorbije Events: event_date < vandaag (desc)
    """
    tz = pytz.timezone("Europe/Brussels")
    today = datetime.now(tz).date()

    upcoming = []
    today_events = []
    past = []

    for ev in events or []:
        dt = ev.get("datetime")
        if not dt:
            # reconstructeer uit strings indien nodig
            dt = datetime.now(tz)
        ev_date = dt.date()

        if ev_date > today:
            upcoming.append(ev)
        elif ev_date == today:
            today_events.append(ev)
        else:
            past.append(ev)

    # Sorteer zoals gevraagd
    upcoming.sort(key=lambda e: e.get("datetime"))
    today_events.sort(key=lambda e: e.get("datetime"))
    past.sort(key=lambda e: e.get("datetime"), reverse=True)

    return {
        "upcoming": upcoming,
        "today": today_events,
        "past": past,
    }

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
    """Overzichtspagina met aankondigingen en nieuwe agenda-layout (Toekomstige/Vandaag/Voorbije)."""
    events = _fetch_events()
    grouped = _group_events_by_date(events)

    # Bouw label "Vandaag: <weekdag> d/m/jjjj" in het Nederlands
    tz = pytz.timezone("Europe/Brussels")
    today_dt = datetime.now(tz)
    weekday_name = WEEKDAY_NAMES_NL[today_dt.weekday()]
    today_label = f"Vandaag: {weekday_name} {today_dt.day}/{today_dt.month}/{today_dt.year}"

    return render_template(
        "dashboard.html",
        announcements=_fetch_announcements(),
        upcoming_events=grouped["upcoming"],
        today_events=grouped["today"],
        past_events=grouped["past"],
        today_label=today_label,
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

@main.route("/announcements/get-all")
@login_required
def get_all_announcements():
    """Haal alle announcements op voor dropdown selectie"""
    try:
        announcements = db.session.query(Announcement).order_by(Announcement.created_at.desc()).all()
        announcements_list = []
        
        for ann in announcements:
            created_at = ann.created_at
            if created_at.tzinfo is None:
                tz = pytz.timezone("Europe/Brussels")
                created_at = tz.localize(created_at)
            else:
                created_at = created_at.astimezone(pytz.timezone("Europe/Brussels"))
            
            announcements_list.append({
                "id": ann.id,
                "title": ann.title or 'Onbekend',
                "date": created_at.strftime("%d/%m/%Y"),
                "display": f"{ann.title or 'Onbekend'} - {created_at.strftime('%d/%m/%Y')}"
            })
        return jsonify({"announcements": announcements_list})
    except Exception as e:
        print(f"Error fetching all announcements: {e}")
        return jsonify({"error": "Fout bij ophalen van announcements."}), 500

@main.route("/announcements/get-details/<int:announcement_id>")
@login_required
def get_announcement_details(announcement_id):
    """Haal announcement details op voor editing"""
    try:
        announcement = db.session.query(Announcement).filter(Announcement.id == announcement_id).first()
        
        if not announcement:
            return jsonify({'error': 'Announcement niet gevonden.'}), 404
        
        created_at = announcement.created_at or datetime.now()
        if created_at.tzinfo is None:
            tz = pytz.timezone("Europe/Brussels")
            created_at = tz.localize(created_at)
        else:
            created_at = created_at.astimezone(pytz.timezone("Europe/Brussels"))
        
        return jsonify({
            'id': announcement.id,
            'title': announcement.title or '',
            'body': announcement.body or '',
            'author': announcement.author or '',
            'date': created_at.strftime("%d/%m/%Y")
        })
    except Exception as e:
        print(f"Error fetching announcement details: {e}")
        return jsonify({'error': 'Fout bij ophalen van announcement details.'}), 500

@main.route("/announcements/update", methods=["POST"])
@login_required
def update_announcement():
    """Update een announcement"""
    try:
        announcement_id = request.form.get("announcement_id", "").strip()
        
        if not announcement_id:
            flash("Announcement ID ontbreekt.", "error")
            return redirect(url_for("main.dashboard"))
        
        try:
            announcement_id = int(announcement_id)
        except (ValueError, TypeError):
            flash("Ongeldig announcement ID.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Find announcement
        announcement = db.session.query(Announcement).filter(Announcement.id == announcement_id).first()
        
        if not announcement:
            flash("Announcement niet gevonden.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Get form data
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        
        # Validate required fields
        if not title:
            flash("Titel is verplicht.", "error")
            return redirect(url_for("main.dashboard"))
        
        if not body:
            flash("Bericht is verplicht.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Update announcement
        announcement.title = title
        announcement.body = body
        
        db.session.commit()
        
        flash(f"Announcement '{title}' is succesvol bijgewerkt.", "success")
    except Exception as exc:
        print(f"WARNING: Announcement update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van announcement.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.dashboard"))

@main.route("/announcements/delete", methods=["POST"])
@login_required
def delete_announcement():
    """Verwijder een announcement"""
    try:
        announcement_id = request.form.get("announcement_id", "").strip()
        
        if not announcement_id:
            flash("Announcement ID ontbreekt.", "error")
            return redirect(url_for("main.dashboard"))
        
        try:
            announcement_id = int(announcement_id)
        except (ValueError, TypeError):
            flash("Ongeldig announcement ID.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Find announcement
        announcement = db.session.query(Announcement).filter(Announcement.id == announcement_id).first()
        
        if not announcement:
            flash("Announcement niet gevonden.", "error")
            return redirect(url_for("main.dashboard"))
        
        title = announcement.title
        
        # Delete announcement
        db.session.delete(announcement)
        db.session.commit()
        
        flash(f"Announcement '{title}' is succesvol verwijderd.", "success")
    except Exception as exc:
        print(f"WARNING: Announcement delete failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij verwijderen van announcement.", "error")
        db.session.rollback()
    
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


# --- Agenda / Events: Edit and Delete routes ---

@main.route("/events/get-all")
@login_required
def get_all_events():
    """Haal alle events op voor dropdown selectie"""
    try:
        events = db.session.query(Event).order_by(Event.event_date.asc()).all()
        events_list = []
        for evt in events:
            event_dt = evt.event_date or datetime.now()
            if event_dt.tzinfo is None:
                tz = pytz.timezone("Europe/Brussels")
                event_dt = tz.localize(event_dt)
            else:
                event_dt = event_dt.astimezone(pytz.timezone("Europe/Brussels"))
            
            events_list.append({
                "event_number": evt.event_number,
                "event_name": evt.event_name,
                "event_date": event_dt.strftime("%d/%m/%Y"),
                "event_time": event_dt.strftime("%H:%M"),
                "location": evt.location or "Onbekende locatie",
                "display": f"{evt.event_name} - {event_dt.strftime('%d/%m/%Y %H:%M')}"
            })
        return jsonify({"events": events_list})
    except Exception as e:
        print(f"Error fetching all events: {e}")
        return jsonify({"error": "Fout bij ophalen van events."}), 500

@main.route("/events/get-details/<int:event_number>")
@login_required
def get_event_details(event_number):
    """Haal event details op voor editing"""
    try:
        event = db.session.query(Event).filter(Event.event_number == event_number).first()
        
        if not event:
            return jsonify({'error': 'Event niet gevonden.'}), 404
        
        event_dt = event.event_date or datetime.now()
        if event_dt.tzinfo is None:
            tz = pytz.timezone("Europe/Brussels")
            event_dt = tz.localize(event_dt)
        else:
            event_dt = event_dt.astimezone(pytz.timezone("Europe/Brussels"))
        
        return jsonify({
            'event_number': event.event_number,
            'event_name': event.event_name or '',
            'event_date': event_dt.strftime("%d/%m/%Y"),
            'event_time': event_dt.strftime("%H:%M"),
            'location': event.location or ''
        })
    except Exception as e:
        print(f"Error fetching event details: {e}")
        return jsonify({'error': 'Fout bij ophalen van event details.'}), 500

@main.route("/events/update", methods=["POST"])
@login_required
def update_event():
    """Update een event"""
    try:
        event_number = request.form.get("event_number", "").strip()
        
        if not event_number:
            flash("Event nummer ontbreekt.", "error")
            return redirect(url_for("main.dashboard"))
        
        try:
            event_number = int(event_number)
        except (ValueError, TypeError):
            flash("Ongeldig event nummer.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Find event
        event = db.session.query(Event).filter(Event.event_number == event_number).first()
        
        if not event:
            flash("Event niet gevonden.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Get form data
        event_name = request.form.get("event_name", "").strip()
        event_date = request.form.get("event_date", "").strip()
        event_time = request.form.get("event_time", "").strip()
        location = request.form.get("location", "").strip()
        
        # Validate required fields
        if not event_name:
            flash("Event naam is verplicht.", "error")
            return redirect(url_for("main.dashboard"))
        
        if not event_date:
            flash("Datum is verplicht.", "error")
            return redirect(url_for("main.dashboard"))
        
        if not event_time:
            event_time = "00:00"
        
        # Parse and format date
        iso_date = _format_event_date(event_date, event_time)
        
        # Update event
        event.event_name = event_name
        event.event_date = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        event.location = location or "Onbekende locatie"
        
        db.session.commit()
        
        flash(f"Event '{event_name}' is succesvol bijgewerkt.", "success")
    except Exception as exc:
        print(f"WARNING: Event update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van event.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.dashboard"))

@main.route("/events/delete", methods=["POST"])
@login_required
def delete_event():
    """Verwijder een event"""
    try:
        event_number = request.form.get("event_number", "").strip()
        
        if not event_number:
            flash("Event nummer ontbreekt.", "error")
            return redirect(url_for("main.dashboard"))
        
        try:
            event_number = int(event_number)
        except (ValueError, TypeError):
            flash("Ongeldig event nummer.", "error")
            return redirect(url_for("main.dashboard"))
        
        # Find and delete event
        event = db.session.query(Event).filter(Event.event_number == event_number).first()
        
        if not event:
            flash("Event niet gevonden.", "error")
            return redirect(url_for("main.dashboard"))
        
        event_name = event.event_name or 'Onbekend'
        
        # Delete the event
        db.session.delete(event)
        db.session.commit()
        
        flash(f"Event '{event_name}' is succesvol verwijderd.", "success")
    except Exception as exc:
        print(f"WARNING: Event deletion failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij verwijderen van event.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.dashboard"))


# --- Agenda / Events: iCal export routes ---

@main.route("/events/<int:event_id>/ical")
@login_required
def export_single_event_ical(event_id):
    """
    Genereer een RFC5545-compliant .ics-bestand voor één event.
    SUMMARY, DTSTART, DTEND (+1u), LOCATION en DESCRIPTION worden gevuld.
    """
    from icalendar import Calendar, Event as ICalEvent

    tz = pytz.timezone("Europe/Brussels")

    event = db.session.get(Event, event_id)
    if not event:
        flash("Event niet gevonden voor iCal-export.", "error")
        return redirect(url_for("main.dashboard"))

    event_dt = event.event_date or datetime.now(tz)
    if event_dt.tzinfo is None:
        event_dt = tz.localize(event_dt)
    else:
        event_dt = event_dt.astimezone(tz)

    cal = Calendar()
    cal.add("prodid", "-//VIC Agenda//NL")
    cal.add("version", "2.0")

    ical_event = ICalEvent()
    ical_event.add("uid", f"event-{event.event_number}@vic-app")
    ical_event.add("summary", event.event_name)
    ical_event.add("dtstart", event_dt)
    ical_event.add("dtend", event_dt + timedelta(hours=1))
    ical_event.add("location", event.location or "Onbekende locatie")
    ical_event.add("description", "Event gegenereerd via de applicatie")

    cal.add_component(ical_event)

    ics_bytes = cal.to_ical()
    resp = Response(ics_bytes, mimetype="text/calendar")
    resp.headers["Content-Disposition"] = f"attachment; filename=event_{event.event_number}.ics"
    return resp


@main.route("/events/export/all")
@login_required
def export_all_events_ical():
    """
    Genereer één .ics-bestand met alle events in de database (of Supabase fallback).
    De events worden in een enkele agenda gegroepeerd.
    """
    from icalendar import Calendar, Event as ICalEvent

    tz = pytz.timezone("Europe/Brussels")

    cal = Calendar()
    cal.add("prodid", "-//VIC Agenda Alle Events//NL")
    cal.add("version", "2.0")

    # Gebruik primair de Event-tabel
    events = db.session.query(Event).order_by(Event.event_date.asc()).all()

    # Als er geen events zijn, kunnen we optioneel mock/Supabase gebruiken,
    # maar meestal zal de tabel gevuld zijn via add_event().
    if not events and supabase is not None:
        try:
            response = supabase.table("events").select("*").order("event_date", desc=False).execute()
            for row in (response.data or []):
                name = row.get("event_name", "Onbekend event")
                event_date_str = row.get("event_date")
                location = row.get("location", "Onbekende locatie")

                if event_date_str:
                    try:
                        dt = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                    except Exception:
                        dt = datetime.now()
                else:
                    dt = datetime.now()

                if dt.tzinfo is None:
                    dt = tz.localize(dt)
                else:
                    dt = dt.astimezone(tz)

                ical_event = ICalEvent()
                ical_event.add("uid", f"event-supabase-{name}@vic-app")
                ical_event.add("summary", name)
                ical_event.add("dtstart", dt)
                ical_event.add("dtend", dt + timedelta(hours=1))
                ical_event.add("location", location)
                ical_event.add("description", "Event gegenereerd via de applicatie (Supabase fallback)")
                cal.add_component(ical_event)
        except Exception as exc:
            print(f"WARNING: Supabase fetch for iCal all-events failed: {exc}")
    else:
        for event in events:
            event_dt = event.event_date or datetime.now(tz)
            if event_dt.tzinfo is None:
                event_dt = tz.localize(event_dt)
            else:
                event_dt = event_dt.astimezone(tz)

            ical_event = ICalEvent()
            ical_event.add("uid", f"event-{event.event_number}@vic-app")
            ical_event.add("summary", event.event_name)
            ical_event.add("dtstart", event_dt)
            ical_event.add("dtend", event_dt + timedelta(hours=1))
            ical_event.add("location", event.location or "Onbekende locatie")
            ical_event.add("description", "Event gegenereerd via de applicatie")
            cal.add_component(ical_event)

    ics_bytes = cal.to_ical()
    resp = Response(ics_bytes, mimetype="text/calendar")
    resp.headers["Content-Disposition"] = "attachment; filename=agenda.ics"
    return resp

# Portfolio pagina
@main.route("/portfolio")
@login_required 
def portfolio():
    try:
        # Haal centrale portfolio op
        central_portfolio = db.session.query(Portfolio).first()
        
        # Haal cash op uit positions tabel (pos_id = 0)
        cash_position = db.session.query(Position).filter(Position.pos_id == 0).first()
        cash_amount = MOCK_CASH_AMOUNT
        if cash_position and cash_position.pos_value is not None:
            cash_amount = float(cash_position.pos_value)
        
        # Haal alle positions op (met of zonder portfolio), maar EXCLUDE pos_id = 0 (cash)
        if central_portfolio:
            positions = db.session.query(Position).filter(
                Position.portfolio_id == central_portfolio.portfolio_id,
                Position.pos_id != 0  # Exclude cash position
            ).all()
        else:
            positions = []
        
        # Als er geen positions zijn gekoppeld, probeer alle positions (exclude cash)
        if not positions:
            positions = db.session.query(Position).filter(Position.pos_id != 0).all()
        
        # Als er nog steeds geen positions zijn, gebruik mock data als fallback
        if not positions:
            total_market_value = sum(p['market_value'] for p in MOCK_POSITIONS)
            total_unrealized_gain = sum(p['unrealizedGain'] for p in MOCK_POSITIONS)
            portfolio_value = cash_amount + total_market_value  # Portfolio Value = Cash + Position Value
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
                cash_amount=format_currency(cash_amount),
                cash_amount_raw=cash_amount,
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
                'pos_id': p.pos_id,  # Add pos_id for deletion functionality
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
        
        # Haal cash bedrag op uit positions tabel (pos_id = 0)
        cash_position = db.session.query(Position).filter(Position.pos_id == 0).first()
        cash_amount = MOCK_CASH_AMOUNT
        if cash_position and cash_position.pos_value is not None:
            cash_amount = float(cash_position.pos_value)
        
        portfolio_value = cash_amount + total_market_value  # Portfolio Value = Cash + Position Value
        
        # Bereken weight voor elke positie (op basis van portfolio_value, niet alleen market_value)
        for p_data in portfolio_data_formatted:
            weight = (p_data['market_value'] / portfolio_value) * 100 if portfolio_value > 0 else 0
            p_data['weight'] = format_currency(weight)
            p_data['market_value'] = format_currency(p_data['market_value'])
        
    except Exception:
        # Fallback naar mock data
        # Probeer eerst cash uit database te halen (pos_id = 0)
        try:
            cash_position = db.session.query(Position).filter(Position.pos_id == 0).first()
            cash_amount = float(cash_position.pos_value) if cash_position and cash_position.pos_value is not None else MOCK_CASH_AMOUNT
        except:
            cash_amount = MOCK_CASH_AMOUNT
        
        total_market_value = sum(p['market_value'] for p in MOCK_POSITIONS)
        total_unrealized_gain = sum(p['unrealizedGain'] for p in MOCK_POSITIONS)
        portfolio_value = cash_amount + total_market_value  # Portfolio Value = Cash + Position Value
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
        cash_amount=format_currency(cash_amount),
        cash_amount_raw=cash_amount,
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
    """Voting pagina met openstaande votingen en resultaten"""
    tz = pytz.timezone("Europe/Brussels")
    now = datetime.now(tz)
    
    # Haal alle voting proposals op
    proposals = db.session.query(VotingProposal).order_by(VotingProposal.deadline.desc()).all()
    
    open_votes = []
    results = []
    user_id = g.user.member_id if g.user else None
    
    for proposal in proposals:
        # Check of deadline verstreken is
        deadline = proposal.deadline
        if deadline.tzinfo is None:
            deadline = tz.localize(deadline)
        else:
            deadline = deadline.astimezone(tz)
        
        is_pending = deadline > now
        
        # Haal stemmen op voor dit proposal
        votes = db.session.query(Vote).filter(Vote.proposal_id == proposal.proposal_id).all()
        
        # Tel stemmen
        for_votes = sum(1 for v in votes if v.vote_option == 'voor')
        against_votes = sum(1 for v in votes if v.vote_option == 'tegen')
        abstain_votes = sum(1 for v in votes if v.vote_option == 'onthouding')
        total_votes = len(votes)
        
        # Check of gebruiker al gestemd heeft
        user_voted = False
        if user_id:
            user_vote = db.session.query(Vote).filter(
                Vote.proposal_id == proposal.proposal_id,
                Vote.member_id == user_id
            ).first()
            user_voted = user_vote is not None
        
        proposal_data = {
            'proposal_id': proposal.proposal_id,
            'title': proposal.proposal_type or 'Onbekend',
            'stock_name': proposal.stock_name or 'Stock XYZ',
            'deadline': deadline.strftime('%d/%m/%Y'),
            'deadline_datetime': deadline,
            'for_votes': for_votes,
            'against_votes': against_votes,
            'abstain_votes': abstain_votes,
            'total_votes': total_votes,
            'is_pending': is_pending,
            'user_voted': user_voted
        }
        
        if is_pending:
            open_votes.append(proposal_data)
        else:
            results.append(proposal_data)
    
    return render_template("voting.html", open_votes=open_votes, results=results)

# Deelnemers pagina
@main.route("/deelnemers")
@login_required
def deelnemers():
    # Haal alle members op en filter op basis van rol
    try:
        all_members = db.session.query(Member).all()
        
        def get_first_three_digits(member_id):
            """Haal eerste 3 cijfers van ID op voor sortering"""
            id_str = str(member_id).zfill(6)
            return int(id_str[:3]) if len(id_str) >= 3 else 0
        
        def get_last_three_digits(member_id):
            """Haal laatste 3 cijfers van ID op (jaar) voor sortering"""
            id_str = str(member_id).zfill(6)
            return int(id_str[-3:]) if len(id_str) >= 3 else 0
        
        def sort_members(members_list):
            """Sorteer members: eerst op eerste 3 cijfers, dan op laatste 3 cijfers (jaar)"""
            return sorted(members_list, key=lambda m: (get_first_three_digits(m.member_id), get_last_three_digits(m.member_id)))
        
        # Categoriseer members op basis van ID nummer
        admin_members = []
        board_members = []
        analisten = []
        leden = []
        kapitaalverschaffers = []
        oud_bestuur_analisten = []
        
        for m in all_members:
            id_str = str(m.member_id).zfill(6)
            first_digit = int(id_str[0]) if len(id_str) > 0 else 0
            first_two_digits = int(id_str[:2]) if len(id_str) >= 2 else 0
            first_five_digits = int(id_str[:5]) if len(id_str) >= 5 else 0
            
            # Admin: begint met 5 nullen (00000x)
            if first_five_digits == 0 and len(id_str) == 6:
                admin_members.append(m)
            # Bestuur: begint met 00 en dan een getal (00xxxx, maar niet 00000x)
            elif first_two_digits == 0 and first_five_digits != 0:
                board_members.append(m)
            # Analist: begint met 1
            elif first_digit == 1:
                analisten.append(m)
            # Leden: begint met 2
            elif first_digit == 2:
                leden.append(m)
            # Kapitaalverschaffer: begint met 3
            elif first_digit == 3:
                kapitaalverschaffers.append(m)
            # Oud bestuur: begint met 4
            elif first_digit == 4:
                oud_bestuur_analisten.append(m)
            # Fallback: gebruik get_role() methode
            else:
                role = m.get_role()
                if role == 'board':
                    board_members.append(m)
                elif role == 'analist':
                    analisten.append(m)
                elif role == 'lid':
                    leden.append(m)
                elif role == 'kapitaalverschaffers':
                    kapitaalverschaffers.append(m)
                elif role == 'oud_bestuur_analisten':
                    oud_bestuur_analisten.append(m)
        
        # Sorteer alle lijsten
        admin_members = sort_members(admin_members)
        board_members = sort_members(board_members)
        analisten = sort_members(analisten)
        leden = sort_members(leden)
        kapitaalverschaffers = sort_members(kapitaalverschaffers)
        oud_bestuur_analisten = sort_members(oud_bestuur_analisten)
        
    except Exception as exc:
        print(f"WARNING: Database fetch failed: {exc}")
        import traceback
        traceback.print_exc()
        all_members = []
        admin_members = []
        board_members = []
        analisten = []
        leden = []
        kapitaalverschaffers = []
        oud_bestuur_analisten = []
    
    return render_template(
        "deelnemers.html",
        members=leden,  # Leden worden als 'members' doorgegeven voor backward compatibility
        admin_members=admin_members,  # Admin members voor Site-Admin sectie
        board_members=board_members,
        analisten=analisten,
        kapitaalverschaffers=kapitaalverschaffers,
        oud_bestuur_analisten=oud_bestuur_analisten,
        all_members=all_members  # Voor eventuele andere doeleinden
    )

@main.route("/deelnemers/add", methods=["POST"])
@login_required
def add_member():
    """Voeg een nieuwe deelnemer toe"""
    try:
        member_id = request.form.get("member_id", "").strip()
        member_name = request.form.get("member_name", "").strip()
        password = request.form.get("password", "").strip()
        email = request.form.get("email", "").strip() or None
        voting_right = request.form.get("voting_right", "").strip() or None
        sector = request.form.get("sector", "").strip() or None
        join_date = request.form.get("join_date", "").strip()
        
        if not member_id or not member_name or not password:
            flash("ID nummer, naam en wachtwoord zijn verplicht.", "error")
            return redirect(url_for("main.deelnemers"))
        
        member_id_int = int(member_id)
        
        # Check of ID al bestaat
        existing = db.session.query(Member).filter_by(member_id=member_id_int).first()
        if existing:
            flash(f"ID nummer {member_id_int:06d} bestaat al. Kies een uniek ID nummer.", "error")
            return redirect(url_for("main.deelnemers"))
        
        # Check of email al bestaat (als email is opgegeven)
        if email:
            existing_email = db.session.query(Member).filter_by(email=email).first()
            if existing_email:
                flash(f"Email {email} is al in gebruik.", "error")
                return redirect(url_for("main.deelnemers"))
        
        # Maak nieuwe member
        member = Member(
            member_id=member_id_int,
            member_name=member_name,
            email=email,
            voting_right=voting_right,
            sector=sector,
            join_date=int(join_date) if join_date else datetime.now().year
        )
        member.set_password(password)
        
        db.session.add(member)
        db.session.commit()
        
        flash(f"Deelnemer {member_name} (ID: {member_id_int:06d}) is toegevoegd.", "success")
    except ValueError:
        flash("Ongeldig ID nummer of startjaar.", "error")
    except Exception as exc:
        db.session.rollback()
        print(f"ERROR: Failed to add member: {exc}")
        flash("Er is een fout opgetreden bij het toevoegen van de deelnemer.", "error")
    
    return redirect(url_for("main.deelnemers"))

@main.route("/deelnemers/get-member/<int:member_id>")
@login_required
def get_member(member_id):
    """Haal een deelnemer op voor edit/delete"""
    try:
        member = db.session.query(Member).filter_by(member_id=member_id).first()
        if not member:
            return jsonify({"error": f"Deelnemer met ID {member_id:06d} niet gevonden."}), 404
        
        return jsonify({
            "member_id": member.member_id,
            "member_name": member.member_name or "",
            "email": member.email or "",
            "voting_right": member.voting_right or "",
            "sector": member.sector or "",
            "join_date": member.join_date or member.get_year() or datetime.now().year,
            "tel": "",  # Tel en studie zijn niet in het model, maar we geven lege strings terug
            "studie": ""
        })
    except Exception as exc:
        print(f"ERROR: Failed to get member: {exc}")
        return jsonify({"error": "Er is een fout opgetreden bij het ophalen van de deelnemer."}), 500

@main.route("/deelnemers/update", methods=["POST"])
@login_required
def update_member():
    """Update een deelnemer"""
    try:
        member_id = int(request.form.get("member_id", "").strip())
        member_name = request.form.get("member_name", "").strip()
        password = request.form.get("password", "").strip()
        email = request.form.get("email", "").strip() or None
        voting_right = request.form.get("voting_right", "").strip() or None
        sector = request.form.get("sector", "").strip() or None
        join_date = request.form.get("join_date", "").strip()
        
        if not member_name:
            flash("Naam is verplicht.", "error")
            return redirect(url_for("main.deelnemers"))
        
        member = db.session.query(Member).filter_by(member_id=member_id).first()
        if not member:
            flash(f"Deelnemer met ID {member_id:06d} niet gevonden.", "error")
            return redirect(url_for("main.deelnemers"))
        
        # Update velden
        member.member_name = member_name
        if password:
            member.set_password(password)
        member.voting_right = voting_right
        member.sector = sector
        if join_date:
            member.join_date = int(join_date)
        
        # Check email uniekheid (als email is opgegeven en gewijzigd)
        if email and email != member.email:
            existing_email = db.session.query(Member).filter_by(email=email).first()
            if existing_email:
                flash(f"Email {email} is al in gebruik door een andere deelnemer.", "error")
                return redirect(url_for("main.deelnemers"))
            member.email = email
        elif not email:
            member.email = None
        
        db.session.commit()
        
        flash(f"Deelnemer {member_name} (ID: {member_id:06d}) is bijgewerkt.", "success")
    except ValueError:
        flash("Ongeldig ID nummer of startjaar.", "error")
    except Exception as exc:
        db.session.rollback()
        print(f"ERROR: Failed to update member: {exc}")
        flash("Er is een fout opgetreden bij het bijwerken van de deelnemer.", "error")
    
    return redirect(url_for("main.deelnemers"))

@main.route("/deelnemers/delete", methods=["POST"])
@login_required
def delete_member():
    """Verwijder een deelnemer"""
    try:
        member_id = int(request.form.get("member_id", "").strip())
        
        member = db.session.query(Member).filter_by(member_id=member_id).first()
        if not member:
            flash(f"Deelnemer met ID {member_id:06d} niet gevonden.", "error")
            return redirect(url_for("main.deelnemers"))
        
        member_name = member.member_name or "Onbekend"
        
        db.session.delete(member)
        db.session.commit()
        
        flash(f"Deelnemer {member_name} (ID: {member_id:06d}) is verwijderd.", "success")
    except ValueError:
        flash("Ongeldig ID nummer.", "error")
    except Exception as exc:
        db.session.rollback()
        print(f"ERROR: Failed to delete member: {exc}")
        flash("Er is een fout opgetreden bij het verwijderen van de deelnemer.", "error")
    
    return redirect(url_for("main.deelnemers"))

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

# Portfolio: Cash bedrag bijwerken
@main.route("/portfolio/update-cash", methods=["POST"])
@login_required
def update_cash():
    cash_amount_str = request.form.get("cash_amount", "").strip()
    
    if not cash_amount_str:
        flash("Cash bedrag is verplicht.", "error")
        return redirect(url_for("main.portfolio"))
    
    try:
        cash_amount = float(cash_amount_str)
        if cash_amount < 0:
            flash("Cash bedrag moet positief zijn.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Haal cash position op (pos_id = 0) of maak aan
        cash_position = db.session.query(Position).filter(Position.pos_id == 0).first()
        
        # Eerst portfolio ophalen of aanmaken (nodig voor portfolio_id)
        central_portfolio = db.session.query(Portfolio).first()
        if not central_portfolio:
            central_portfolio = Portfolio()
            db.session.add(central_portfolio)
            db.session.flush()
        
        if not cash_position:
            # Maak nieuwe cash position aan met pos_id = 0 via direct SQL
            # (omdat autoincrement normaal niet toestaat om pos_id = 0 handmatig in te stellen)
            from sqlalchemy import text
            try:
                db.session.execute(
                    text("""
                        INSERT INTO positions (pos_id, pos_name, pos_type, pos_quantity, pos_value, pos_ticker, pos_sector, portfolio_id)
                        VALUES (0, 'CASH', 'Cash', 1, :cash, 'CASH', 'Cash', :portfolio_id)
                    """),
                    {"cash": cash_amount, "portfolio_id": central_portfolio.portfolio_id}
                )
                db.session.commit()
            except Exception as insert_exc:
                # Als insert faalt (bijv. pos_id = 0 bestaat al), probeer update
                print(f"Insert failed, trying update: {insert_exc}")
                db.session.rollback()
                db.session.execute(
                    text("UPDATE positions SET pos_value = :cash WHERE pos_id = 0"),
                    {"cash": cash_amount}
                )
                db.session.commit()
        else:
            # Update bestaande cash position
            cash_position.pos_value = cash_amount
            db.session.commit()
        
        flash(f"Cash bedrag bijgewerkt naar € {format_currency(cash_amount)}.", "success")
        
    except Exception as exc:
        print(f"WARNING: Cash update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van cash bedrag.", "error")
        db.session.rollback()
    except (ValueError, TypeError):
        flash("Cash bedrag moet een geldig getal zijn.", "error")
    
    return redirect(url_for("main.portfolio"))

# Portfolio: Get position by number (for deletion)
@main.route("/portfolio/get-position/<int:position_number>")
@login_required
def get_position_by_number(position_number):
    """Haal positie op op basis van het nummer in de tabel (1-based index)"""
    try:
        # Haal alle positions op (exclude cash, pos_id = 0)
        positions = db.session.query(Position).filter(Position.pos_id != 0).order_by(Position.pos_id).all()
        
        if not positions:
            return jsonify({'error': 'Geen posities gevonden.'}), 404
        
        # Check if position_number is valid (1-based index)
        if position_number < 1 or position_number > len(positions):
            return jsonify({'error': f'Ongeldig positie nummer. Kies een nummer tussen 1 en {len(positions)}.'}), 404
        
        # Get position at index (position_number - 1 because it's 1-based)
        position = positions[position_number - 1]
        
        return jsonify({
            'position_id': position.pos_id,
            'position_name': position.pos_name or 'Onbekend',
            'ticker': position.pos_ticker or 'N/A'
        })
    except Exception as e:
        print(f"Error fetching position: {e}")
        return jsonify({'error': 'Fout bij ophalen van positie informatie.'}), 500

# Portfolio: Get position details for editing
@main.route("/portfolio/get-position-details/<int:position_id>")
@login_required
def get_position_details(position_id):
    """Haal volledige positie details op voor editing"""
    try:
        position = db.session.query(Position).filter(Position.pos_id == position_id).first()
        
        if not position:
            return jsonify({'error': 'Positie niet gevonden.'}), 404
        
        # Prevent editing cash position (pos_id = 0)
        if position_id == 0:
            return jsonify({'error': 'Cash positie kan niet bewerkt worden.'}), 400
        
        return jsonify({
            'position_id': position.pos_id,
            'pos_name': position.pos_name or '',
            'pos_ticker': position.pos_ticker or '',
            'pos_sector': position.pos_sector or '',
            'pos_type': position.pos_type or '',
            'pos_quantity': position.pos_quantity or 0,
            'pos_value': float(position.pos_value) if position.pos_value else 0.0
        })
    except Exception as e:
        print(f"Error fetching position details: {e}")
        return jsonify({'error': 'Fout bij ophalen van positie details.'}), 500

# Portfolio: Update position
@main.route("/portfolio/update-position", methods=["POST"])
@login_required
def update_position():
    """Update een positie in het portfolio"""
    try:
        position_id = request.form.get("position_id", "").strip()
        
        if not position_id:
            flash("Positie ID ontbreekt.", "error")
            return redirect(url_for("main.portfolio"))
        
        try:
            position_id = int(position_id)
        except (ValueError, TypeError):
            flash("Ongeldig positie ID.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Prevent editing cash position (pos_id = 0)
        if position_id == 0:
            flash("Cash positie kan niet bewerkt worden.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Find position
        position = db.session.query(Position).filter(Position.pos_id == position_id).first()
        
        if not position:
            flash("Positie niet gevonden.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Get form data
        pos_name = request.form.get("pos_name", "").strip()
        pos_ticker = request.form.get("pos_ticker", "").strip()
        pos_sector = request.form.get("pos_sector", "").strip()
        pos_type = request.form.get("pos_type", "").strip()
        pos_quantity_str = request.form.get("pos_quantity", "").strip()
        pos_value_str = request.form.get("pos_value", "").strip()
        
        # Validate required fields
        if not pos_name or not pos_ticker or not pos_sector or not pos_type:
            flash("Alle verplichte velden moeten ingevuld zijn.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Parse quantity
        try:
            pos_quantity = int(pos_quantity_str)
            if pos_quantity < 1:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            flash("Ongeldige hoeveelheid.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Parse avg buy price and calculate total pos_value
        try:
            avg_buy_price = float(pos_value_str.replace(',', '.'))
            if avg_buy_price < 0:
                raise ValueError("Price must be non-negative")
            # Calculate total pos_value (avg buy price * quantity)
            pos_value = avg_buy_price * pos_quantity
        except (ValueError, TypeError):
            flash("Ongeldige gemiddelde aankoopprijs.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Update position
        position.pos_name = pos_name
        position.pos_ticker = pos_ticker
        position.pos_sector = pos_sector
        position.pos_type = pos_type
        position.pos_quantity = pos_quantity
        position.pos_value = pos_value
        
        db.session.commit()
        
        flash(f"Positie '{pos_name}' is succesvol bijgewerkt.", "success")
    except Exception as exc:
        print(f"WARNING: Position update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van positie.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.portfolio"))

# Portfolio: Delete position
@main.route("/portfolio/delete-position", methods=["POST"])
@login_required
def delete_position():
    """Verwijder een positie uit het portfolio"""
    try:
        position_id = request.form.get("position_id", "").strip()
        
        if not position_id:
            flash("Positie ID ontbreekt.", "error")
            return redirect(url_for("main.portfolio"))
        
        try:
            position_id = int(position_id)
        except (ValueError, TypeError):
            flash("Ongeldig positie ID.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Prevent deletion of cash position (pos_id = 0)
        if position_id == 0:
            flash("Cash positie kan niet verwijderd worden.", "error")
            return redirect(url_for("main.portfolio"))
        
        # Find and delete position
        position = db.session.query(Position).filter(Position.pos_id == position_id).first()
        
        if not position:
            flash("Positie niet gevonden.", "error")
            return redirect(url_for("main.portfolio"))
        
        position_name = position.pos_name or 'Onbekend'
        
        # Delete the position
        db.session.delete(position)
        db.session.commit()
        
        flash(f"Positie '{position_name}' is succesvol verwijderd.", "success")
    except Exception as exc:
        print(f"WARNING: Position deletion failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij verwijderen van positie.", "error")
        db.session.rollback()
    
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

# Transactions: Get transaction by number (for deletion/editing)
@main.route("/transactions/get-transaction/<int:transaction_number>")
@login_required
def get_transaction_by_number(transaction_number):
    """Haal transactie op op basis van het nummer in de tabel (1-based index)"""
    try:
        # Haal transacties direct uit de database in dezelfde volgorde als getoond
        try:
            db_transactions = db.session.query(Transaction).order_by(Transaction.transaction_date.asc()).all()
        except Exception as db_exc:
            print(f"Warning: Could not fetch from database: {db_exc}")
            db_transactions = []
        
        if not db_transactions:
            # Fallback naar genormaliseerde transacties
            transactions = _fetch_transactions()
            if not transactions:
                return jsonify({'error': 'Geen transacties gevonden.'}), 404
            
            if transaction_number < 1 or transaction_number > len(transactions):
                return jsonify({'error': f'Ongeldig transactie nummer. Kies een nummer tussen 1 en {len(transactions)}.'}), 404
            
            transaction = transactions[transaction_number - 1]
            transaction_id = transaction.get('transaction_id') or transaction.get('number')
            
            if not transaction_id:
                return jsonify({'error': 'Transactie ID niet gevonden.'}), 500
            
            return jsonify({
                'transaction_id': transaction_id,
                'transaction_name': transaction.get('asset_name') or transaction.get('asset') or 'Onbekend',
                'ticker': transaction.get('ticker') or 'N/A'
            })
        
        # Check if transaction_number is valid (1-based index)
        if transaction_number < 1 or transaction_number > len(db_transactions):
            return jsonify({'error': f'Ongeldig transactie nummer. Kies een nummer tussen 1 en {len(db_transactions)}.'}), 404
        
        # Get transaction at index (transaction_number - 1 because it's 1-based)
        db_transaction = db_transactions[transaction_number - 1]
        
        # Get asset name from asset_type or ticker
        asset_name = db_transaction.asset_type or db_transaction.transaction_ticker or 'Onbekend'
        
        return jsonify({
            'transaction_id': db_transaction.transaction_id,
            'transaction_name': asset_name,
            'ticker': db_transaction.transaction_ticker or 'N/A'
        })
    except Exception as e:
        print(f"Error fetching transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Fout bij ophalen van transactie informatie.'}), 500

# Transactions: Get transaction details for editing
@main.route("/transactions/get-transaction-details/<int:transaction_id>")
@login_required
def get_transaction_details(transaction_id):
    """Haal volledige transactie details op voor editing"""
    try:
        transaction = db.session.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        
        if not transaction:
            return jsonify({'error': 'Transactie niet gevonden.'}), 404
        
        # Format date as dd/mm/yyyy
        date_str = ''
        if transaction.transaction_date:
            if isinstance(transaction.transaction_date, str):
                date_str = transaction.transaction_date
            else:
                date_str = transaction.transaction_date.strftime("%d/%m/%Y")
        
        # Get asset_name from asset_type or construct from ticker
        asset_name = transaction.asset_type or transaction.transaction_ticker or ''
        
        return jsonify({
            'transaction_id': transaction.transaction_id,
            'transaction_date': date_str,
            'transaction_type': transaction.transaction_type or '',
            'asset_name': asset_name,
            'transaction_ticker': transaction.transaction_ticker or '',
            'transaction_quantity': float(transaction.transaction_quantity) if transaction.transaction_quantity else 0.0,
            'transaction_share_price': float(transaction.transaction_share_price) if transaction.transaction_share_price else 0.0,
            'transaction_currency': transaction.transaction_currency or 'EUR',
            'asset_class': transaction.asset_class or transaction.asset_type or 'Stock',
            'sector': transaction.sector or ''
        })
    except Exception as e:
        print(f"Error fetching transaction details: {e}")
        return jsonify({'error': 'Fout bij ophalen van transactie details.'}), 500

# Transactions: Update transaction
@main.route("/transactions/update-transaction", methods=["POST"])
@login_required
def update_transaction():
    """Update een transactie"""
    try:
        transaction_id = request.form.get("transaction_id", "").strip()
        
        if not transaction_id:
            flash("Transactie ID ontbreekt.", "error")
            return redirect(url_for("main.transactions"))
        
        try:
            transaction_id = int(transaction_id)
        except (ValueError, TypeError):
            flash("Ongeldig transactie ID.", "error")
            return redirect(url_for("main.transactions"))
        
        # Find transaction
        transaction = db.session.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        
        if not transaction:
            flash("Transactie niet gevonden.", "error")
            return redirect(url_for("main.transactions"))
        
        # Get form data
        transaction_date = request.form.get("transaction_date", "").strip()
        transaction_type = request.form.get("transaction_type", "").strip()
        asset_name = request.form.get("asset_name", "").strip()
        transaction_ticker = request.form.get("transaction_ticker", "").strip()
        transaction_quantity_str = request.form.get("transaction_quantity", "").strip()
        transaction_share_price_str = request.form.get("transaction_share_price", "").strip()
        transaction_currency = request.form.get("transaction_currency", "EUR").strip()
        asset_class = request.form.get("asset_class", "Stock").strip()
        sector = request.form.get("sector", "").strip()
        
        # Validate required fields
        if not transaction_date or not transaction_type or not asset_name or not transaction_ticker:
            flash("Alle verplichte velden moeten ingevuld zijn.", "error")
            return redirect(url_for("main.transactions"))
        
        # Parse date
        parsed_date = None
        for date_format in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
            try:
                parsed_date = datetime.strptime(transaction_date, date_format)
                break
            except ValueError:
                continue
        if not parsed_date:
            parsed_date = datetime.now()
        
        # Parse quantity and price
        try:
            quantity = float(transaction_quantity_str)
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            flash("Ongeldige hoeveelheid.", "error")
            return redirect(url_for("main.transactions"))
        
        try:
            share_price = float(transaction_share_price_str)
            if share_price <= 0:
                raise ValueError("Price must be positive")
        except (ValueError, TypeError):
            flash("Ongeldige prijs per aandeel.", "error")
            return redirect(url_for("main.transactions"))
        
        # Calculate total amount
        transaction_amount = quantity * share_price
        
        # Update transaction
        transaction.transaction_date = parsed_date
        transaction.transaction_type = transaction_type.upper()
        transaction.transaction_ticker = transaction_ticker
        transaction.transaction_quantity = quantity
        transaction.transaction_share_price = share_price
        transaction.transaction_amount = transaction_amount
        transaction.transaction_currency = transaction_currency.upper()
        transaction.asset_type = asset_class
        transaction.asset_class = asset_class
        transaction.sector = sector if sector else None
        
        db.session.commit()
        
        flash(f"Transactie is succesvol bijgewerkt.", "success")
    except Exception as exc:
        print(f"WARNING: Transaction update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van transactie.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.transactions"))

# Transactions: Delete transaction
@main.route("/transactions/delete-transaction", methods=["POST"])
@login_required
def delete_transaction():
    """Verwijder een transactie"""
    try:
        transaction_id = request.form.get("transaction_id", "").strip()
        
        if not transaction_id:
            flash("Transactie ID ontbreekt.", "error")
            return redirect(url_for("main.transactions"))
        
        try:
            transaction_id = int(transaction_id)
        except (ValueError, TypeError):
            flash("Ongeldig transactie ID.", "error")
            return redirect(url_for("main.transactions"))
        
        # Find and delete transaction
        transaction = db.session.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        
        if not transaction:
            flash("Transactie niet gevonden.", "error")
            return redirect(url_for("main.transactions"))
        
        # Delete the transaction
        db.session.delete(transaction)
        db.session.commit()
        
        flash(f"Transactie is succesvol verwijderd.", "success")
    except Exception as exc:
        print(f"WARNING: Transaction deletion failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij verwijderen van transactie.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.transactions"))

# Voting: Stemming toevoegen
@main.route("/voting/add", methods=["POST"])
@login_required
def add_voting_proposal():
    proposal_type = request.form.get("proposal_type", "").strip()
    stock_name = request.form.get("stock_name", "").strip()
    deadline_date = request.form.get("deadline_date", "").strip()
    minimum_requirements = request.form.get("minimum_requirements", "").strip()
    
    if not proposal_type:
        flash("Proposal type is verplicht.", "error")
        return redirect(url_for("main.voting"))
    
    if not stock_name:
        flash("Stock naam is verplicht.", "error")
        return redirect(url_for("main.voting"))
    
    if not deadline_date:
        flash("Deadline is verplicht.", "error")
        return redirect(url_for("main.voting"))
    
    try:
        # Parse deadline (dd/mm/yyyy format)
        tz = pytz.timezone("Europe/Brussels")
        deadline_dt = datetime.strptime(deadline_date, "%d/%m/%Y")
        deadline_dt = tz.localize(deadline_dt.replace(hour=23, minute=59, second=59))
        
        proposal = VotingProposal(
            proposal_type=proposal_type,
            stock_name=stock_name,
            deadline=deadline_dt,
            minimum_requirements=minimum_requirements or None
        )
        db.session.add(proposal)
        db.session.commit()
        flash(f"Stemming '{proposal_type}' toegevoegd.", "success")
    except ValueError:
        flash("Ongeldige deadline datum. Gebruik formaat dd/mm/yyyy.", "error")
    except Exception as exc:
        print(f"ERROR: Voting proposal insert failed: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij toevoegen van stemming.", "error")
    
    return redirect(url_for("main.voting"))

# Voting: Get all proposals for dropdown
@main.route("/voting/get-all")
@login_required
def get_all_voting_proposals():
    """Haal voting proposals op voor dropdown selectie"""
    try:
        include_closed = request.args.get('include_closed', 'false').lower() == 'true'
        only_closed = request.args.get('only_closed', 'false').lower() == 'true'  # Alleen resultaten
        tz = pytz.timezone("Europe/Brussels")
        now = datetime.now(tz)
        
        proposals = db.session.query(VotingProposal).order_by(VotingProposal.deadline.desc()).all()
        proposals_list = []
        
        for prop in proposals:
            deadline = prop.deadline
            if deadline.tzinfo is None:
                deadline = tz.localize(deadline)
            else:
                deadline = deadline.astimezone(tz)
            
            is_pending = deadline > now
            
            # Alleen resultaten (deadline verstreken)
            if only_closed:
                if is_pending:
                    continue  # Skip openstaande votingen
            # Alleen openstaande (deadline nog niet verstreken)
            elif not include_closed:
                if not is_pending:
                    continue  # Skip resultaten
            # include_closed=true: toon alles (zowel openstaande als resultaten)
            
            proposals_list.append({
                "proposal_id": prop.proposal_id,
                "proposal_type": prop.proposal_type or 'Onbekend',
                "stock_name": prop.stock_name or 'Stock XYZ',
                "deadline": deadline.strftime("%d/%m/%Y"),
                "display": f"{prop.proposal_type or 'Onbekend'} - {prop.stock_name or 'Stock XYZ'}"
            })
        return jsonify({"proposals": proposals_list})
    except Exception as e:
        print(f"Error fetching all voting proposals: {e}")
        return jsonify({"error": "Fout bij ophalen van voting proposals."}), 500

# Voting: Get proposal details for editing
@main.route("/voting/get-details/<int:proposal_id>")
@login_required
def get_voting_proposal_details(proposal_id):
    """Haal voting proposal details op voor editing"""
    try:
        proposal = db.session.query(VotingProposal).filter(VotingProposal.proposal_id == proposal_id).first()
        
        if not proposal:
            return jsonify({'error': 'Voting proposal niet gevonden.'}), 404
        
        deadline = proposal.deadline
        tz = pytz.timezone("Europe/Brussels")
        if deadline.tzinfo is None:
            deadline = tz.localize(deadline)
        else:
            deadline = deadline.astimezone(tz)
        
        return jsonify({
            'proposal_id': proposal.proposal_id,
            'proposal_type': proposal.proposal_type or '',
            'stock_name': proposal.stock_name or '',
            'deadline': deadline.strftime("%d/%m/%Y"),
            'minimum_requirements': proposal.minimum_requirements or ''
        })
    except Exception as e:
        print(f"Error fetching voting proposal details: {e}")
        return jsonify({'error': 'Fout bij ophalen van voting proposal details.'}), 500

# Voting: Update proposal
@main.route("/voting/update", methods=["POST"])
@login_required
def update_voting_proposal():
    """Update een voting proposal"""
    try:
        proposal_id = request.form.get("proposal_id", "").strip()
        
        if not proposal_id:
            flash("Proposal ID ontbreekt.", "error")
            return redirect(url_for("main.voting"))
        
        try:
            proposal_id = int(proposal_id)
        except (ValueError, TypeError):
            flash("Ongeldig proposal ID.", "error")
            return redirect(url_for("main.voting"))
        
        # Find proposal
        proposal = db.session.query(VotingProposal).filter(VotingProposal.proposal_id == proposal_id).first()
        
        if not proposal:
            flash("Voting proposal niet gevonden.", "error")
            return redirect(url_for("main.voting"))
        
        # Get form data
        proposal_type = request.form.get("proposal_type", "").strip()
        stock_name = request.form.get("stock_name", "").strip()
        deadline_date = request.form.get("deadline_date", "").strip()
        minimum_requirements = request.form.get("minimum_requirements", "").strip()
        
        # Validate required fields
        if not proposal_type:
            flash("Proposal type is verplicht.", "error")
            return redirect(url_for("main.voting"))
        
        if not stock_name:
            flash("Stock naam is verplicht.", "error")
            return redirect(url_for("main.voting"))
        
        if not deadline_date:
            flash("Deadline is verplicht.", "error")
            return redirect(url_for("main.voting"))
        
        # Parse deadline
        tz = pytz.timezone("Europe/Brussels")
        deadline_dt = datetime.strptime(deadline_date, "%d/%m/%Y")
        deadline_dt = tz.localize(deadline_dt.replace(hour=23, minute=59, second=59))
        
        # Update proposal
        proposal.proposal_type = proposal_type
        proposal.stock_name = stock_name
        proposal.deadline = deadline_dt
        proposal.minimum_requirements = minimum_requirements or None
        
        db.session.commit()
        
        flash(f"Voting proposal '{proposal_type}' is succesvol bijgewerkt.", "success")
    except ValueError:
        flash("Ongeldige deadline datum. Gebruik formaat dd/mm/yyyy.", "error")
    except Exception as exc:
        print(f"WARNING: Voting proposal update failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij bijwerken van voting proposal.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.voting"))

# Voting: Delete proposal
@main.route("/voting/delete", methods=["POST"])
@login_required
def delete_voting_proposal():
    """Verwijder een voting proposal"""
    try:
        proposal_id = request.form.get("proposal_id", "").strip()
        
        if not proposal_id:
            flash("Proposal ID ontbreekt.", "error")
            return redirect(url_for("main.voting"))
        
        try:
            proposal_id = int(proposal_id)
        except (ValueError, TypeError):
            flash("Ongeldig proposal ID.", "error")
            return redirect(url_for("main.voting"))
        
        # Find and delete proposal
        proposal = db.session.query(VotingProposal).filter(VotingProposal.proposal_id == proposal_id).first()
        
        if not proposal:
            flash("Voting proposal niet gevonden.", "error")
            return redirect(url_for("main.voting"))
        
        proposal_type = proposal.proposal_type or 'Onbekend'
        
        # Delete the proposal (cascade will delete votes)
        db.session.delete(proposal)
        db.session.commit()
        
        flash(f"Voting proposal '{proposal_type}' is succesvol verwijderd.", "success")
    except Exception as exc:
        print(f"WARNING: Voting proposal deletion failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij verwijderen van voting proposal.", "error")
        db.session.rollback()
    
    return redirect(url_for("main.voting"))

# Voting: Submit vote
@main.route("/voting/submit-vote", methods=["POST"])
@login_required
def submit_vote():
    """Stem op een voting proposal"""
    try:
        proposal_id = request.form.get("proposal_id", "").strip()
        vote_option = request.form.get("vote_option", "").strip()
        
        if not proposal_id or not vote_option:
            flash("Proposal ID en stem optie zijn verplicht.", "error")
            return redirect(url_for("main.voting"))
        
        if vote_option not in ['voor', 'tegen', 'onthouding']:
            flash("Ongeldige stem optie.", "error")
            return redirect(url_for("main.voting"))
        
        try:
            proposal_id = int(proposal_id)
        except (ValueError, TypeError):
            flash("Ongeldig proposal ID.", "error")
            return redirect(url_for("main.voting"))
        
        # Check if proposal exists and deadline not passed
        proposal = db.session.query(VotingProposal).filter(VotingProposal.proposal_id == proposal_id).first()
        if not proposal:
            flash("Voting proposal niet gevonden.", "error")
            return redirect(url_for("main.voting"))
        
        tz = pytz.timezone("Europe/Brussels")
        deadline = proposal.deadline
        if deadline.tzinfo is None:
            deadline = tz.localize(deadline)
        else:
            deadline = deadline.astimezone(tz)
        
        now = datetime.now(tz)
        if deadline <= now:
            flash("Deadline voor deze stemming is verstreken.", "error")
            return redirect(url_for("main.voting"))
        
        # Check if user already voted
        user_id = g.user.member_id
        existing_vote = db.session.query(Vote).filter(
            Vote.proposal_id == proposal_id,
            Vote.member_id == user_id
        ).first()
        
        if existing_vote:
            # Update existing vote
            existing_vote.vote_option = vote_option
            flash("Je stem is bijgewerkt.", "success")
        else:
            # Create new vote
            vote = Vote(
                proposal_id=proposal_id,
                member_id=user_id,
                vote_option=vote_option
            )
            db.session.add(vote)
            flash("Je stem is opgeslagen.", "success")
        
        db.session.commit()
    except Exception as exc:
        print(f"WARNING: Vote submission failed: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij opslaan van stem.", "error")
        db.session.rollback()
    
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

# Helper functie om bestandstype icoon te bepalen
def _get_file_icon(file_name):
    """Bepaal het icoon voor een bestand op basis van extensie"""
    if not file_name:
        return '📄'
    
    ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
    
    icon_map = {
        'doc': 'word',
        'docx': 'word',
        'xls': 'excel',
        'xlsx': 'excel',
        'ppt': 'powerpoint',
        'pptx': 'powerpoint',
        'pdf': 'pdf',
        'txt': 'text',
        'zip': 'zip',
        'rar': 'zip',
        'png': 'image',
        'jpg': 'image',
        'jpeg': 'image',
        'gif': 'image',
    }
    
    return icon_map.get(ext, 'default')

# Helper functie om alle folders recursief op te halen voor dropdown
def _get_all_folders(exclude_folder_id=None):
    """Haal alle folders recursief op en retourneer met pad informatie (skip VIC Leden)"""
    def is_vic_leden_folder(folder_name):
        """Check of een folder een 'VIC Leden' folder is die geskipt moet worden"""
        folder_name_lower = folder_name.lower()
        # Check voor "VIC Leden", "VIC leden", "C Leden", etc.
        return ('vic' in folder_name_lower and 'leden' in folder_name_lower) or folder_name_lower.startswith('c leden') or folder_name_lower == 'leden'
    
    def build_folder_tree(parent_id=None, prefix=""):
        folders = db.session.query(FileItem).filter(
            FileItem.item_type == 'folder',
            FileItem.parent_id == parent_id
        ).order_by(FileItem.name.asc()).all()
        
        result = []
        for folder in folders:
            if exclude_folder_id and folder.item_id == exclude_folder_id:
                continue
            
            # Check of dit een VIC Leden folder is
            is_vic_folder = is_vic_leden_folder(folder.name)
            
            # Als dit een VIC Leden folder is, skip de naam maar toon wel subfolders
            if is_vic_folder:
                # Skip deze folder - toon alleen subfolders zonder VIC Leden in pad
                subfolder_prefix = prefix  # Behoud huidige prefix (zonder VIC Leden)
            else:
                # Normale folder - voeg toe aan pad en lijst
                if prefix:
                    display_name = f"{prefix}{folder.name}"
                else:
                    display_name = folder.name
                
                result.append({
                    'id': folder.item_id,
                    'name': folder.name,
                    'display_name': display_name,
                    'parent_id': folder.parent_id
                })
                
                subfolder_prefix = f"{display_name} / " if display_name else ""
            
            # Recursief ophalen van subfolders (met of zonder VIC Leden prefix)
            if is_vic_folder:
                subfolders = build_folder_tree(folder.item_id, subfolder_prefix)
            else:
                subfolders = build_folder_tree(folder.item_id, subfolder_prefix)
            result.extend(subfolders)
        
        return result
    
    return build_folder_tree()

# Bestanden pagina
@main.route("/bestanden")
@login_required
def bestanden():
    """Toon bestanden pagina met folders en files"""
    try:
        # Haal alle root-level items op (geen parent)
        root_items = db.session.query(FileItem).filter(FileItem.parent_id == None).order_by(FileItem.item_type.desc(), FileItem.name.asc()).all()
        
        # Check of er precies één root folder is met een naam zoals "VIC leden" of "C Leden"
        # In dat geval, toon direct de subfolders
        root_folders = [item for item in root_items if item.item_type == 'folder']
        
        if len(root_folders) == 1:
            root_folder = root_folders[0]
            folder_name_lower = root_folder.name.lower()
            # Check of de folder naam iets bevat zoals "leden" of "vic"
            if 'leden' in folder_name_lower or 'vic' in folder_name_lower or folder_name_lower.startswith('c '):
                # Skip deze root folder en toon direct de subfolders
                items_to_display = db.session.query(FileItem).filter(FileItem.parent_id == root_folder.item_id).order_by(FileItem.item_type.desc(), FileItem.name.asc()).all()
            else:
                items_to_display = root_items
        else:
            items_to_display = root_items
        
        # Organiseer items in folders en files
        folders = []
        files = []
        
        for item in items_to_display:
            if item.item_type == 'folder':
                # Tel aantal bestanden en mappen in deze folder
                children = db.session.query(FileItem).filter(FileItem.parent_id == item.item_id).all()
                file_count = sum(1 for c in children if c.item_type == 'file')
                folder_count = sum(1 for c in children if c.item_type == 'folder')
                folders.append({
                    'item': item,
                    'file_count': file_count,
                    'folder_count': folder_count
                })
            else:
                files.append(item)
        
        # Bepaal breadcrumbs (voor nu alleen root)
        breadcrumbs = []
        current_folder = None
        
        # Haal alle folders op voor dropdown selector
        all_folders = _get_all_folders()
        
        return render_template("bestanden.html", folders=folders, files=files, current_folder=current_folder, breadcrumbs=breadcrumbs, all_folders=all_folders)
    except Exception as exc:
        print(f"ERROR: Fout bij ophalen van bestanden: {exc}")
        import traceback
        traceback.print_exc()
        return render_template("bestanden.html", folders=[], files=[], current_folder=None, breadcrumbs=[])

@main.route("/bestanden/folder/<int:folder_id>")
@login_required
def bestanden_folder(folder_id):
    """Toon inhoud van een specifieke folder"""
    try:
        # Haal folder op
        folder = db.session.query(FileItem).filter(FileItem.item_id == folder_id, FileItem.item_type == 'folder').first()
        
        if not folder:
            flash("Folder niet gevonden.", "error")
            return redirect(url_for("main.bestanden"))
        
        # Haal items in deze folder op
        items = db.session.query(FileItem).filter(FileItem.parent_id == folder_id).order_by(FileItem.item_type.desc(), FileItem.name.asc()).all()
        
        # Organiseer items in folders en files
        folders = []
        files = []
        
        for item in items:
            if item.item_type == 'folder':
                # Tel aantal bestanden en mappen in deze folder
                children = db.session.query(FileItem).filter(FileItem.parent_id == item.item_id).all()
                file_count = sum(1 for c in children if c.item_type == 'file')
                folder_count = sum(1 for c in children if c.item_type == 'folder')
                folders.append({
                    'item': item,
                    'file_count': file_count,
                    'folder_count': folder_count
                })
            else:
                files.append(item)
        
        # Bouw breadcrumbs (pad naar deze folder)
        breadcrumbs = []
        
        # Start altijd met "Bestanden"
        breadcrumbs.append({'name': 'Bestanden', 'id': None, 'url': url_for('main.bestanden')})
        
        # Bouw pad naar deze folder (skip "VIC leden" folder)
        path_items = []
        temp = folder
        while temp.parent_id:
            path_items.insert(0, temp)
            temp = db.session.query(FileItem).filter(FileItem.item_id == temp.parent_id).first()
            if not temp:
                break
        
        # Voeg pad items toe (skip "VIC leden" folder)
        for path_item in path_items:
            folder_name_lower = path_item.name.lower()
            # Skip de "VIC leden" folder
            if not ('leden' in folder_name_lower or 'vic' in folder_name_lower or folder_name_lower.startswith('c ')):
                breadcrumbs.append({
                    'name': path_item.name,
                    'id': path_item.item_id,
                    'url': url_for('main.bestanden_folder', folder_id=path_item.item_id)
                })
        
        # Voeg huidige folder toe
        breadcrumbs.append({'name': folder.name, 'id': folder.item_id, 'url': None})
        
        # Haal alle folders op voor dropdown selector
        all_folders = _get_all_folders(exclude_folder_id=folder.item_id)
        
        return render_template("bestanden.html", folders=folders, files=files, current_folder=folder, breadcrumbs=breadcrumbs, all_folders=all_folders)
    except Exception as exc:
        print(f"ERROR: Fout bij ophalen van folder inhoud: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij ophalen van folder inhoud.", "error")
        return redirect(url_for("main.bestanden"))

@main.route("/bestanden/create-folder", methods=["POST"])
@login_required
def create_folder():
    """Maak een nieuwe folder aan"""
    try:
        folder_name = request.form.get("folder_name", "").strip()
        parent_id = request.form.get("parent_id", "").strip()
        
        parent_id_int = int(parent_id) if parent_id else None
        
        if not folder_name:
            flash("Mapnaam is verplicht.", "error")
            if parent_id_int:
                return redirect(url_for("main.bestanden_folder", folder_id=parent_id_int))
            return redirect(url_for("main.bestanden"))
        
        # Check of folder al bestaat
        existing = db.session.query(FileItem).filter(
            FileItem.name == folder_name,
            FileItem.item_type == 'folder',
            FileItem.parent_id == parent_id_int
        ).first()
        
        if existing:
            flash(f"Een map met de naam '{folder_name}' bestaat al.", "error")
            if parent_id_int:
                return redirect(url_for("main.bestanden_folder", folder_id=parent_id_int))
            return redirect(url_for("main.bestanden"))
        
        new_folder = FileItem(
            name=folder_name,
            item_type='folder',
            parent_id=parent_id_int,
            created_by=g.user.member_id if g.user else None
        )
        
        db.session.add(new_folder)
        db.session.commit()
        
        flash(f"Map '{folder_name}' is succesvol aangemaakt.", "success")
    except Exception as exc:
        print(f"ERROR: Fout bij aanmaken van folder: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij aanmaken van map.", "error")
    
    # Redirect naar parent folder als die bestaat, anders naar root
    parent_id_int = int(parent_id) if parent_id else None
    if parent_id_int:
        return redirect(url_for("main.bestanden_folder", folder_id=parent_id_int))
    return redirect(url_for("main.bestanden"))

@main.route("/bestanden/upload-file", methods=["POST"])
@login_required
def upload_file():
    """Upload een bestand"""
    try:
        if 'file' not in request.files:
            flash("Geen bestand geselecteerd.", "error")
            return redirect(url_for("main.bestanden"))
        
        file = request.files['file']
        if file.filename == '':
            flash("Geen bestand geselecteerd.", "error")
            return redirect(url_for("main.bestanden"))
        
        parent_id = request.form.get("parent_id", "").strip()
        parent_id_int = int(parent_id) if parent_id else None
        
        # Haal upload folder op uit config
        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        upload_folder.mkdir(parents=True, exist_ok=True)
        
        # Bepaal waar bestand opgeslagen moet worden
        if parent_id_int:
            # Maak folder structuur gebaseerd op parent folder
            parent_folder = db.session.query(FileItem).filter(FileItem.item_id == parent_id_int).first()
            if parent_folder:
                folder_parts = []
                current_folder = parent_folder
                while current_folder:
                    folder_parts.insert(0, current_folder.name)
                    if current_folder.parent_id:
                        current_folder = db.session.query(FileItem).filter(
                            FileItem.item_id == current_folder.parent_id
                        ).first()
                    else:
                        current_folder = None
                
                file_upload_dir = upload_folder / Path(*folder_parts)
            else:
                file_upload_dir = upload_folder
        else:
            file_upload_dir = upload_folder
        
        file_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Genereer unieke bestandsnaam als bestand al bestaat
        file_name = file.filename
        file_dest = file_upload_dir / file_name
        counter = 1
        while file_dest.exists():
            name_parts = file_name.rsplit('.', 1)
            if len(name_parts) == 2:
                file_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
            else:
                file_name = f"{file_name}_{counter}"
            file_dest = file_upload_dir / file_name
            counter += 1
        
        # Sla bestand op
        file.save(str(file_dest))
        file_size = file_dest.stat().st_size
        
        # Sla file path relatief op ten opzichte van upload folder
        relative_file_path = file_dest.relative_to(upload_folder)
        
        # Maak FileItem record aan
        new_file = FileItem(
            name=file_name,
            item_type='file',
            parent_id=parent_id_int,
            file_path=str(relative_file_path),
            file_size=file_size,
            created_by=g.user.member_id if g.user else None
        )
        
        db.session.add(new_file)
        db.session.commit()
        
        flash(f"Bestand '{file_name}' is succesvol geüpload.", "success")
    except Exception as exc:
        print(f"ERROR: Fout bij uploaden van bestand: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij uploaden van bestand.", "error")
    
    # Redirect naar parent folder als die bestaat, anders naar root
    parent_id_int = int(parent_id) if parent_id else None
    if parent_id_int:
        return redirect(url_for("main.bestanden_folder", folder_id=parent_id_int))
    # Redirect naar parent folder als die bestaat, anders naar root
    parent_id_int = int(parent_id) if parent_id else None
    if parent_id_int:
        return redirect(url_for("main.bestanden_folder", folder_id=parent_id_int))
    return redirect(url_for("main.bestanden"))

@main.route("/bestanden/import-zip", methods=["POST"])
@login_required
def import_zip():
    """Importeer een zip bestand met folders en files"""
    try:
        if 'zip_file' not in request.files:
            flash("Geen zip bestand geselecteerd.", "error")
            return redirect(url_for("main.bestanden"))
        
        zip_file = request.files['zip_file']
        if zip_file.filename == '' or not zip_file.filename.lower().endswith('.zip'):
            flash("Selecteer een geldig zip bestand.", "error")
            return redirect(url_for("main.bestanden"))
        
        # Haal upload folder op uit config
        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        upload_folder.mkdir(parents=True, exist_ok=True)
        
        # Sla zip tijdelijk op
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / zip_file.filename
            zip_file.save(str(zip_path))
            
            # Extraheer zip
            extract_path = temp_path / 'extracted'
            extract_path.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Dictionary om parent folders bij te houden tijdens import
            folder_map = {}  # {relative_path: FileItem}
            
            def process_path(file_path, parent_db_id=None):
                """Recursieve functie om folders en files te verwerken"""
                relative_path = file_path.relative_to(extract_path)
                
                if file_path.is_dir():
                    # Maak folder aan in database
                    folder_name = file_path.name
                    
                    # Check of folder al bestaat
                    existing_folder = db.session.query(FileItem).filter(
                        FileItem.name == folder_name,
                        FileItem.item_type == 'folder',
                        FileItem.parent_id == parent_db_id
                    ).first()
                    
                    if existing_folder:
                        folder_item = existing_folder
                    else:
                        folder_item = FileItem(
                            name=folder_name,
                            item_type='folder',
                            parent_id=parent_db_id,
                            created_by=g.user.member_id if g.user else None
                        )
                        db.session.add(folder_item)
                        db.session.flush()  # Flush om ID te krijgen
                    
                    folder_map[str(relative_path)] = folder_item
                    
                    # Verwerk kinderen
                    for child in sorted(file_path.iterdir()):
                        process_path(child, folder_item.item_id)
                        
                elif file_path.is_file():
                    # Maak file aan in database en kopieer naar upload folder
                    file_name = file_path.name
                    file_size = file_path.stat().st_size
                    
                    # Bepaal waar bestand opgeslagen moet worden
                    relative_path_str = str(relative_path.parent)
                    parent_folder = folder_map.get(relative_path_str)
                    parent_db_id = parent_folder.item_id if parent_folder else parent_db_id
                    
                    # Kopieer bestand naar upload folder
                    # Maak folder structuur in upload folder
                    if parent_folder:
                        # Recreëer folder structuur in upload folder
                        folder_parts = []
                        current_folder = parent_folder
                        while current_folder:
                            folder_parts.insert(0, current_folder.name)
                            if current_folder.parent_id:
                                current_folder = db.session.query(FileItem).filter(
                                    FileItem.item_id == current_folder.parent_id
                                ).first()
                            else:
                                current_folder = None
                        
                        file_upload_dir = upload_folder / Path(*folder_parts)
                    else:
                        file_upload_dir = upload_folder
                    
                    file_upload_dir.mkdir(parents=True, exist_ok=True)
                    file_dest = file_upload_dir / file_name
                    
                    # Kopieer bestand
                    shutil.copy2(file_path, file_dest)
                    
                    # Sla file path relatief op ten opzichte van upload folder
                    relative_file_path = file_dest.relative_to(upload_folder)
                    
                    # Check of file al bestaat
                    existing_file = db.session.query(FileItem).filter(
                        FileItem.name == file_name,
                        FileItem.item_type == 'file',
                        FileItem.parent_id == parent_db_id
                    ).first()
                    
                    if not existing_file:
                        file_item = FileItem(
                            name=file_name,
                            item_type='file',
                            parent_id=parent_db_id,
                            file_path=str(relative_file_path),
                            file_size=file_size,
                            created_by=g.user.member_id if g.user else None
                        )
                        db.session.add(file_item)
            
            # Verwerk alle items in de geëxtraheerde zip
            for item in sorted(extract_path.iterdir()):
                process_path(item, None)
            
            db.session.commit()
            
            flash(f"Zip bestand succesvol geïmporteerd! Folders en bestanden zijn toegevoegd.", "success")
            
    except zipfile.BadZipFile:
        flash("Ongeldig zip bestand.", "error")
    except Exception as exc:
        print(f"ERROR: Fout bij importeren van zip bestand: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f"Fout bij importeren van zip bestand: {str(exc)}", "error")
    
    return redirect(url_for("main.bestanden"))

@main.route("/bestanden/download/<int:file_id>")
@login_required
def download_file(file_id):
    """Download een bestand"""
    try:
        # Haal file item op
        file_item = db.session.query(FileItem).filter(
            FileItem.item_id == file_id,
            FileItem.item_type == 'file'
        ).first()
        
        if not file_item:
            flash("Bestand niet gevonden.", "error")
            abort(404)
        
        # Controleer of bestand een file_path heeft
        if not file_item.file_path:
            flash("Bestand pad niet gevonden.", "error")
            abort(404)
        
        # Haal upload folder op uit config
        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        file_path = upload_folder / file_item.file_path
        
        # Controleer of bestand bestaat
        if not file_path.exists() or not file_path.is_file():
            flash("Bestand niet gevonden op de server.", "error")
            abort(404)
        
        # Serveer bestand voor download
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=file_item.name,
            mimetype=None  # Laat Flask MIME-type automatisch detecteren
        )
        
    except Exception as exc:
        print(f"ERROR: Fout bij downloaden van bestand: {exc}")
        import traceback
        traceback.print_exc()
        flash("Fout bij downloaden van bestand.", "error")
        abort(500)

@main.route("/bestanden/edit/<int:file_id>", methods=["POST"])
@login_required
def edit_file(file_id):
    """Bewerk een bestand (naam wijzigen)"""
    try:
        file_item = db.session.query(FileItem).filter(
            FileItem.item_id == file_id,
            FileItem.item_type == 'file'
        ).first()
        
        if not file_item:
            flash("Bestand niet gevonden.", "error")
            return redirect(url_for("main.bestanden"))
        
        new_name = request.form.get("file_name", "").strip()
        if not new_name:
            flash("Bestandsnaam is verplicht.", "error")
            return redirect(url_for("main.bestanden"))
        
        # Check of bestand met nieuwe naam al bestaat in dezelfde folder
        existing = db.session.query(FileItem).filter(
            FileItem.name == new_name,
            FileItem.item_type == 'file',
            FileItem.parent_id == file_item.parent_id,
            FileItem.item_id != file_id
        ).first()
        
        if existing:
            flash(f"Een bestand met de naam '{new_name}' bestaat al in deze map.", "error")
            if file_item.parent_id:
                return redirect(url_for("main.bestanden_folder", folder_id=file_item.parent_id))
            return redirect(url_for("main.bestanden"))
        
        # Update bestandsnaam
        old_name = file_item.name
        file_item.name = new_name
        
        # Als bestand fysiek bestaat, hernoem het ook
        if file_item.file_path:
            upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
            old_file_path = upload_folder / file_item.file_path
            
            if old_file_path.exists() and old_file_path.is_file():
                # Bepaal nieuwe pad
                new_file_path = old_file_path.parent / new_name
                try:
                    old_file_path.rename(new_file_path)
                    # Update file_path in database
                    relative_new_path = new_file_path.relative_to(upload_folder)
                    file_item.file_path = str(relative_new_path)
                except Exception as rename_exc:
                    print(f"WARNING: Kon bestand niet hernoemen: {rename_exc}")
                    # Ga door met database update ook al is fysieke rename mislukt
        
        db.session.commit()
        flash(f"Bestand '{old_name}' is hernoemd naar '{new_name}'.", "success")
        
    except Exception as exc:
        print(f"ERROR: Fout bij bewerken van bestand: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij bewerken van bestand.", "error")
    
    # Redirect terug naar folder of root
    file_item = db.session.query(FileItem).filter(FileItem.item_id == file_id).first()
    if file_item and file_item.parent_id:
        return redirect(url_for("main.bestanden_folder", folder_id=file_item.parent_id))
    return redirect(url_for("main.bestanden"))

@main.route("/bestanden/delete/<int:file_id>")
@login_required
def delete_file(file_id):
    """Verwijder een bestand"""
    try:
        file_item = db.session.query(FileItem).filter(
            FileItem.item_id == file_id,
            FileItem.item_type == 'file'
        ).first()
        
        if not file_item:
            flash("Bestand niet gevonden.", "error")
            return redirect(url_for("main.bestanden"))
        
        file_name = file_item.name
        parent_id = file_item.parent_id
        
        # Verwijder fysiek bestand als het bestaat
        if file_item.file_path:
            upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
            file_path = upload_folder / file_item.file_path
            
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                except Exception as delete_exc:
                    print(f"WARNING: Kon fysiek bestand niet verwijderen: {delete_exc}")
                    # Ga door met database verwijdering ook al is fysieke delete mislukt
        
        # Verwijder uit database
        db.session.delete(file_item)
        db.session.commit()
        
        flash(f"Bestand '{file_name}' is succesvol verwijderd.", "success")
        
    except Exception as exc:
        print(f"ERROR: Fout bij verwijderen van bestand: {exc}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("Fout bij verwijderen van bestand.", "error")
    
    # Redirect terug naar folder of root
    if parent_id:
        return redirect(url_for("main.bestanden_folder", folder_id=parent_id))
    return redirect(url_for("main.bestanden"))