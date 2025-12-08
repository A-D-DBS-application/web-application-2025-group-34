# Project A&D - DBS Group 34/app/jobs.py

from .models import db, Position, Portfolio
import yfinance as yf
from sqlalchemy import func

def fetch_exchange_rate(currency_pair, currency_name):
    """Haal exchange rate op voor een valuta paar via yfinance"""
    try:
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

# Om te testen: zorg ervoor dat 'db' wordt geïmporteerd via 'from .models import db'
# en niet 'db = SQLAlchemy()'