# Project A&D - DBS Group 34/app/jobs.py

from .models import db, Position, Portfolio
import yfinance as yf
from sqlalchemy import func

def update_portfolio_prices(app):
    """
    Haalt de live beurskoersen op voor alle unieke assets in het portfolio,
    en werkt de current_price en day_change_pct bij in de Position tabel.
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
            # 2. Gebruik yfinance om de live prijzen op te halen
            ticker_objects = yf.Tickers(" ".join(ticker_list))
            
            # 3. Update elke positie met de nieuwe prijs en dagverandering
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
                        # Bereken dagverandering percentage
                        day_change_pct = ((current_price - previous_close) / previous_close) * 100
                        
                        # Update positie in database
                        pos.current_price = current_price
                        pos.day_change_pct = day_change_pct
                        updated_count += 1
                    else:
                        print(f"WAARSCHUWING: Kan prijs voor {ticker} niet ophalen (geen data beschikbaar)")
                        
                except Exception as e:
                    print(f"WAARSCHUWING: Kan prijs voor {ticker} niet ophalen. Fout: {e}")
                    continue
            
            # Commit alle wijzigingen
            db.session.commit()
            print(f"✓ {updated_count} posities bijgewerkt met nieuwe prijzen")
            
        except Exception as e:
            db.session.rollback()
            print(f"FATALE FOUT bij het updaten van portfolio prijzen: {e}")

# Om te testen: zorg ervoor dat 'db' wordt geïmporteerd via 'from .models import db'
# en niet 'db = SQLAlchemy()'