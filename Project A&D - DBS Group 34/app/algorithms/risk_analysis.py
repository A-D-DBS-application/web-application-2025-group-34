"""
Risico-analyse module voor portfolio
Berekent VaR, volatility, diversification metrics, stress testing, en benchmark vergelijkingen.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import yfinance as yf
import logging
from ..models import Position
from ..utils import normalize_ticker_for_yfinance

# Configureer logging
logger = logging.getLogger(__name__)

# Note: requests_cache wordt geïnitialiseerd in routes.py en jobs.py
# Dit voorkomt rate limiting bij Yahoo Finance API calls
# De cache werkt globaal voor alle HTTP requests inclusief yfinance

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
    Gebruikt de gedeelde normalize_ticker_for_yfinance functie uit utils.
    """
    return normalize_ticker_for_yfinance(ticker, return_variants=False)


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
            
            # Haal historische prijzen op via Yahoo Finance API
            prices_dict = {}
            try:
                ticker_data = yf.download(
                    " ".join(tickers), 
                    start=start_date, 
                    end=end_date, 
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )
                
                if not ticker_data.empty:
                    # Verwerk yfinance data
                    for ticker in tickers:
                        if len(tickers) == 1:
                            # Single ticker
                            if 'Close' in ticker_data.columns:
                                prices_dict[ticker] = ticker_data['Close'].dropna()
                            else:
                                prices_dict[ticker] = ticker_data.dropna()
                        else:
                            # Multi-ticker
                            if isinstance(ticker_data.columns, pd.MultiIndex):
                                if (ticker, 'Close') in ticker_data.columns:
                                    prices_dict[ticker] = ticker_data[(ticker, 'Close')].dropna()
                                elif ticker in ticker_data.columns:
                                    prices_dict[ticker] = ticker_data[ticker].dropna()
                            else:
                                if ticker in ticker_data.columns:
                                    prices_dict[ticker] = ticker_data[ticker].dropna()
            except Exception as e:
                logger.warning(f"Error downloading ticker data from Yahoo Finance: {e}")
            
            if not prices_dict:
                return None
            
            # prices_dict is nu al gevuld (uit database of yfinance)
            
            # Bereken daily returns voor elke ticker
            returns = {}
            for ticker in tickers:
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
        Bereken vereenvoudigde diversificatie metrics voor portfolio
        (Sector spreiding wordt al getoond in portfolio tabblad)
        
        Returns:
            Dict met diversificatie metrics
        """
        weights = self.calculate_portfolio_weights()
        
        if not weights:
            return {
                'score': 0.0,
                'num_positions': 0,
                'max_weight': 0.0
            }
        
        # Exclude cash from position count
        position_weights = {k: v for k, v in weights.items() if k != 'CASH'}
        num_positions = len(position_weights)
        
        # Maximum gewicht (concentratie risico)
        max_weight = max(position_weights.values()) if position_weights else 0.0
        
        # Vereenvoudigde diversificatie score (0-100)
        # Gebaseerd op aantal posities en max weight (sector spreiding al in portfolio tabblad)
        position_score = min(num_positions / 15.0, 1.0) * 50  # Max 50 punten voor posities
        concentration_score = (1 - max_weight) * 50  # Max 50 punten voor spreiding
        
        total_score = position_score + concentration_score
        
        return {
            'score': round(float(total_score), 2),
            'num_positions': num_positions,
            'max_weight': round(float(max_weight), 3)
        }
    
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
    
    def calculate_maximum_drawdown(self, lookback_days: int = 252) -> Optional[Dict[str, Any]]:
        """
        Bereken Maximum Drawdown (MDD) voor portfolio
        MDD is de grootste daling van piek naar dal in de periode
        
        Args:
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Dict met 'mdd_percentage', 'mdd_absolute', 'peak_date', 'trough_date' of None
        """
        stats = self._get_returns_and_stats(self.calculate_portfolio_weights(), lookback_days)
        if not stats or stats['returns'] is None:
            return None
        
        returns = stats['returns']
        
        # Bereken cumulatieve returns (portfolio waarde over tijd)
        cumulative_returns = (1 + returns).cumprod()
        
        # Bereken running maximum (peak)
        running_max = cumulative_returns.expanding().max()
        
        # Bereken drawdown (percentage daling vanaf peak)
        drawdown = (cumulative_returns - running_max) / running_max * 100
        
        # Maximum drawdown
        max_drawdown = drawdown.min()
        
        # Vind datum van peak en trough
        trough_idx = drawdown.idxmin()
        peak_idx = running_max[:trough_idx].idxmax() if trough_idx is not None else None
        
        # Bereken absolute MDD in EUR
        portfolio_value = self.calculate_portfolio_value()
        mdd_absolute = portfolio_value * (abs(max_drawdown) / 100) if max_drawdown < 0 else 0
        
        return {
            'mdd_percentage': round(float(max_drawdown), 2),
            'mdd_absolute': round(float(mdd_absolute), 2),
            'peak_date': peak_idx.strftime('%Y-%m-%d') if peak_idx is not None else None,
            'trough_date': trough_idx.strftime('%Y-%m-%d') if trough_idx is not None else None
        }
    
    def calculate_conditional_var(self, confidence_level: float = 0.95, lookback_days: int = 252) -> Optional[Dict[str, Any]]:
        """
        Bereken Conditional Value at Risk (CVaR) / Expected Shortfall
        CVaR is de verwachte verlies GEGEVEN dat VaR wordt overschreden
        
        Args:
            confidence_level: Confidence level (default 0.95 = 95%)
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Dict met 'cvar_percentage', 'cvar_absolute' of None
        """
        stats = self._get_returns_and_stats(self.calculate_portfolio_weights(), lookback_days)
        if not stats or stats['returns'] is None:
            return None
        
        returns = stats['returns']
        portfolio_value = self.calculate_portfolio_value()
        
        # Bereken VaR threshold (percentiel)
        var_threshold = returns.quantile(1 - confidence_level)
        
        # CVaR = gemiddelde van alle returns die erger zijn dan VaR threshold
        tail_returns = returns[returns <= var_threshold]
        
        if len(tail_returns) == 0:
            return None
        
        # CVaR als percentage (negatief omdat het verlies is)
        cvar_percentage = abs(tail_returns.mean()) * np.sqrt(252) * 100
        
        # CVaR in absolute waarde (EUR)
        cvar_absolute = portfolio_value * (cvar_percentage / 100)
        
        return {
            'cvar_percentage': round(float(cvar_percentage), 2),
            'cvar_absolute': round(float(cvar_absolute), 2),
            'confidence_level': confidence_level
        }
    
    def calculate_portfolio_beta(self, benchmark_ticker: str = "SPY", lookback_days: int = 252) -> Optional[float]:
        """
        Bereken portfolio beta t.o.v. benchmark (default S&P 500)
        Beta meet hoe gevoelig portfolio is voor marktbewegingen
        
        Args:
            benchmark_ticker: Benchmark ticker (default "SPY" voor S&P 500)
            lookback_days: Aantal dagen terug voor historische data
        
        Returns:
            Beta waarde of None
        """
        stats = self._get_returns_and_stats(self.calculate_portfolio_weights(), lookback_days)
        if not stats or stats['returns'] is None:
            return None
        
        portfolio_returns = stats['returns']
        
        # Haal benchmark returns op
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)
            
            benchmark_data = yf.download(
                benchmark_ticker,
                start=start_date,
                end=end_date,
                progress=False
            )
            
            if benchmark_data.empty:
                return None
            
            # Handle both single column and multi-column DataFrames
            # Ensure we get a 1D Series, not a 2D DataFrame
            if 'Close' in benchmark_data.columns:
                benchmark_prices = benchmark_data['Close']
                # If it's still a DataFrame (MultiIndex), get the first column
                if isinstance(benchmark_prices, pd.DataFrame):
                    benchmark_prices = benchmark_prices.iloc[:, 0]
                # Ensure it's a Series
                if not isinstance(benchmark_prices, pd.Series):
                    benchmark_prices = pd.Series(benchmark_prices.values.flatten(), index=benchmark_data.index)
            elif len(benchmark_data.columns) == 1:
                benchmark_prices = benchmark_data.iloc[:, 0]
                # Ensure it's a Series
                if not isinstance(benchmark_prices, pd.Series):
                    benchmark_prices = pd.Series(benchmark_prices.values.flatten(), index=benchmark_data.index)
            else:
                return None
            
            # Ensure benchmark_prices is 1D
            if isinstance(benchmark_prices, pd.DataFrame):
                benchmark_prices = benchmark_prices.iloc[:, 0]
            if hasattr(benchmark_prices, 'values') and len(benchmark_prices.values.shape) > 1:
                benchmark_prices = pd.Series(benchmark_prices.values.flatten(), index=benchmark_prices.index)
            
            benchmark_returns = benchmark_prices.pct_change().dropna()
            
            # Align portfolio en benchmark returns op datum
            aligned_returns = pd.DataFrame({
                'portfolio': portfolio_returns,
                'benchmark': benchmark_returns
            }).dropna()
            
            if len(aligned_returns) < 10:
                return None
            
            # Beta = cov(portfolio, benchmark) / var(benchmark)
            covariance = aligned_returns['portfolio'].cov(aligned_returns['benchmark'])
            benchmark_variance = aligned_returns['benchmark'].var()
            
            if benchmark_variance == 0:
                return None
            
            beta = covariance / benchmark_variance
            
            return float(beta)
            
        except Exception as e:
            logger.warning(f"Error calculating portfolio beta: {e}")
            return None
    
    def calculate_stress_test(self) -> Dict[str, Any]:
        """
        Voer stress test uit met verschillende scenario's
        Simuleert impact van markt crashes en extreme events op portfolio
        
        Returns:
            Dict met stress test resultaten voor verschillende scenario's
        """
        try:
            portfolio_value = self.calculate_portfolio_value()
            position_value = self.calculate_position_value()
            weights = self.calculate_portfolio_weights()
            position_weights = {k: v for k, v in weights.items() if k != 'CASH' and v > 0}
            
            if not position_weights:
                return {
                    'scenarios': [],
                    'total_portfolio_value': float(portfolio_value),
                    'total_position_value': float(position_value)
                }
            
            scenarios = []
            
            # Scenario 1: Algemene markt crash (-10%, -20%, -30%)
            for crash_percentage in [10, 20, 30]:
                # Bereken nieuwe position value na crash
                scenario_position_value = position_value * (1 - crash_percentage / 100)
                # Totale portfolio waarde = nieuwe position value + cash (cash blijft onveranderd)
                total_value = scenario_position_value + self.cash_amount
                # Verlies = verschil tussen oude en nieuwe portfolio waarde
                loss_absolute = portfolio_value - total_value
                # Verlies percentage van totale portfolio waarde
                loss_percentage = (loss_absolute / portfolio_value * 100) if portfolio_value > 0 else 0
                
                scenarios.append({
                    'name': f'Market Crash -{crash_percentage}%',
                    'description': f'Simuleert een algemene marktcrash van {crash_percentage}%',
                    'position_value_after': round(float(scenario_position_value), 2),
                    'total_value_after': round(float(total_value), 2),
                    'loss_absolute': round(float(loss_absolute), 2),
                    'loss_percentage': round(float(loss_percentage), 2),
                    'cash_impact': 'Cash blijft onveranderd',
                    'severity': 'High' if crash_percentage >= 20 else 'Medium'
                })
            
            # Scenario 2: Tech sector crash (-25%)
            tech_tickers = []
            tech_weight = 0.0
            for pos in self.positions:
                if not pos:
                    continue
                ticker = None
                if hasattr(pos, 'pos_ticker') and pos.pos_ticker:
                    ticker = normalize_ticker(str(pos.pos_ticker))
                elif hasattr(pos, 'pos_name') and pos.pos_name:
                    ticker = normalize_ticker(str(pos.pos_name))
                
                if ticker and ticker in position_weights:
                    sector = str(pos.pos_sector) if hasattr(pos, 'pos_sector') and pos.pos_sector else "Unknown"
                    # Tech sector keywords (kan uitgebreid worden)
                    if any(keyword in sector.lower() for keyword in ['tech', 'technology', 'software', 'semiconductor']):
                        tech_weight += position_weights.get(ticker, 0)
                        tech_tickers.append(ticker)
            
            if tech_weight > 0:
                tech_crash_percentage = 25
                # Verlies alleen op tech posities
                tech_loss = position_value * tech_weight * (tech_crash_percentage / 100)
                # Nieuwe position value = oude value - tech loss
                scenario_position_value = position_value - tech_loss
                # Totale portfolio waarde = nieuwe position value + cash
                total_value = scenario_position_value + self.cash_amount
                # Verlies = verschil tussen oude en nieuwe portfolio waarde
                loss_absolute = portfolio_value - total_value
                loss_percentage = (loss_absolute / portfolio_value * 100) if portfolio_value > 0 else 0
                
                scenarios.append({
                    'name': f'Tech Sector Crash -{tech_crash_percentage}%',
                    'description': f'Simuleert een tech sector crash van {tech_crash_percentage}% (impact: {tech_weight*100:.1f}% van portfolio)',
                    'position_value_after': round(float(scenario_position_value), 2),
                    'total_value_after': round(float(total_value), 2),
                    'loss_absolute': round(float(loss_absolute), 2),
                    'loss_percentage': round(float(loss_percentage), 2),
                    'cash_impact': 'Cash blijft onveranderd',
                    'severity': 'High',
                    'affected_positions': len(tech_tickers)
                })
            
            # Scenario 3: Volatility spike (2x volatiliteit)
            volatility = self.calculate_portfolio_volatility(lookback_days=252)
            if volatility is not None:
                # Bij 2x volatiliteit, veronderstel een 1.5x standaarddeviatie move (ongeveer 95% VaR)
                volatility_multiplier = 2.0
                stress_volatility = volatility * volatility_multiplier
                # Gebruik VaR-achtige berekening: 1.645 * volatility (95% confidence)
                stress_move = (stress_volatility / np.sqrt(252)) * 1.645  # 1-day move
                stress_percentage = abs(stress_move)
                
                # Nieuwe position value na volatility spike
                scenario_position_value = position_value * (1 - stress_percentage / 100)
                # Totale portfolio waarde = nieuwe position value + cash
                total_value = scenario_position_value + self.cash_amount
                # Verlies = verschil tussen oude en nieuwe portfolio waarde
                loss_absolute = portfolio_value - total_value
                loss_percentage = (loss_absolute / portfolio_value * 100) if portfolio_value > 0 else 0
                
                scenarios.append({
                    'name': f'Volatility Spike (2x)',
                    'description': f'Simuleert een volatiliteitsspike waarbij portfolio volatiliteit verdubbelt naar {stress_volatility:.1f}%',
                    'position_value_after': round(float(scenario_position_value), 2),
                    'total_value_after': round(float(total_value), 2),
                    'loss_absolute': round(float(loss_absolute), 2),
                    'loss_percentage': round(float(loss_percentage), 2),
                    'cash_impact': 'Cash blijft onveranderd',
                    'severity': 'Medium',
                    'volatility_after': round(float(stress_volatility), 2)
                })
            
            # Scenario 4: Worst case (combineert -30% crash + volatility spike)
            worst_case_percentage = 35  # Conservatieve worst case
            # Nieuwe position value na worst case
            scenario_position_value = position_value * (1 - worst_case_percentage / 100)
            # Totale portfolio waarde = nieuwe position value + cash
            total_value = scenario_position_value + self.cash_amount
            # Verlies = verschil tussen oude en nieuwe portfolio waarde
            loss_absolute = portfolio_value - total_value
            loss_percentage = (loss_absolute / portfolio_value * 100) if portfolio_value > 0 else 0
            
            scenarios.append({
                'name': 'Worst Case Scenario',
                'description': f'Conservatieve worst case combinatie: -{worst_case_percentage}% marktcrash + extreme volatiliteit',
                'position_value_after': round(float(scenario_position_value), 2),
                'total_value_after': round(float(total_value), 2),
                'loss_absolute': round(float(loss_absolute), 2),
                'loss_percentage': round(float(loss_percentage), 2),
                'cash_impact': 'Cash blijft onveranderd',
                'severity': 'Critical'
            })
            
            # Sorteer scenarios op severity en loss percentage
            severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
            scenarios.sort(key=lambda x: (severity_order.get(x.get('severity', 'Low'), 3), -x.get('loss_percentage', 0)))
            
            return {
                'scenarios': scenarios,
                'total_portfolio_value': round(float(portfolio_value), 2),
                'total_position_value': round(float(position_value), 2),
                'cash_amount': round(float(self.cash_amount), 2),
                'num_positions': len(position_weights)
            }
            
        except Exception as e:
            logger.error(f"Error calculating stress test: {e}", exc_info=True)
            return {
                'scenarios': [],
                'total_portfolio_value': float(self.calculate_portfolio_value()),
                'total_position_value': float(self.calculate_position_value()),
                'cash_amount': float(self.cash_amount),
                'num_positions': 0
            }
    
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
            sharpe_ratio = self.calculate_sharpe_ratio(lookback_days=252)
            max_drawdown = self.calculate_maximum_drawdown(lookback_days=252)
            cvar_95 = self.calculate_conditional_var(confidence_level=0.95, lookback_days=252)
            portfolio_beta = self.calculate_portfolio_beta(lookback_days=252)
            stress_test = self.calculate_stress_test()
            
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
                'risk_level': self._assess_risk_level(volatility, diversification, var_95),
                'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio is not None else None,
                'max_drawdown': max_drawdown,
                'cvar_95': cvar_95,
                'portfolio_beta': float(portfolio_beta) if portfolio_beta is not None else None,
                'stress_test': stress_test,
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
                'diversification': {'score': 0.0, 'num_positions': 0, 'max_weight': 0.0},
                'risk_level': 'Unknown',
                'sharpe_ratio': None,
                'max_drawdown': None,
                'cvar_95': None,
                'portfolio_beta': None,
                'stress_test': {'scenarios': [], 'total_portfolio_value': 0, 'total_position_value': 0, 'cash_amount': 0, 'num_positions': 0},
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
