# Project A&D - DBS Group 34/app/jobs.py

from .models import db, Position, Portfolio, StockPriceHistory, CompanyInfo
import yfinance as yf
from sqlalchemy import func, and_
from datetime import datetime, timedelta, date
import time
import logging
from pathlib import Path
import pandas as pd

# Initialize requests_cache voor yfinance rate limiting
# Dit zorgt ervoor dat alle yfinance calls gecached worden (24 uur)
# Belangrijk: requests_cache.install_cache() werkt GLOBAAL, dus als het al in routes.py
# of risk_analysis.py is geïnitialiseerd, wordt die cache gebruikt.
# We initialiseren het hier ook voor het geval jobs.py als eerste wordt geladen.
try:
    import requests_cache
    _cache_dir = Path(__file__).parent.parent / '.cache'
    _cache_dir.mkdir(exist_ok=True)
    _cache_file = _cache_dir / 'yfinance_cache'
    
    # Probeer cache te installeren (als het al geïnstalleerd is, doet dit niets)
    try:
        requests_cache.install_cache(
            cache_name=str(_cache_file),
            expire_after=86400,  # 24 uur
            backend='sqlite',
            allowable_methods=['GET', 'POST'],
            allowable_codes=[200, 429],
            stale_if_error=True
        )
        logger = logging.getLogger(__name__)
        logger.info(f"Price update cache geïnitialiseerd: {_cache_file} (TTL: 24 uur)")
    except Exception as e:
        # Cache is mogelijk al geïnstalleerd door een andere module
        logger = logging.getLogger(__name__)
        logger.debug(f"Cache al geïnstalleerd of fout: {e}")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("requests_cache niet beschikbaar - rate limiting kan optreden bij prijsupdates")

def fetch_exchange_rate(currency_pair, currency_name):
    """Haal exchange rate op voor een valuta paar via yfinance"""
    try:
        # Nieuwe versies van yfinance gebruiken automatisch curl_cffi als beschikbaar
        # Geen custom session nodig - yfinance handelt dit zelf af
        ticker = yf.Ticker(currency_pair)
        info = ticker.info
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        if price:
            rate = 1.0 / price  # Converteer naar EUR
            print(f"{currency_name}/EUR wisselkoers: {rate:.4f}")
            return rate
    except Exception as e:
        print(f"WAARSCHUWING: Kan {currency_name}/EUR wisselkoers niet ophalen: {e}")
        print(f"{currency_name}-prijzen worden niet geconverteerd naar EUR.")
    return None

