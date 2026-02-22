"""MongoDB storage handler."""
from pymongo import MongoClient
import pandas as pd
from datetime import datetime


class MongoStorage:
    """Handles data storage in MongoDB."""
    
    def __init__(self, db_connector):
        """
        Initialize MongoDB storage.
        
        Args:
            db_connector: DatabaseConnector instance
        """
        self.client = db_connector.get_mongo_client()
        self.db = self.client['investment_data']
        self.collection = self.db['company_metrics']
    
    def store_dataframe(self, df: pd.DataFrame):
        """
        Store DataFrame in MongoDB.
        
        Args:
            df: DataFrame to store
        """
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        
        # Add metadata
        for record in records:
            record['inserted_at'] = datetime.utcnow()
        
        # Insert into MongoDB
        if records:
            result = self.collection.insert_many(records)
            print(f"✅ Inserted {len(result.inserted_ids)} records to MongoDB")
    
    def query_by_ticker(self, ticker: str) -> pd.DataFrame:
        """
        Query data for a specific ticker.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            DataFrame with results
        """
        results = list(self.collection.find({'ticker': ticker}))
        return pd.DataFrame(results)
    
    def query_by_year(self, year: int) -> pd.DataFrame:
        """
        Query data for a specific year.
        
        Args:
            year: Year to query
            
        Returns:
            DataFrame with results
        """
        # Adjust this based on your date field structure
        results = list(self.collection.find({
            'date': {'$regex': f'^{year}'}
        }))
        return pd.DataFrame(results)
