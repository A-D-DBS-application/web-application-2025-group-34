"""
Utility functies voor de applicatie
"""
import urllib.parse
import logging
from typing import List, Tuple, Optional
import yfinance as yf
from . import db
from .models import Position, Portfolio

logger = logging.getLogger(__name__)


def normalize_ticker_for_yfinance(ticker: str, return_variants: bool = True) -> List[str] | str:
    """
    Normaliseer ticker en genereer varianten om te proberen voor Yahoo Finance.
    Deze functie vervangt zowel normalize_ticker_for_yfinance() als normalize_ticker()
    uit risk_analysis.py.
    
    Args:
        ticker: Originele ticker string
        return_variants: Als True, retourneert lijst van varianten. Als False, retourneert enkel genormaliseerde string.
        
    Returns:
        Als return_variants=True: Lijst van ticker varianten om te proberen
        Als return_variants=False: Genormaliseerde ticker string
    """
    if not ticker:
        return [] if return_variants else ""
    
    # URL decode indien nodig
    ticker = urllib.parse.unquote(ticker)
    original_ticker = ticker.strip()
    
    # Als we alleen de genormaliseerde versie willen (zoals risk_analysis.py)
    if not return_variants:
        return original_ticker.upper()
    
    # Genereer varianten (zoals routes.py)
    normalized_ticker = original_ticker.replace(" ", "-").replace(".", "-").replace("--", "-")
    
    tickers_to_try = [
        original_ticker.upper(),
        normalized_ticker.upper(),
        original_ticker,
        normalized_ticker,
    ]
    
    # Voeg variant zonder punten/dashes toe
    if "." in original_ticker or "-" in original_ticker:
        clean_ticker = original_ticker.replace(".", "").replace("-", "").upper()
        if clean_ticker not in [t.upper() for t in tickers_to_try]:
            tickers_to_try.append(clean_ticker)
    
    # Verwijder duplicaten maar behoud volgorde
    seen = set()
    return [t for t in tickers_to_try if not (t in seen or seen.add(t))]


def fetch_company_info_from_yfinance(tickers_to_try: List[str], logger_instance: Optional[logging.Logger] = None) -> Tuple[Optional[dict], Optional[str]]:
    """
    Haal company info op via Yahoo Finance API
    
    Args:
        tickers_to_try: Lijst van ticker varianten om te proberen
        logger_instance: Logger instance (gebruikt module logger als None)
        
    Returns:
        Tuple van (info_dict, error_message) - info_dict is None bij error
    """
    log = logger_instance or logger
    last_error = None
    
    for ticker_variant in tickers_to_try:
        try:
            ticker_obj = yf.Ticker(ticker_variant)
            yf_info = ticker_obj.info
            
            # Check of we geldige data hebben
            if yf_info and isinstance(yf_info, dict) and len(yf_info) > 0:
                if any(key in yf_info for key in ['symbol', 'longName', 'shortName', 'name']):
                    log.debug(f"Company info opgehaald voor {ticker_variant}")
                    return yf_info, None
                else:
                    log.debug(f"Lege of ongeldige data voor {ticker_variant}")
            else:
                log.debug(f"Geen data voor {ticker_variant}")
        except Exception as yf_error:
            error_str = str(yf_error)
            last_error = yf_error
            log.debug(f"Error bij ophalen data voor {ticker_variant}: {error_str}")
            continue
    
    # Geen data gevonden
    error_msg = 'Ticker not found or no data available.'
    if last_error:
        error_str = str(last_error)
        if '429' in error_str or 'Too Many Requests' in error_str:
            error_msg = 'Yahoo Finance is rate limiting requests. Please try again in a few minutes.'
        elif '404' in error_str or 'Not Found' in error_str:
            error_msg = 'This ticker may not exist or may be delisted.'
    
    return None, error_msg


# ============================================================================
# DATABASE HELPER FUNCTIES
# ============================================================================

def get_cash_position():
    """
    Haal cash positie op (pos_id == 0).
    Gecached voor efficiëntie - cash positie wordt vaak opgehaald.
    """
    return db.session.query(Position).filter(Position.pos_id == 0).first()


def get_positions(exclude_cash: bool = True):
    """
    Haal alle posities op (exclusief cash standaard).
    
    Args:
        exclude_cash: Als True, sluit cash positie uit (pos_id != 0)
    
    Returns:
        Query result met alle posities
    """
    query = db.session.query(Position)
    if exclude_cash:
        query = query.filter(Position.pos_id != 0)
    return query.all()


def get_portfolio():
    """
    Haal het eerste portfolio op (meestal is er maar één).
    """
    return db.session.query(Portfolio).first()