def update_portfolio_prices(app):
    """
    Haalt de live beurskoersen op voor alle unieke assets in het portfolio,
    en werkt de current_price en day_change_pct bij in de Position tabel.
    Prijzen worden automatisch geconverteerd naar EUR (USD, SEK, HKD, CNY -> EUR conversie).
    Dit wordt elke 5 minuten uitgevoerd door de scheduler.
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        # 1. Haal alle posities op met unieke tickers
        all_positions = db.session.query(Position).all()
        
        if not all_positions:
            print("Geen posities gevonden om te tracken.")
            return
        
        # Verzamel unieke tickers (gebruik pos_ticker als die bestaat, anders pos_name)
        ticker_set = set()
        for pos in all_positions:
            ticker = pos.pos_ticker or pos.pos_name
            if ticker:
                ticker_set.add(ticker)
        
        ticker_list = list(ticker_set)
        
        if not ticker_list:
            print("Geen tickers gevonden om te tracken.")
            return
            
        print(f"Start koersen ophalen voor {len(ticker_list)} tickers...")
        
        try:
            # 2. Haal wisselkoersen op (eenmalig voor alle conversies)
            # Haal alle exchange rates op
            exchange_rates = {
                'USD': fetch_exchange_rate("EURUSD=X", "USD"),
                'SEK': fetch_exchange_rate("EURSEK=X", "SEK"),
                'HKD': fetch_exchange_rate("EURHKD=X", "HKD"),
                'CNY': fetch_exchange_rate("EURCNY=X", "CNY"),
            }
            
            # 3. Gebruik yfinance om de live prijzen op te halen
            # Nieuwe versies van yfinance gebruiken automatisch curl_cffi als beschikbaar
            ticker_objects = yf.Tickers(" ".join(ticker_list))
            
            # 4. Update elke positie met de nieuwe prijs en dagverandering
            updated_count = 0
            for pos in all_positions:
                ticker = pos.pos_ticker or pos.pos_name
                if not ticker:
                    continue
                
                try:
                    ticker_obj = ticker_objects.tickers.get(ticker)
                    if not ticker_obj:
                        continue
                    
                    info = ticker_obj.info
                    
                    # Haal huidige prijs op
                    current_price = (info.get('regularMarketPrice') or 
                                    info.get('currentPrice') or 
                                    info.get('previousClose'))
                    
                    # Haal vorige sluitprijs op voor dagverandering
                    previous_close = info.get('previousClose') or current_price
                    
                    if current_price and previous_close:
                        # Detecteer valuta van het aandeel
                        currency = info.get('currency', '').upper()
                        
                        # Converteer naar EUR als nodig
                        if currency == 'EUR' or currency == '':
                            # Al EUR of valuta onbekend (aannemen dat het EUR is)
                            current_price_eur = current_price
                            previous_close_eur = previous_close
                        elif currency in exchange_rates and exchange_rates[currency]:
                            # Valuta met beschikbare conversie
                            rate = exchange_rates[currency]
                            current_price_eur = current_price * rate
                            previous_close_eur = previous_close * rate
                            print(f"{ticker}: {current_price:.2f} {currency} -> {current_price_eur:.2f} EUR")
                        else:
                            # Andere valuta (GBP, CHF, etc.) - waarschuw maar gebruik originele prijs
                            print(f"WAARSCHUWING: {ticker} heeft valuta {currency}, geen conversie beschikbaar. Gebruikt originele prijs.")
                            current_price_eur = current_price
                            previous_close_eur = previous_close
                        
                        # Bereken dagverandering percentage (na conversie)
                        day_change_pct = ((current_price_eur - previous_close_eur) / previous_close_eur) * 100
                        
                        # Update positie in database (opslaan in EUR)
                        pos.current_price = current_price_eur
                        pos.day_change_pct = day_change_pct
                        updated_count += 1
                    else:
                        print(f"WAARSCHUWING: Kan prijs voor {ticker} niet ophalen (geen data beschikbaar)")
                        
                except Exception as e:
                    print(f"WAARSCHUWING: Kan prijs voor {ticker} niet ophalen. Fout: {e}")
                    continue
            
            # Commit alle wijzigingen
            db.session.commit()
            print(f"✓ {updated_count} posities bijgewerkt met nieuwe prijzen (in EUR)")
            
        except Exception as e:
            db.session.rollback()
            print(f"FATALE FOUT bij het updaten van portfolio prijzen: {e}")

def update_historical_prices(app, lookback_days: int = 365):
    """
    Haal historische dagelijkse sluitingsprijzen op voor alle tickers in het portfolio
    en sla ze op in de database. Dit wordt dagelijks uitgevoerd (bijv. 's nachts).
    
    Args:
        app: Flask application instance
        lookback_days: Aantal dagen historische data om op te halen (default: 365 = 1 jaar)
    """
    with app.app_context():
        logger = logging.getLogger(__name__)
        logger.info("Start update historische prijzen...")
        
        # 1. Haal alle unieke tickers op uit posities
        all_positions = db.session.query(Position).all()
        ticker_set = set()
        for pos in all_positions:
            ticker = pos.pos_ticker or pos.pos_name
            if ticker:
                ticker_set.add(ticker.strip().upper())
        
        # 2. Voeg ook benchmark tickers toe (voor risk analysis)
        from .algorithms.risk_analysis import BENCHMARKS
        for benchmark_name, benchmark_weights in BENCHMARKS.items():
            for ticker in benchmark_weights.keys():
                ticker_set.add(ticker.strip().upper())
        
        if not ticker_set:
            logger.info("Geen tickers gevonden om historische data voor op te halen.")
            return
        
        ticker_list = list(ticker_set)
        logger.info(f"Ophalen historische data voor {len(ticker_list)} tickers ({len(all_positions)} posities + benchmarks)...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer
        
        updated_count = 0
        error_count = 0
        
        for ticker in ticker_list:
            try:
                # Skip CASH ticker (geen historische data nodig)
                if ticker.upper() == 'CASH':
                    continue
                
                # Download historische data via yfinance
                ticker_data = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True
                )
                
                if ticker_data.empty or len(ticker_data) == 0:
                    logger.warning(f"Geen data beschikbaar voor {ticker}")
                    continue
                
                # Verwerk de data - handle verschillende DataFrame structuren
                # yfinance kan een DataFrame met MultiIndex columns teruggeven
                prices = None
                
                try:
                    # Eenvoudige aanpak: probeer altijd 'Close' kolom eerst
                    if 'Close' in ticker_data.columns:
                        prices = ticker_data['Close']
                    elif isinstance(ticker_data.columns, pd.MultiIndex):
                        # MultiIndex: zoek Close in eerste level
                        level_0_cols = ticker_data.columns.get_level_values(0)
                        if 'Close' in level_0_cols:
                            # Vind de Close kolom
                            for col in ticker_data.columns:
                                if isinstance(col, tuple) and col[0] == 'Close':
                                    prices = ticker_data[col]
                                    break
                            if prices is None:
                                # Fallback: gebruik eerste kolom
                                prices = ticker_data.iloc[:, 0]
                        else:
                            # Geen Close, gebruik eerste kolom
                            prices = ticker_data.iloc[:, 0]
                    else:
                        # Geen Close kolom, gebruik eerste kolom
                        if len(ticker_data.columns) > 0:
                            prices = ticker_data.iloc[:, 0]
                        else:
                            logger.warning(f"Geen kolommen gevonden in ticker_data voor {ticker}")
                            continue
                    
                    # Zorg dat prices een Series is (iloc[:, 0] geeft altijd een Series)
                    if prices is None:
                        logger.warning(f"Kon geen prijsdata vinden voor {ticker}")
                        continue
                    
                    # Als het een DataFrame is (zou niet moeten gebeuren, maar voor de zekerheid)
                    if isinstance(prices, pd.DataFrame):
                        prices = prices.iloc[:, 0]
                    
                    # Zorg dat het een Series is
                    if not isinstance(prices, pd.Series):
                        logger.warning(f"Prijsdata is geen Series voor {ticker}, type: {type(prices)}")
                        continue
                    
                    # Zorg dat de Series niet leeg is
                    if len(prices) == 0:
                        logger.warning(f"Lege prijsdata voor {ticker}")
                        continue
                        
                except Exception as extract_error:
                    logger.warning(f"Fout bij extraheren prijsdata voor {ticker}: {extract_error}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
                
                # Bulk fetch bestaande records voor deze ticker (efficiënter dan per datum query)
                price_dates = []
                for date_idx in prices.index:
                    if pd.isna(prices[date_idx]):
                        continue
                    try:
                        if isinstance(date_idx, pd.Timestamp):
                            price_dates.append(date_idx.date())
                        elif hasattr(date_idx, 'date'):
                            price_dates.append(date_idx.date())
                        else:
                            price_dates.append(pd.to_datetime(date_idx).date())
                    except Exception:
                        continue
                
                # Bulk query voor bestaande records
                existing_records = {
                    record.price_date: record
                    for record in db.session.query(StockPriceHistory).filter(
                        and_(
                            StockPriceHistory.ticker == ticker,
                            StockPriceHistory.price_date.in_(price_dates)
                        )
                    ).all()
                }
                
                records_added = 0
                records_updated = 0
                now = datetime.now()
                
                # Sla elke dagprijs op in database
                for date_idx, close_price in prices.items():
                    if pd.isna(close_price):
                        continue
                    
                    # Converteer date index naar date object
                    try:
                        if isinstance(date_idx, pd.Timestamp):
                            price_date = date_idx.date()
                        elif hasattr(date_idx, 'date'):
                            price_date = date_idx.date()
                        else:
                            price_date = pd.to_datetime(date_idx).date()
                    except Exception as date_error:
                        logger.warning(f"Kon datum niet parsen voor {ticker}: {date_idx} - {date_error}")
                        continue
                    
                    # Haal scalar waarden op (niet Series)
                    try:
                        close_val = float(close_price) if not pd.isna(close_price) else None
                        if close_val is None:
                            continue
                        
                        # Haal andere prijzen op (zorg dat we scalar waarden krijgen)
                        open_val = None
                        high_val = None
                        low_val = None
                        volume_val = None
                        
                        if isinstance(ticker_data.columns, pd.MultiIndex):
                            # MultiIndex: gebruik iloc of probeer kolom te vinden
                            row_idx = ticker_data.index.get_loc(date_idx) if date_idx in ticker_data.index else None
                            if row_idx is not None:
                                if 'Open' in ticker_data.columns.get_level_values(0):
                                    open_val = ticker_data.iloc[row_idx, ticker_data.columns.get_level_values(0).get_loc('Open')]
                                    if pd.notna(open_val):
                                        open_val = float(open_val)
                                    else:
                                        open_val = None
                                if 'High' in ticker_data.columns.get_level_values(0):
                                    high_val = ticker_data.iloc[row_idx, ticker_data.columns.get_level_values(0).get_loc('High')]
                                    if pd.notna(high_val):
                                        high_val = float(high_val)
                                    else:
                                        high_val = None
                                if 'Low' in ticker_data.columns.get_level_values(0):
                                    low_val = ticker_data.iloc[row_idx, ticker_data.columns.get_level_values(0).get_loc('Low')]
                                    if pd.notna(low_val):
                                        low_val = float(low_val)
                                    else:
                                        low_val = None
                                if 'Volume' in ticker_data.columns.get_level_values(0):
                                    vol_val = ticker_data.iloc[row_idx, ticker_data.columns.get_level_values(0).get_loc('Volume')]
                                    if pd.notna(vol_val):
                                        volume_val = int(vol_val)
                                    else:
                                        volume_val = None
                        else:
                            # Normale DataFrame
                            if date_idx in ticker_data.index:
                                if 'Open' in ticker_data.columns:
                                    open_val = ticker_data.loc[date_idx, 'Open']
                                    open_val = float(open_val) if pd.notna(open_val) else None
                                if 'High' in ticker_data.columns:
                                    high_val = ticker_data.loc[date_idx, 'High']
                                    high_val = float(high_val) if pd.notna(high_val) else None
                                if 'Low' in ticker_data.columns:
                                    low_val = ticker_data.loc[date_idx, 'Low']
                                    low_val = float(low_val) if pd.notna(low_val) else None
                                if 'Volume' in ticker_data.columns:
                                    vol_val = ticker_data.loc[date_idx, 'Volume']
                                    volume_val = int(vol_val) if pd.notna(vol_val) else None
                    except Exception as val_error:
                        logger.warning(f"Fout bij ophalen waarden voor {ticker} op {date_idx}: {val_error}")
                        continue
                    
                    # Check of record al bestaat (uit bulk query)
                    existing = existing_records.get(price_date)
                    
                    if existing:
                        # Update bestaand record
                        existing.close_price = close_val
                        existing.open_price = open_val
                        existing.high_price = high_val
                        existing.low_price = low_val
                        existing.volume = volume_val
                        existing.updated_at = now
                        records_updated += 1
                    else:
                        # Nieuw record
                        new_price = StockPriceHistory(
                            ticker=ticker,
                            price_date=price_date,
                            close_price=close_val,
                            open_price=open_val,
                            high_price=high_val,
                            low_price=low_val,
                            volume=volume_val
                        )
                        db.session.add(new_price)
                        records_added += 1
                
                # Commit per ticker om progress te behouden
                try:
                    db.session.commit()
                    updated_count += 1
                    logger.info(f"✓ {ticker}: {records_added} nieuwe records, {records_updated} bijgewerkt")
                except Exception as commit_error:
                    db.session.rollback()
                    logger.error(f"Fout bij committen data voor {ticker}: {commit_error}")
                    error_count += 1
                    continue
                
                # Rate limiting: wacht even tussen tickers
                time.sleep(1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Fout bij ophalen historische data voor {ticker}: {e}")
                db.session.rollback()  # Rollback bij fout
                continue
        
        logger.info(f"✓ Historische prijzen bijgewerkt: {updated_count} tickers succesvol, {error_count} fouten")


def update_company_info(app):
    """
    Haal company informatie op voor alle tickers in het portfolio
    en sla ze op in de database. Dit wordt dagelijks uitgevoerd.
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        logger = logging.getLogger(__name__)
        logger.info("Start update company info...")
        
        # 1. Haal alle unieke tickers op uit posities
        all_positions = db.session.query(Position).all()
        ticker_set = set()
        for pos in all_positions:
            ticker = pos.pos_ticker or pos.pos_name
            if ticker:
                ticker_set.add(ticker.strip().upper())
        
        # 2. Voeg ook benchmark tickers toe (voor risk analysis)
        from .algorithms.risk_analysis import BENCHMARKS
        for benchmark_name, benchmark_weights in BENCHMARKS.items():
            for ticker in benchmark_weights.keys():
                ticker_set.add(ticker.strip().upper())
        
        if not ticker_set:
            logger.info("Geen tickers gevonden om company info voor op te halen.")
            return
        
        ticker_list = list(ticker_set)
        logger.info(f"Ophalen company info voor {len(ticker_list)} tickers ({len(all_positions)} posities + benchmarks)...")
        
        updated_count = 0
        error_count = 0
        
        # Bulk fetch alle bestaande records in één query (efficiënter)
        existing_records = {
            record.ticker: record 
            for record in db.session.query(CompanyInfo).filter(
                CompanyInfo.ticker.in_([t.upper() for t in ticker_list])
            ).all()
        }
        
        for ticker in ticker_list:
            try:
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info
                
                if not info or len(info) == 0:
                    logger.warning(f"Geen company info beschikbaar voor {ticker}")
                    continue
                
                # Check of record al bestaat (uit bulk query)
                ticker_upper = ticker.upper()
                existing = existing_records.get(ticker_upper)
                
                # Extract financial data - gebruik service layer
                from .services.company_info_service import extract_financial_data_from_yfinance
                financial_data = extract_financial_data_from_yfinance(info)
                
                if existing:
                    # Update bestaand record
                    existing.name = info.get('shortName') or info.get('longName')
                    existing.long_name = info.get('longName')
                    existing.sector = info.get('sector')
                    existing.industry = info.get('industry')
                    existing.country = info.get('country')
                    existing.description = info.get('longBusinessSummary')
                    existing.website = info.get('website')
                    existing.employees = info.get('fullTimeEmployees')
                    existing.market_cap = info.get('marketCap')
                    existing.currency = info.get('currency')
                    existing.exchange = info.get('exchange')
                    existing.financial_data = financial_data
                    existing.updated_at = datetime.now()
                else:
                    # Nieuw record
                    new_info = CompanyInfo(
                        ticker=ticker,
                        name=info.get('shortName') or info.get('longName'),
                        long_name=info.get('longName'),
                        sector=info.get('sector'),
                        industry=info.get('industry'),
                        country=info.get('country'),
                        description=info.get('longBusinessSummary'),
                        website=info.get('website'),
                        employees=info.get('fullTimeEmployees'),
                        market_cap=info.get('marketCap'),
                        currency=info.get('currency'),
                        exchange=info.get('exchange'),
                        financial_data=financial_data
                    )
                    db.session.add(new_info)
                
                # Commit per ticker om progress te behouden
                db.session.commit()
                updated_count += 1
                logger.info(f"✓ {ticker}: Company info opgeslagen")
                
                # Rate limiting: wacht even tussen tickers
                time.sleep(1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Fout bij ophalen company info voor {ticker}: {e}")
                db.session.rollback()  # Rollback bij fout
                continue
        
        logger.info(f"✓ Company info bijgewerkt: {updated_count} tickers succesvol, {error_count} fouten")

# Om te testen: zorg ervoor dat 'db' wordt geïmporteerd via 'from .models import db'
# en niet 'db = SQLAlchemy()'