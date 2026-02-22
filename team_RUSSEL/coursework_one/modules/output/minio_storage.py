"""MinIO storage handler."""
from minio import Minio
from io import BytesIO
import pandas as pd
from datetime import datetime


class MinIOStorage:
    """Handles data storage in MinIO (S3-compatible)."""
    
    def __init__(self, config: dict):
        """
        Initialize MinIO client.
        
        Args:
            config: Configuration dictionary
        """
        self.client = Minio(
            config['minio']['endpoint'],
            access_key=config['minio']['access_key'],
            secret_key=config['minio']['secret_key'],
            secure=config['minio']['secure']
        )
        self.bucket_name = "investment-data"
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            print(f"✅ Created bucket: {self.bucket_name}")
    
    def store_dataframe(self, df: pd.DataFrame, object_name: str):
        """
        Store DataFrame as Parquet in MinIO.
        
        Args:
            df: DataFrame to store
            object_name: Name/path for the object in MinIO
        """
        # Clean data: replace Infinity and bad values that Parquet can't handle
        import numpy as np
        df = df.copy()
        df = df.replace([np.inf, -np.inf, 'Infinity', '-Infinity'], None)
        # Convert numeric columns to proper types
        numeric_cols = df.select_dtypes(include=['object']).columns
        for col in numeric_cols:
            try:
                df[col] = pd.to_numeric(df[col], errors='ignore')
            except Exception:
                pass
            
        # Convert DataFrame to Parquet bytes
        parquet_bytes = BytesIO()
        df.to_parquet(parquet_bytes, index=False, engine='pyarrow')
        parquet_bytes.seek(0)
        
        # Upload to MinIO
        self.client.put_object(
            self.bucket_name,
            object_name,
            parquet_bytes,
            length=len(parquet_bytes.getvalue()),
            content_type='application/octet-stream'
        )
        
        print(f"✅ Stored data to MinIO: {object_name}")
    
    def retrieve_dataframe(self, object_name: str) -> pd.DataFrame:
        """
        Retrieve DataFrame from MinIO.
        
        Args:
            object_name: Name/path of the object in MinIO
            
        Returns:
            DataFrame
        """
        response = self.client.get_object(self.bucket_name, object_name)
        df = pd.read_parquet(BytesIO(response.read()))
        response.close()
        response.release_conn()
        
        return df
