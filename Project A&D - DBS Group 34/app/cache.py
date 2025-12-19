"""
Gecentraliseerde cache initialisatie voor yfinance API calls.
Dit voorkomt duplicatie tussen routes.py en jobs.py.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Globale variabele om te tracken of cache al geïnitialiseerd is
_cache_initialized = False


def initialize_yfinance_cache():
    """
    Initialiseer requests_cache voor yfinance rate limiting.
    Werkt globaal voor alle HTTP requests inclusief yfinance.
    Kan veilig meerdere keren worden aangeroepen - doet niets als al geïnitialiseerd.
    """
    global _cache_initialized
    
    if _cache_initialized:
        logger.debug("Cache al geïnitialiseerd, skip.")
        return
    
    try:
        import requests_cache
        
        # Gebruik dezelfde cache directory voor consistentie
        _cache_dir = Path(__file__).parent.parent / '.cache'
        _cache_dir.mkdir(exist_ok=True)
        _cache_file = _cache_dir / 'yfinance_cache'
        
        # Installeer de cache voor alle requests (werkt automatisch voor yfinance)
        # Dit cached alle HTTP requests inclusief yf.Ticker().info calls
        requests_cache.install_cache(
            cache_name=str(_cache_file),
            expire_after=86400,  # 24 uur in seconden
            backend='sqlite',
            allowable_methods=['GET', 'POST'],
            allowable_codes=[200, 429],  # Cache ook 429 errors
            stale_if_error=True  # Gebruik oude data bij errors
        )
        logger.info(f"YFinance cache geïnitialiseerd: {_cache_file} (TTL: 24 uur)")
        _cache_initialized = True
        
    except ImportError:
        logger.warning("requests_cache niet beschikbaar - rate limiting kan optreden bij yfinance calls")
        _cache_initialized = True  # Markeer als geïnitialiseerd om herhaalde warnings te voorkomen
    except Exception as e:
        logger.warning(f"Kon requests_cache niet initialiseren: {e}. Rate limiting kan optreden.")
        _cache_initialized = True  # Markeer als geïnitialiseerd om herhaalde warnings te voorkomen

