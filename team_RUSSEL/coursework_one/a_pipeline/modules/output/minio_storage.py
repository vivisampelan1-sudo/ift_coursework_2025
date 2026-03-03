"""
MinIO storage handler.

Stores DataFrames as Parquet files in MinIO (S3-compatible object storage),
providing the data lake layer of the pipeline architecture.

:module: modules.output.minio_storage
"""
from minio import Minio
from io import BytesIO
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MinIOStorage:
    """
    Handles data storage and retrieval in MinIO (S3-compatible).

    Data is stored in the ``investment-data`` bucket as Parquet files,
    organised by date path (e.g. ``current_data/2026/02/23/value_factors.parquet``).

    :param config: Configuration dictionary with a ``minio`` section containing
        ``endpoint``, ``access_key``, ``secret_key``, and ``secure`` keys.
    :type config: dict
    """

    def __init__(self, config: dict):
        """
        Initialise MinIO client and ensure bucket exists.

        :param config: Configuration dictionary.
        :type config: dict
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
        """Create the storage bucket if it does not already exist."""
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            logger.info(f"Created MinIO bucket: {self.bucket_name}")
        else:
            logger.debug(f"MinIO bucket already exists: {self.bucket_name}")

    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean a DataFrame for safe Parquet serialisation.

        Replaces infinity values with ``None`` and converts numeric-like
        object columns (excluding known text columns) to proper numeric types.

        :param df: Raw DataFrame.
        :type df: pandas.DataFrame
        :returns: Cleaned copy of the DataFrame.
        :rtype: pandas.DataFrame
        """
        df = df.copy()

        # Replace infinities
        df = df.replace([np.inf, -np.inf, 'Infinity', '-Infinity'], None)

        # Known text columns that should NOT be converted to numeric
        text_columns = {
            'company_id', 'ticker', 'company_name', 'date', 'error',
            'sector', 'industry', 'db_sector', 'db_industry'
        }

        # Only attempt numeric conversion on non-text object columns
        object_cols = df.select_dtypes(include=['object']).columns
        for col in object_cols:
            if col not in text_columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except Exception:
                    pass

        return df

    def store_dataframe(self, df: pd.DataFrame, object_name: str):
        """
        Store a DataFrame as a Parquet file in MinIO.

        :param df: DataFrame to store.
        :type df: pandas.DataFrame
        :param object_name: Object path in MinIO
            (e.g. ``current_data/2026/02/23/value_factors.parquet``).
        :type object_name: str
        """
        df = self._clean_dataframe(df)

        parquet_bytes = BytesIO()
        df.to_parquet(parquet_bytes, index=False, engine='pyarrow')
        parquet_bytes.seek(0)

        self.client.put_object(
            self.bucket_name,
            object_name,
            parquet_bytes,
            length=len(parquet_bytes.getvalue()),
            content_type='application/octet-stream'
        )

        logger.info(f"Stored {len(df)} rows to MinIO: {object_name}")

    def retrieve_dataframe(self, object_name: str) -> pd.DataFrame:
        """
        Retrieve a DataFrame from a Parquet file in MinIO.

        :param object_name: Object path in MinIO.
        :type object_name: str
        :returns: DataFrame read from the Parquet file.
        :rtype: pandas.DataFrame
        """
        response = self.client.get_object(self.bucket_name, object_name)
        try:
            df = pd.read_parquet(BytesIO(response.read()))
        finally:
            response.close()
            response.release_conn()

        logger.info(f"Retrieved {len(df)} rows from MinIO: {object_name}")
        return df
