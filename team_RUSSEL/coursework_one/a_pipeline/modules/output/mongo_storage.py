"""
MongoDB storage handler.

Stores extracted financial metrics in MongoDB with upsert semantics
keyed on ``(ticker, date)`` to prevent duplicate records across
repeated pipeline runs.

:module: modules.output.mongo_storage
"""
from pymongo import UpdateOne
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MongoStorage:
    """
    Handles data storage in MongoDB with upsert-based deduplication.

    Data is stored in the ``investment_data`` database, within the
    ``company_metrics`` collection. A unique index on ``(ticker, date)``
    is created automatically to enforce deduplication.

    :param db_connector: An initialised DatabaseConnector instance.
    :type db_connector: modules.db.db_connection.DatabaseConnector
    """

    def __init__(self, db_connector):
        """
        Initialise MongoDB storage.

        :param db_connector: DatabaseConnector instance.
        :type db_connector: modules.db.db_connection.DatabaseConnector
        """
        self.client = db_connector.get_mongo_client()
        self.db = self.client['investment_data']
        self.collection = self.db['company_metrics']
        self._ensure_indexes()

    def _ensure_indexes(self):
        """
        Create indexes for efficient querying and upsert deduplication.

        Creates a unique compound index on ``(ticker, date)`` so that
        repeated pipeline runs update existing records rather than
        creating duplicates.
        """
        self.collection.create_index(
            [('ticker', 1), ('date', 1)],
            unique=True,
            name='idx_ticker_date'
        )
        logger.info("MongoDB indexes ensured on (ticker, date)")

    def store_dataframe(self, df: pd.DataFrame):
        """
        Store DataFrame in MongoDB using bulk upsert operations.

        Each row is upserted by matching on ``(ticker, date)``. Existing
        records are updated; new records are inserted.

        :param df: DataFrame to store. Must contain ``ticker`` and ``date`` columns.
        :type df: pandas.DataFrame
        """
        if df.empty:
            logger.warning("Empty DataFrame — nothing to store in MongoDB.")
            return

        records = df.to_dict('records')
        operations = []

        for record in records:
            ticker = record.get('ticker')
            date = record.get('date')

            if not ticker or not date:
                logger.warning(f"Skipping record with missing ticker/date: {record}")
                continue

            # Add/update metadata timestamp
            record['updated_at'] = datetime.utcnow()

            operations.append(
                UpdateOne(
                    {'ticker': ticker, 'date': date},
                    {'$set': record, '$setOnInsert': {'inserted_at': datetime.utcnow()}},
                    upsert=True
                )
            )

        if operations:
            result = self.collection.bulk_write(operations, ordered=False)
            logger.info(
                f"MongoDB bulk upsert: {result.upserted_count} inserted, "
                f"{result.modified_count} updated, "
                f"{result.matched_count} matched"
            )
        else:
            logger.warning("No valid records to upsert into MongoDB.")

    def query_by_ticker(self, ticker: str) -> pd.DataFrame:
        """
        Query all records for a specific ticker.

        :param ticker: Company ticker symbol (e.g. ``AAPL``).
        :type ticker: str
        :returns: DataFrame with all matching records.
        :rtype: pandas.DataFrame
        """
        results = list(self.collection.find(
            {'ticker': ticker},
            {'_id': 0}  # Exclude MongoDB internal ID
        ))
        return pd.DataFrame(results)

    def query_by_year(self, year: int) -> pd.DataFrame:
        """
        Query all records for a specific year.

        :param year: Year to query (e.g. ``2024``).
        :type year: int
        :returns: DataFrame with all matching records.
        :rtype: pandas.DataFrame
        """
        results = list(self.collection.find(
            {'date': {'$regex': f'^{year}'}},
            {'_id': 0}
        ))
        return pd.DataFrame(results)

    def query_by_ticker_and_year(self, ticker: str, year: int) -> pd.DataFrame:
        """
        Query records for a specific ticker and year.

        :param ticker: Company ticker symbol.
        :type ticker: str
        :param year: Year to query.
        :type year: int
        :returns: DataFrame with matching records.
        :rtype: pandas.DataFrame
        """
        results = list(self.collection.find(
            {'ticker': ticker, 'date': {'$regex': f'^{year}'}},
            {'_id': 0}
        ))
        return pd.DataFrame(results)
