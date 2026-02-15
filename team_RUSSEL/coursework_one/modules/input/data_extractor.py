"""
Data extraction module for financial data.
"""
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict
import requests


class DataExtractor:
    """Extracts financial data for companies."""
    
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
        Extract data for a single company.
        
        Args:
            company: Company dictionary with id, ticker, name
            
        Returns:
            DataFrame with extracted data
        """
        # TODO: Replace with actual data source
        # This is a placeholder showing the structure
        
        ticker = company['ticker']
        
        # Example: You might call an API here
        # data = self._fetch_from_api(ticker)
        
        # For now, create sample structure
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * self.lookback_years)
        
        # Placeholder data structure
        data = {
            'company_id': company['id'],
            'ticker': ticker,
            'date': end_date.strftime('%Y-%m-%d'),
            'revenue': None,  # To be filled from actual source
            'profit': None,
            'market_cap': None,
            # Add more fields based on your investment factor
        }
        
        return pd.DataFrame([data])
    
    def extract_bulk_data(self, companies: List[dict]) -> pd.DataFrame:
        """
        Extract data for multiple companies.
        
        Args:
            companies: List of company dictionaries
            
        Returns:
            DataFrame with all extracted data
        """
        all_data = []
        
        for company in companies:
            try:
                df = self.extract_company_data(company)
                all_data.append(df)
                print(f"✅ Extracted data for {company['ticker']}")
            except Exception as e:
                print(f"❌ Failed to extract {company['ticker']}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()
