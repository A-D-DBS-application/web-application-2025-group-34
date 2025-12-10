"""
Risico-analyse module voor portfolio
Berekent VaR, volatility, correlation, diversification metrics, etc.
Inclusief geavanceerde Portefeuille Benchmark Vergelijking.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import yfinance as yf
import logging
from ..models import Position

# Configureer logging
logger = logging.getLogger(__name__)

# Mock Benchmark Portefeuilles
BENCHMARKS = {
    "Defensief (ETF Mix)": {
        "VTI": 0.30,  # Vanguard Total Stock Market ETF
        "VEA": 0.25,  # Vanguard FTSE Developed Markets ETF
        "BND": 0.25,  # Vanguard Total Bond Market ETF
        "GLD": 0.20   # SPDR Gold Shares
    },
    "Gebalanceerd (Global Index)": {
        "VTI": 0.40,  # Vanguard Total Stock Market ETF
        "VEA": 0.30,  # Vanguard FTSE Developed Markets ETF
        "VWO": 0.20,  # Vanguard FTSE Emerging Markets ETF
        "BND": 0.10   # Vanguard Total Bond Market ETF
    },
    "Agressief (Tech & Growth)": {
        "QQQ": 0.35,  # Invesco QQQ Trust (Nasdaq-100)
        "VUG": 0.25,  # Vanguard Growth ETF
        "ARKK": 0.20, # ARK Innovation ETF
        "VTI": 0.20   # Vanguard Total Stock Market ETF
    }
}


def normalize_ticker(ticker: str) -> str:
    """
    Normaliseer ticker voor yfinance.
    Converteert bijvoorbeeld BRK-B naar BRK-B (yfinance gebruikt -)
    en ADYEN.AS blijft ADYEN.AS
    """
    if not ticker:
        return ""
    # Verwijder whitespace
    ticker = ticker.strip().upper()
    # yfinance gebruikt - voor Berkshire, dus BRK-B is correct
    # Voor Europese beurzen zoals .AS, .L, etc. blijven we het behouden
    return ticker


class RiskAnalyzer:
    """Analyseer risico van het portfolio"""
    
    def __init__(self, positions: List[Position], cash_amount: float = 0.0, risk_free_rate: float = 0.02):
        """
        Args:
            positions: Lijst van Position objecten (exclusief cash)
            cash_amount: Cash bedrag in portfolio (EUR)
            risk_free_rate: Risicovrije rente (default 2% per jaar)
        """
        self.positions = positions or []
        self.cash_amount = float(cash_amount) if cash_amount else 0.0
        self.risk_free_rate = float(risk_free_rate)
    
    def calculate_portfolio_value(self) -> float:
        """Bereken totale portfolio waarde in EUR (inclusief cash)"""
        total = self.cash_amount
        for pos in self.positions:
            if pos and hasattr(pos, 'current_price') and hasattr(pos, 'pos_quantity'):
                if pos.current_price is not None and pos.pos_quantity is not None:
                    try:
                        total += float(pos.current_price) * int(pos.pos_quantity)
                    except (ValueError, TypeError):
                        continue
        return float(total)
    
    def calculate_position_value(self) -> float:
        """Bereken totale waarde van posities (exclusief cash)"""
        total = 0.0
        for pos in self.positions:
            if pos and hasattr(pos, 'current_price') and hasattr(pos, 'pos_quantity'):
                if pos.current_price is not None and pos.pos_quantity is not None:
                    try:
                        total += float(pos.current_price) * int(pos.pos_quantity)
                    except (ValueError, TypeError):
                        continue
        return float(total)
    
    def calculate_portfolio_weights(self) -> Dict[str, float]:
        """
        Bereken gewichten van elke positie in portfolio (inclusief cash)
        Returns: Dict met ticker als key en weight (0-1) als value
        """
        total_value = self.calculate_portfolio_value()
        if total_value == 0:
            return {}
        
        weights = {}
        # Cash gewicht
        if self.cash_amount > 0:
            weights['CASH'] = self.cash_amount / total_value
        
        # Positie gewichten
        for pos in self.positions:
            if not pos:
                continue
            ticker = None
            if hasattr(pos, 'pos_ticker') and pos.pos_ticker:
                ticker = normalize_ticker(str(pos.pos_ticker))
            elif hasattr(pos, 'pos_name') and pos.pos_name:
                ticker = normalize_ticker(str(pos.pos_name))
            
            if ticker and hasattr(pos, 'current_price') and hasattr(pos, 'pos_quantity'):
                if pos.current_price is not None and pos.pos_quantity is not None:
                    try:
                        position_value = float(pos.current_price) * int(pos.pos_quantity)
                        if position_value > 0:
                            weights[ticker] = position_value / total_value
                    except (ValueError, TypeError):
                        continue
        
        return weights
    
    def get_top_positions(self, top_n: int = 5) -> List[Dict]:
        """
        Haal top N posities op (gesorteerd op waarde)
        
        Returns:
            Lijst van dicts met positie informatie
        """
        position_data = []
        for pos in self.positions:
            if not pos:
                continue
            if not (hasattr(pos, 'current_price') and hasattr(pos, 'pos_quantity')):
                continue
            if pos.current_price is None or pos.pos_quantity is None:
                continue
            
            try:
                ticker = None
                if hasattr(pos, 'pos_ticker') and pos.pos_ticker:
                    ticker = str(pos.pos_ticker)
                elif hasattr(pos, 'pos_name') and pos.pos_name:
                    ticker = str(pos.pos_name)
                
                if not ticker:
                    continue
                
                value = float(pos.current_price) * int(pos.pos_quantity)
                position_data.append({
                    'ticker': ticker,
                    'name': str(pos.pos_name) if hasattr(pos, 'pos_name') and pos.pos_name else ticker,
                    'sector': str(pos.pos_sector) if hasattr(pos, 'pos_sector') and pos.pos_sector else 'Unknown',
                    'value': float(value),
                    'quantity': int(pos.pos_quantity),
                    'price': float(pos.current_price),
                    'weight': 0.0  # Wordt later berekend
                })
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Error processing position: {e}")
                continue
        
        # Sorteer op waarde (hoogste eerst)
        position_data.sort(key=lambda x: x['value'], reverse=True)
        
        # Bereken gewichten
        total_value = self.calculate_portfolio_value()
        for p in position_data:
            if total_value > 0:
                p['weight'] = (p['value'] / total_value) * 100
        
        return position_data[:top_n]
    
    def _get_returns_and_stats(self, weights: Dict[str, float], lookback_days: int = 252) -> Optional[Dict]:
        """
        Centrale helper functie om historische returns en statistieken te berekenen.
        
        Args:
            weights: Dict met ticker als key en weight (0-1) als value
            lookback_days: Aantal dagen terug voor historische data (default 252 = 1 jaar)
        
        Returns:
            Dict met:
                - 'returns': pandas Series met dagelijkse portfolio returns
                - 'annual_return': Geannualiseerd rendement (percentage)
                - 'volatility': Geannualiseerde volatiliteit (percentage)
                - 'sharpe_ratio': Sharpe ratio
            of None als data niet beschikbaar is
        """
        try:
            if not weights:
                return None
            
            # Exclude cash voor returns berekening
            position_weights = {k: v for k, v in weights.items() if k != 'CASH' and v > 0}
            
            if not position_weights:
                return None
            
            tickers = [normalize_ticker(t) for t in position_weights.keys() if normalize_ticker(t)]
            
            if not tickers:
                return None
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer voor weekends/holidays
            
            # Download historische data
            try:
                ticker_data = yf.download(
                    " ".join(tickers), 
                    start=start_date, 
                    end=end_date, 
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )
            except Exception as e:
                logger.warning(f"Error downloading ticker data: {e}")
                return None
            
            if ticker_data.empty:
                return None
            
            # Handle both single and multi-ticker responses
            if len(tickers) == 1:
                # Single ticker returns DataFrame with columns directly
                if 'Close' in ticker_data.columns:
                    prices = ticker_data['Close'].dropna()
                else:
                    prices = ticker_data.dropna()
            else:
                # Multi-ticker: check structure
                if isinstance(ticker_data.columns, pd.MultiIndex):
                    # MultiIndex columns
                    prices_dict = {}
                    for ticker in tickers:
                        if (ticker, 'Close') in ticker_data.columns:
                            prices_dict[ticker] = ticker_data[(ticker, 'Close')].dropna()
                        elif ticker in ticker_data.columns:
                            prices_dict[ticker] = ticker_data[ticker].dropna()
                    if not prices_dict:
                        return None
                else:
                    # Simple columns, try to match tickers
                    prices_dict = {}
                    for ticker in tickers:
                        if ticker in ticker_data.columns:
                            prices_dict[ticker] = ticker_data[ticker].dropna()
                    if not prices_dict:
                        return None
            
            # Bereken daily returns voor elke ticker
            returns = {}
            for ticker in tickers:
                if len(tickers) == 1:
                    if len(prices) > 1:
                        daily_returns = prices.pct_change().dropna()
                        if len(daily_returns) > 0:
                            returns[ticker] = daily_returns
                else:
                    if ticker in prices_dict and len(prices_dict[ticker]) > 1:
                        daily_returns = prices_dict[ticker].pct_change().dropna()
                        if len(daily_returns) > 0:
                            returns[ticker] = daily_returns
            
            if not returns:
                return None
            
            # Bereken portfolio returns (gewogen gemiddelde)
            portfolio_returns = None
            for ticker, ticker_returns in returns.items():
                weight = position_weights.get(ticker, 0)
                if weight <= 0:
                    continue
                
                if portfolio_returns is None:
                    portfolio_returns = ticker_returns * weight
                else:
                    # Align returns op datum
                    aligned_returns = ticker_returns.reindex(portfolio_returns.index).fillna(0)
                    portfolio_returns += aligned_returns * weight
            
            if portfolio_returns is None or len(portfolio_returns) == 0:
                return None
            
            # Bereken statistieken
            # Geannualiseerd rendement (gemiddelde dagelijkse return * 252)
            annual_return = portfolio_returns.mean() * 252 * 100  # Als percentage
            
            # Geannualiseerde volatiliteit (standaarddeviatie * sqrt(252))
            volatility = portfolio_returns.std() * np.sqrt(252) * 100  # Als percentage
            
            # Sharpe ratio = (Return - Risk-free rate) / Volatility
            sharpe_ratio = None
            if volatility > 0:
                sharpe_ratio = (annual_return - (self.risk_free_rate * 100)) / volatility
            
            return {
                'returns': portfolio_returns,
                'annual_return': float(annual_return),
                'volatility': float(volatility),
                'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio is not None else None
            }
            
        except Exception as e:
            logger.error(f"Error in _get_returns_and_stats: {e}", exc_info=True)
            return None
    
    def calculate_portfolio_volatility(self, lookback_days: int = 252) -> Optional[float]:
        """
        Bereken portfolio volatility (standaarddeviatie van returns)
        
        Args:
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Portfolio volatility (jaarlijks percentage) of None als data niet beschikbaar is
        """
        try:
            weights = self.calculate_portfolio_weights()
            if not weights:
                return None
            
            stats = self._get_returns_and_stats(weights, lookback_days)
            if stats is None:
                return None
            
            return stats['volatility']
            
        except Exception as e:
            logger.error(f"Error calculating portfolio volatility: {e}")
            return None
    
    def calculate_var(self, confidence_level: float = 0.95, lookback_days: int = 252) -> Optional[Dict[str, Any]]:
        """
        Bereken Value at Risk (VaR) voor portfolio
        
        Args:
            confidence_level: Confidence level (default 95%)
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Dict met 'var_absolute' (in EUR) en 'var_percentage' (als percentage) of None
        """
        try:
            # VaR wordt berekend op basis van position value (exclusief cash)
            # omdat cash geen volatiliteit heeft
            position_value = self.calculate_position_value()
            portfolio_value = self.calculate_portfolio_value()
            
            if position_value == 0 or portfolio_value == 0:
                return None
            
            # Gebruik _get_returns_and_stats voor volatiliteit
            weights = self.calculate_portfolio_weights()
            stats = self._get_returns_and_stats(weights, lookback_days)
            
            if stats is None or stats['volatility'] is None:
                return None
            
            volatility = stats['volatility']
            
            # VaR = position_value * volatility * z-score
            # Voor 95% confidence: z-score ≈ 1.645
            # Voor 99% confidence: z-score ≈ 2.326
            z_scores = {0.95: 1.645, 0.99: 2.326, 0.90: 1.282}
            z_score = z_scores.get(confidence_level, 1.645)
            
            # VaR als percentage van position value (1 dag)
            var_percentage = (volatility / np.sqrt(252)) * z_score
            
            # VaR in absolute waarde (EUR) - alleen op basis van positions
            var_absolute = position_value * (var_percentage / 100)
            
            # Percentage van totale portfolio (inclusief cash)
            var_percentage_of_portfolio = (var_absolute / portfolio_value * 100) if portfolio_value > 0 else 0
            
            return {
                'var_absolute': float(var_absolute),
                'var_percentage': float(var_percentage),
                'var_percentage_of_portfolio': float(var_percentage_of_portfolio),
                'confidence_level': float(confidence_level)
            }
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return None
    
    def calculate_diversification_score(self) -> Dict[str, Any]:
        """
        Bereken diversificatie metrics voor portfolio
        
        Returns:
            Dict met verschillende diversificatie metrics
        """
        weights = self.calculate_portfolio_weights()
        
        if not weights:
            return {
                'score': 0.0,
                'num_positions': 0,
                'sector_concentration': 1.0,
                'max_weight': 0.0,
                'sector_weights': {}
            }
        
        # Exclude cash from position count
        position_weights = {k: v for k, v in weights.items() if k != 'CASH'}
        num_positions = len(position_weights)
        
        # Maximum gewicht (concentratie risico)
        max_weight = max(position_weights.values()) if position_weights else 0.0
        
        # Sector concentratie (als sector data beschikbaar is)
        sector_weights = {}
        for pos in self.positions:
            if not pos:
                continue
            ticker = None
            if hasattr(pos, 'pos_ticker') and pos.pos_ticker:
                ticker = normalize_ticker(str(pos.pos_ticker))
            elif hasattr(pos, 'pos_name') and pos.pos_name:
                ticker = normalize_ticker(str(pos.pos_name))
            
            if ticker:
                sector = str(pos.pos_sector) if hasattr(pos, 'pos_sector') and pos.pos_sector else "Unknown"
                weight = position_weights.get(ticker, 0)
                sector_weights[sector] = sector_weights.get(sector, 0) + weight
        
        # Herfindahl-Hirschman Index voor sector concentratie
        # HHI = sum(weight^2), lager is beter (meer gediversifieerd)
        hhi = sum(w**2 for w in sector_weights.values()) if sector_weights else 1.0
        
        # Diversificatie score (0-100, hoger is beter)
        # Gebaseerd op aantal posities, max weight, en sector spreiding
        position_score = min(num_positions / 20.0, 1.0) * 40  # Max 40 punten voor posities
        concentration_score = (1 - max_weight) * 30  # Max 30 punten voor spreiding
        sector_score = (1 - min(hhi, 1.0)) * 30  # Max 30 punten voor sector diversificatie
        
        total_score = position_score + concentration_score + sector_score
        
        return {
            'score': round(float(total_score), 2),
            'num_positions': num_positions,
            'sector_concentration': round(float(hhi), 3),
            'max_weight': round(float(max_weight), 3),
            'sector_weights': {k: float(v) for k, v in sector_weights.items()}
        }
    
    def calculate_correlation_matrix(self, lookback_days: int = 252) -> Optional[Dict[str, Any]]:
        """
        Bereken correlatie matrix tussen posities
        
        Returns:
            Dict met correlatie data of None
        """
        try:
            weights = self.calculate_portfolio_weights()
            if not weights:
                return None
            
            # Exclude cash
            position_weights = {k: v for k, v in weights.items() if k != 'CASH' and v > 0}
            
            if len(position_weights) < 2:
                return None
            
            tickers = [normalize_ticker(t) for t in position_weights.keys() if normalize_ticker(t)]
            
            if len(tickers) < 2:
                return None
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)
            
            # Download historische data
            try:
                ticker_data = yf.download(
                    " ".join(tickers), 
                    start=start_date, 
                    end=end_date, 
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )
            except Exception as e:
                logger.warning(f"Error downloading ticker data for correlation: {e}")
                return None
            
            if ticker_data.empty:
                return None
            
            # Bereken correlatie matrix
            returns_data = {}
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        if 'Close' in ticker_data.columns:
                            prices = ticker_data['Close'].dropna()
                        else:
                            prices = ticker_data.dropna()
                    else:
                        if isinstance(ticker_data.columns, pd.MultiIndex):
                            if (ticker, 'Close') in ticker_data.columns:
                                prices = ticker_data[(ticker, 'Close')].dropna()
                            elif ticker in ticker_data.columns:
                                prices = ticker_data[ticker].dropna()
                            else:
                                continue
                        else:
                            if ticker in ticker_data.columns:
                                prices = ticker_data[ticker].dropna()
                            else:
                                continue
                    
                    if len(prices) > 1:
                        returns = prices.pct_change().dropna()
                        if len(returns) > 0:
                            returns_data[ticker] = returns
                except Exception as e:
                    logger.debug(f"Error processing ticker {ticker} for correlation: {e}")
                    continue
            
            if len(returns_data) < 2:
                return None
            
            # Maak DataFrame van returns
            returns_df = pd.DataFrame(returns_data)
            returns_df = returns_df.dropna()
            
            if len(returns_df) < 10:  # Minimaal 10 datapunten nodig
                return None
            
            # Bereken correlatie matrix
            correlation_matrix = returns_df.corr()
            
            # Gemiddelde correlatie (hoe lager, hoe beter gediversifieerd)
            # Exclude diagonal (1.0)
            mask = np.triu(np.ones_like(correlation_matrix.values), k=1).astype(bool)
            avg_correlation = correlation_matrix.values[mask].mean()
            
            # Convert to dict for JSON serialization
            matrix_dict = {}
            for idx, ticker1 in enumerate(correlation_matrix.index):
                matrix_dict[ticker1] = {}
                for ticker2 in correlation_matrix.columns:
                    matrix_dict[ticker1][ticker2] = float(correlation_matrix.loc[ticker1, ticker2])
            
            return {
                'matrix': matrix_dict,
                'average_correlation': round(float(avg_correlation), 3),
                'tickers': list(correlation_matrix.index)
            }
            
        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}", exc_info=True)
            return None
    
    def calculate_sharpe_ratio(self, lookback_days: int = 252) -> Optional[float]:
        """
        Bereken Sharpe ratio voor portfolio
        
        Args:
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Sharpe ratio of None
        """
        try:
            weights = self.calculate_portfolio_weights()
            if not weights:
                return None
            
            stats = self._get_returns_and_stats(weights, lookback_days)
            if stats is None:
                return None
            
            return stats['sharpe_ratio']
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return None
    
    def calculate_position_volatilities(self, lookback_days: int = 252) -> Dict[str, float]:
        """
        Bereken volatiliteit voor elke individuele positie
        
        Returns:
            Dict met ticker als key en volatiliteit (jaarlijks %) als value
        """
        volatilities = {}
        try:
            tickers = []
            for pos in self.positions:
                if not pos:
                    continue
                ticker = None
                if hasattr(pos, 'pos_ticker') and pos.pos_ticker:
                    ticker = normalize_ticker(str(pos.pos_ticker))
                elif hasattr(pos, 'pos_name') and pos.pos_name:
                    ticker = normalize_ticker(str(pos.pos_name))
                
                if ticker:
                    tickers.append(ticker)
            
            if not tickers:
                return {}
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)
            
            # Download historische data
            try:
                ticker_data = yf.download(
                    " ".join(tickers), 
                    start=start_date, 
                    end=end_date, 
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )
            except Exception as e:
                logger.warning(f"Error downloading ticker data for volatilities: {e}")
                return {}
            
            if ticker_data.empty:
                return {}
            
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        if 'Close' in ticker_data.columns:
                            prices = ticker_data['Close'].dropna()
                        else:
                            prices = ticker_data.dropna()
                    else:
                        if isinstance(ticker_data.columns, pd.MultiIndex):
                            if (ticker, 'Close') in ticker_data.columns:
                                prices = ticker_data[(ticker, 'Close')].dropna()
                            elif ticker in ticker_data.columns:
                                prices = ticker_data[ticker].dropna()
                            else:
                                continue
                        else:
                            if ticker in ticker_data.columns:
                                prices = ticker_data[ticker].dropna()
                            else:
                                continue
                    
                    if len(prices) > 1:
                        returns = prices.pct_change().dropna()
                        if len(returns) > 0:
                            volatility = returns.std() * np.sqrt(252) * 100
                            volatilities[ticker] = float(volatility)
                except Exception as e:
                    logger.debug(f"Error calculating volatility for {ticker}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error calculating position volatilities: {e}")
        
        return volatilities
    
    def compare_with_benchmarks(self) -> List[Dict[str, Any]]:
        """
        Vergelijk huidige VEK portefeuille met drie benchmark portefeuilles.
        
        Returns:
            Lijst van dictionaries met benchmark vergelijkingen, gesorteerd op Sharpe Ratio (aflopend).
            Elke dict bevat:
                - 'name': Naam van de portefeuille
                - 'annual_return': Geannualiseerd rendement (%)
                - 'volatility': Geannualiseerde volatiliteit (%)
                - 'sharpe_ratio': Sharpe ratio
        """
        results = []
        
        # 1. Huidige VEK Portefeuille (1 jaar lookback)
        try:
            vek_weights = self.calculate_portfolio_weights()
            if vek_weights:
                vek_stats = self._get_returns_and_stats(vek_weights, lookback_days=252)
                
                if vek_stats:
                    results.append({
                        'name': 'Huidige VEK Portefeuille',
                        'annual_return': round(vek_stats['annual_return'], 2),
                        'volatility': round(vek_stats['volatility'], 2),
                        'sharpe_ratio': round(vek_stats['sharpe_ratio'], 3) if vek_stats['sharpe_ratio'] is not None else None
                    })
        except Exception as e:
            logger.error(f"Error calculating VEK portfolio stats: {e}")
        
        # 2. Benchmark Portefeuilles
        for benchmark_name, benchmark_weights in BENCHMARKS.items():
            try:
                benchmark_stats = self._get_returns_and_stats(benchmark_weights, lookback_days=252)
                
                if benchmark_stats:
                    results.append({
                        'name': benchmark_name,
                        'annual_return': round(benchmark_stats['annual_return'], 2),
                        'volatility': round(benchmark_stats['volatility'], 2),
                        'sharpe_ratio': round(benchmark_stats['sharpe_ratio'], 3) if benchmark_stats['sharpe_ratio'] is not None else None
                    })
            except Exception as e:
                logger.error(f"Error calculating benchmark stats for {benchmark_name}: {e}")
        
        # Sorteer op Sharpe Ratio (aflopend), None waarden naar achteren
        results.sort(
            key=lambda x: x['sharpe_ratio'] if x['sharpe_ratio'] is not None else float('-inf'), 
            reverse=True
        )
        
        return results
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Genereer complete risico samenvatting inclusief benchmark vergelijkingen
        
        Returns:
            Dict met alle risico metrics en benchmark vergelijkingen
        """
        try:
            portfolio_value = self.calculate_portfolio_value()
            position_value = self.calculate_position_value()
            weights = self.calculate_portfolio_weights()
            volatility = self.calculate_portfolio_volatility(lookback_days=252)
            var_95 = self.calculate_var(confidence_level=0.95, lookback_days=252)
            var_99 = self.calculate_var(confidence_level=0.99, lookback_days=252)
            diversification = self.calculate_diversification_score()
            correlation = self.calculate_correlation_matrix(lookback_days=252)
            top_positions = self.get_top_positions(top_n=5)
            position_volatilities = self.calculate_position_volatilities(lookback_days=252)
            sharpe_ratio = self.calculate_sharpe_ratio(lookback_days=252)
            
            # Benchmark vergelijkingen
            benchmark_comparison = self.compare_with_benchmarks()
            
            # Cash percentage
            cash_percentage = (self.cash_amount / portfolio_value * 100) if portfolio_value > 0 else 0
            
            return {
                'portfolio_value': float(portfolio_value),
                'position_value': float(position_value),
                'cash_amount': float(self.cash_amount),
                'cash_percentage': round(float(cash_percentage), 2),
                'num_positions': len([w for w in weights.keys() if w != 'CASH']),
                'volatility': float(volatility) if volatility is not None else None,
                'var_95': var_95,
                'var_99': var_99,
                'diversification': diversification,
                'correlation': correlation,
                'risk_level': self._assess_risk_level(volatility, diversification, var_95),
                'top_positions': top_positions,
                'position_volatilities': position_volatilities,
                'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio is not None else None,
                'benchmark_comparison': benchmark_comparison
            }
        except Exception as e:
            logger.error(f"Error generating risk summary: {e}", exc_info=True)
            # Return minimal summary on error
            return {
                'portfolio_value': float(self.calculate_portfolio_value()),
                'position_value': float(self.calculate_position_value()),
                'cash_amount': float(self.cash_amount),
                'cash_percentage': 0.0,
                'num_positions': 0,
                'volatility': None,
                'var_95': None,
                'var_99': None,
                'diversification': {'score': 0.0, 'num_positions': 0, 'sector_concentration': 1.0, 'max_weight': 0.0, 'sector_weights': {}},
                'correlation': None,
                'risk_level': 'Unknown',
                'top_positions': [],
                'position_volatilities': {},
                'sharpe_ratio': None,
                'benchmark_comparison': []
            }
    
    def _assess_risk_level(self, volatility: Optional[float], diversification: Dict, var_95: Optional[Dict]) -> str:
        """Assesseer algemeen risico niveau"""
        if volatility is None:
            return "Unknown"
        
        risk_score = 0
        
        # Volatility component
        if volatility < 10:
            risk_score += 1
        elif volatility < 20:
            risk_score += 2
        else:
            risk_score += 3
        
        # Diversification component
        div_score = diversification.get('score', 0)
        if div_score < 40:
            risk_score += 3
        elif div_score < 70:
            risk_score += 2
        else:
            risk_score += 1
        
        # VaR component
        if var_95:
            var_pct = var_95.get('var_percentage', 0)
            if var_pct > 3:
                risk_score += 3
            elif var_pct > 1.5:
                risk_score += 2
            else:
                risk_score += 1
        
        # Bepaal risico niveau
        if risk_score <= 3:
            return "Low"
        elif risk_score <= 6:
            return "Medium"
        else:
            return "High"
