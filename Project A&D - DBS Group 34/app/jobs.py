# Project A&D - DBS Group 34/app/jobs.py

from flask import current_app
from .models import db, Position, Portfolio
import yfinance as yf
from sqlalchemy import func

def update_portfolio_prices():
    """
    Haalt de live beurskoersen op voor alle unieke assets in het portfolio,
    en werkt de totale winst/verlies bij in de Portfolio tabel.
    """
    with current_app.app_context():
        # 1. Haal alle unieke tickers op uit de Position tabel
        tickers = db.session.query(Position.pos_name).distinct().all()
        # Converteer naar een lijst van strings (tickers)
        ticker_list = [t[0] for t in tickers if t[0]]
        
        if not ticker_list:
            print("Geen assets gevonden om te tracken.")
            return
            
        print(f"Start koersen ophalen voor: {ticker_list}")
        
        try:
            # 2. Gebruik yfinance om de live prijzen op te halen
            # Gebruik Tickers om data van meerdere symbolen tegelijk op te vragen
            ticker_data = yf.Tickers(ticker_list)
            
            # 3. Bereken de totale live-waarde van het portfolio
            total_live_value = 0.0
            
            all_positions = db.session.query(Position).all()
            
            for pos in all_positions:
                ticker = pos.pos_name
                
                # Haal de meest recente prijs op uit de yfinance data
                # Gebruik 'currentPrice' als 'regularMarketPrice' niet beschikbaar is
                try:
                    price = ticker_data.tickers[ticker].info.get('regularMarketPrice') or \
                            ticker_data.tickers[ticker].info.get('currentPrice')
                except Exception as e:
                    print(f"WAARSCHUWING: Kan prijs voor {ticker} niet ophalen. Fout: {e}")
                    price = None
                    
                if price is not None and pos.pos_quantity is not None:
                    total_live_value += price * pos.pos_quantity
            
            # 4. Update de Portfolio tabel
            # Voor een simpele setup: zoek het meest recente portfolio-item en update de winst/verlies
            latest_portfolio = db.session.query(Portfolio).order_by(Portfolio.portfolio_date.desc()).first()
            
            if latest_portfolio:
                # Let op: U moet bepalen hoe u 'profit&loss' definieert.
                # Hieronder wordt een simpele totale waarde gebruikt.
                # Om echte P&L te berekenen heeft u de initiële investering nodig.
                
                # Totaal geïnvesteerd bedrag (dit is een schatting, pas aan naar uw logica)
                total_cost = db.session.query(func.sum(Position.pos_amount)).scalar() or 0.0
                
                # Update P&L in de database
                latest_portfolio.profit_loss = total_live_value - total_cost
                db.session.commit()
                
                print(f"Portfolio bijgewerkt: Nieuwe P&L: {latest_portfolio.profit_loss:.2f} (gebaseerd op totale live waarde: {total_live_value:.2f})")
            
        except Exception as e:
            db.session.rollback()
            print(f"FATALE FOUT bij het updaten van portfolio prijzen: {e}")

# Om te testen: zorg ervoor dat 'db' wordt geïmporteerd via 'from .models import db'
# en niet 'db = SQLAlchemy()'