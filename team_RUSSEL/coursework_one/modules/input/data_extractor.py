"""
Data extraction module for financial data.
Value Factor: Extract P/E, P/B, Market Cap, and related metrics.
"""
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts financial data for companies using Value Factor metrics."""
    
    def __init__(self, config: dict):
        """
        Initialize data extractor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.lookback_years = config['extraction']['lookback_years']
    
    def extract_company_data(self, company: dict) -> pd.DataFrame:
        """
        Extract Value Factor data for a single company.
        
        Value Factor Metrics:
        - Price-to-Earnings (P/E) ratio
        - Price-to-Book (P/B) ratio
        - Market Capitalization
        - Book Value per Share
        - Earnings per Share (EPS)
        - Current Price
        
        Args:
            company: Company dictionary with id, ticker, name
            
        Returns:
            DataFrame with extracted data
        """
        ticker = company['ticker']
        
        try:
            # Create yfinance ticker object
            stock = yf.Ticker(ticker)
            
            # Get company info
            info = stock.info
            
            # Get current date
            current_date = datetime.now()
            
            # Extract Value Factor metrics
            data = {
               'company_id': company['ticker'],
                'ticker': ticker,
                'company_name': company['name'],
                'date': current_date.strftime('%Y-%m-%d'),
                
                # Price metrics
                'current_price': info.get('currentPrice', None),
                'market_cap': info.get('marketCap', None),
                
                # VALUE Factor metrics
                'pe_ratio': info.get('trailingPE', None),
                'forward_pe': info.get('forwardPE', None),
                'pb_ratio': info.get('priceToBook', None),
                'ps_ratio': info.get('priceToSalesTrailing12Months', None),
                'book_value': info.get('bookValue', None),
                'eps': info.get('trailingEps', None),
                'forward_eps': info.get('forwardEps', None),
                'enterprise_value': info.get('enterpriseValue', None),
                'ev_to_ebitda': info.get('enterpriseToEbitda', None),
                'ev_to_revenue': info.get('enterpriseToRevenue', None),
                
                # QUALITY Factor metrics
                'roe': info.get('returnOnEquity', None),
                'roa': info.get('returnOnAssets', None),
                'debt_to_equity': info.get('debtToEquity', None),
                'current_ratio': info.get('currentRatio', None),
                'quick_ratio': info.get('quickRatio', None),
                'profit_margin': info.get('profitMargins', None),
                'operating_margin': info.get('operatingMargins', None),
                'gross_margin': info.get('grossMargins', None),
                'free_cash_flow': info.get('freeCashflow', None),
                'operating_cash_flow': info.get('operatingCashflow', None),
                'revenue_growth': info.get('revenueGrowth', None),
                'earnings_growth': info.get('earningsGrowth', None),
                
                # Additional fundamentals
                'revenue': info.get('totalRevenue', None),
                'total_debt': info.get('totalDebt', None),
                'total_cash': info.get('totalCash', None),
                'ebitda': info.get('ebitda', None),
                'dividend_yield': info.get('dividendYield', None),
                
                # Sector info (from DB + yfinance for comparison)
                'sector': info.get('sector', None),
                'industry': info.get('industry', None),
                'db_sector': company.get('gics_sector', None),
                'db_industry': company.get('gics_industry', None),
            }
            
            logger.info(f"✅ Successfully extracted data for {ticker}")
            return pd.DataFrame([data])
            
        except Exception as e:
            logger.error(f"❌ Failed to extract {ticker}: {e}")
            # Return empty row with company info to maintain record
            return pd.DataFrame([{
                'company_id': company['ticker'],
                'ticker': ticker,
                'company_name': company['name'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'error': str(e)
            }])
    
    def extract_historical_data(self, company: dict) -> pd.DataFrame:
        """Extract historical price data..."""
        ticker = company['ticker']
        try:
            from dateutil.relativedelta import relativedelta

            end_date = datetime.now()
            start_date = end_date - relativedelta(years=self.lookback_years)

            stock = yf.Ticker(ticker)

            # Filter US stocks only (only skip when currency explicitly present and not USD)
            info = stock.info
            currency = None
            if hasattr(info, 'get'):
                currency = info.get('currency', None)
            # Only skip when currency is a real string and explicitly not USD
            if isinstance(currency, str) and currency != 'USD':
                logger.info(f"⏭️  Skipping {ticker} - not a US stock")
                return pd.DataFrame()

            hist = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1mo'
            )

            if hist.empty:
                return pd.DataFrame()

            hist['company_id'] = company['ticker']
            hist['ticker'] = ticker
            hist['company_name'] = company['name']

            hist = hist.reset_index()

            # Convert Date index to date strings (keep month snapshots)
            hist['date'] = pd.to_datetime(hist['Date']).dt.strftime('%Y-%m-%d')

            # Add current fundamentals to most recent row only
            hist['pe_ratio'] = None
            hist['pb_ratio'] = None
            hist['market_cap'] = None
            hist['eps'] = None

            # Populate latest row with current fundamentals
            latest_idx = hist.index[-1]
            def _safe_val(key):
                val = None
                if hasattr(info, 'get'):
                    try:
                        val = info.get(key, None)
                    except Exception:
                        val = None
                else:
                    val = getattr(info, key, None)
                if isinstance(val, (int, float, str)) or val is None:
                    return val
                return None

            hist.loc[latest_idx, 'pe_ratio'] = _safe_val('trailingPE')
            hist.loc[latest_idx, 'pb_ratio'] = _safe_val('priceToBook')
            hist.loc[latest_idx, 'market_cap'] = _safe_val('marketCap')
            hist.loc[latest_idx, 'eps'] = _safe_val('trailingEps')

            hist = hist[['company_id', 'ticker', 'company_name', 'date',
                         'Open', 'High', 'Low', 'Close', 'Volume',
                         'pe_ratio', 'pb_ratio', 'market_cap', 'eps']]

            logger.info(f"✅ Extracted {len(hist)} historical records for {ticker}")
            return hist

        except Exception as e:
            logger.exception(f"❌ Failed to extract historical data for {ticker}: {e}")
            return pd.DataFrame()
    
    def extract_bulk_data(self, companies: List[dict]) -> pd.DataFrame:
        """
        Extract current Value Factor data for multiple companies.
        
        Args:
            companies: List of company dictionaries
            
        Returns:
            DataFrame with all extracted data
        """
        all_data = []
        
        for company in companies:
            df = self.extract_company_data(company)
            all_data.append(df)
            print(f"✅ Extracted data for {company['ticker']}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def extract_bulk_historical_data(self, companies: List[dict]) -> pd.DataFrame:
        """
        Extract historical data for multiple companies.
        
        Args:
            companies: List of company dictionaries
            
        Returns:
            DataFrame with all historical data
        """
        all_data = []
        
        for company in companies:
            df = self.extract_historical_data(company)
            if not df.empty:
                all_data.append(df)
                print(f"✅ Extracted historical data for {company['ticker']}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()