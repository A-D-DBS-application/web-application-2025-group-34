"""
Company Info Service - Centraliseert logica voor company info ophalen en formatteren
"""
from typing import Dict, Optional, Any, List
from sqlalchemy import or_, func
from .. import db
from ..models import CompanyInfo, Position
import logging

logger = logging.getLogger(__name__)

# Financial data field mapping (yfinance -> database -> display)
FINANCIAL_DATA_MAPPING = {
    'pe_ratio': 'trailingPE',
    'forward_pe': 'forwardPE',
    'peg_ratio': 'pegRatio',
    'price_to_book': 'priceToBook',
    'price_to_sales': 'priceToSalesTrailing12Months',
    'dividend_yield': 'dividendYield',
    'dividend_rate': 'dividendRate',
    'payout_ratio': 'payoutRatio',
    'eps': 'trailingEps',
    'eps_forward': 'forwardEps',
    'beta': 'beta',
    '52_week_high': 'fiftyTwoWeekHigh',
    '52_week_low': 'fiftyTwoWeekLow',
    'book_value': 'bookValue',
    'revenue_ttm': 'totalRevenue',
    'profit_margin': 'profitMargins',
    'operating_margin': 'operatingMargins',
    'return_on_assets': 'returnOnAssets',
    'return_on_equity': 'returnOnEquity',
    'debt_to_equity': 'debtToEquity',
    'current_ratio': 'currentRatio',
}


def extract_financial_data_from_yfinance(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract financial data from yfinance info dict
    
    Args:
        info: yfinance info dictionary
        
    Returns:
        Dictionary with normalized financial data keys
    """
    return {
        'pe_ratio': info.get('trailingPE'),
        'forward_pe': info.get('forwardPE'),
        'peg_ratio': info.get('pegRatio'),
        'price_to_book': info.get('priceToBook'),
        'price_to_sales': info.get('priceToSalesTrailing12Months'),
        'dividend_yield': info.get('dividendYield'),
        'dividend_rate': info.get('dividendRate'),
        'payout_ratio': info.get('payoutRatio'),
        'eps': info.get('trailingEps'),
        'eps_forward': info.get('forwardEps'),
        'beta': info.get('beta'),
        '52_week_high': info.get('fiftyTwoWeekHigh'),
        '52_week_low': info.get('fiftyTwoWeekLow'),
        'book_value': info.get('bookValue'),
        'revenue_ttm': info.get('totalRevenue'),
        'profit_margin': info.get('profitMargins'),
        'operating_margin': info.get('operatingMargins'),
        'return_on_assets': info.get('returnOnAssets'),
        'return_on_equity': info.get('returnOnEquity'),
        'debt_to_equity': info.get('debtToEquity'),
        'current_ratio': info.get('currentRatio'),
    }


def convert_company_info_to_yfinance_format(cached_info: CompanyInfo, position: Optional[Position] = None) -> Dict[str, Any]:
    """
    Converteer CompanyInfo database record naar yfinance-achtig formaat
    
    Args:
        cached_info: CompanyInfo database record
        position: Optionele Position record voor sector
        
    Returns:
        Dictionary in yfinance formaat
    """
    # Gebruik sector uit positions als beschikbaar
    sector = position.pos_sector if position and position.pos_sector else cached_info.sector
    
    info = {
        'symbol': cached_info.ticker,
        'longName': cached_info.long_name or cached_info.name,
        'shortName': cached_info.name,
        'sector': sector,
        'industry': cached_info.industry,
        'country': cached_info.country,
        'longBusinessSummary': cached_info.description,
        'website': cached_info.website,
        'fullTimeEmployees': cached_info.employees,
        'marketCap': cached_info.market_cap,
        'currency': cached_info.currency,
        'exchange': cached_info.exchange,
    }
    
    # Voeg financial data toe
    if cached_info.financial_data:
        for db_key, yf_key in FINANCIAL_DATA_MAPPING.items():
            value = cached_info.financial_data.get(db_key)
            if value is not None:
                info[yf_key] = value
    
    return info


def get_company_info_from_cache(ticker_variants: List[str]) -> tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """
    Haal company info op uit database cache met efficiënte query
    
    Args:
        ticker_variants: Lijst van ticker varianten om te proberen
        
    Returns:
        Tuple van (info dict, position) of (None, None) als niet gevonden
    """
    if not ticker_variants:
        return None, None
    
    # Normaliseer alle varianten naar uppercase
    ticker_variants_upper = [t.upper() for t in ticker_variants]
    
    # Efficiënte query: probeer alle varianten in één query
    cached_info = db.session.query(CompanyInfo).filter(
        CompanyInfo.ticker.in_(ticker_variants_upper)
    ).first()
    
    # Als geen exact match, probeer case-insensitive
    if not cached_info:
        cached_info = db.session.query(CompanyInfo).filter(
            func.upper(CompanyInfo.ticker).in_(ticker_variants_upper)
        ).first()
    
    if not cached_info:
        return None, None
    
    # Haal position op voor sector (efficiënte query)
    position = db.session.query(Position).filter(
        or_(
            Position.pos_ticker.in_(ticker_variants_upper),
            Position.pos_name.in_(ticker_variants_upper)
        )
    ).first()
    
    # Converteer naar yfinance formaat
    info = convert_company_info_to_yfinance_format(cached_info, position)
    
    return info, position

