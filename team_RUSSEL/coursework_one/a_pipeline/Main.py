#!/usr/bin/env python3
"""
Main application entry point for investment data pipeline.

This module orchestrates the full ETL pipeline for extracting,
transforming, and loading Value Factor and Quality Factor data
for companies in the investable universe.

:author: Team RUSSEL
:module: Main
"""
import argparse
from datetime import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.db.db_connection import DatabaseConnector, load_company_list
from a_pipeline.modules.input.data_extractor import DataExtractor
from a_pipeline.modules.output.minio_storage import MinIOStorage
from a_pipeline.modules.output.mongo_storage import MongoStorage
from a_pipeline.modules.output.postgres_storage import PostgresStorage


def setup_logging(config):
    """
    Set up logging configuration from config dictionary.

    :param config: Application configuration dictionary.
    :type config: dict
    :returns: Configured logger instance.
    :rtype: logging.Logger
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format=config['logging']['format']
    )
    return logging.getLogger(__name__)


def main(config_path, run_date=None, frequency=None, ticker=None):
    """
    Execute the main pipeline: extract data, store to MinIO, MongoDB, and PostgreSQL.

    :param config_path: Path to the YAML configuration file.
    :type config_path: str
    :param run_date: Optional run date in ``YYYY-MM-DD`` format. Defaults to today.
    :type run_date: str or None
    :param frequency: Optional extraction frequency (``daily``, ``weekly``, ``monthly``).
    :type frequency: str or None
    :param ticker: Optional single ticker to process instead of full universe.
    :type ticker: str or None
    """
    config = load_config(config_path)
    logger = setup_logging(config)

    logger.info("=" * 60)
    logger.info("Starting Investment Data Pipeline")
    logger.info("=" * 60)

    if frequency:
        config['extraction']['frequency'] = frequency
        logger.info(f"Frequency set to: {frequency}")

    if run_date:
        run_date = datetime.strptime(run_date, '%Y-%m-%d')
    else:
        run_date = datetime.now()

    logger.info(f"Run date: {run_date.strftime('%Y-%m-%d')}")

    db_connector = None
    try:
        # Initialize components
        logger.info("Initializing database connections...")
        db_connector = DatabaseConnector(config)

        logger.info("Initializing data extractor...")
        extractor = DataExtractor(config)

        logger.info("Initializing storage handlers...")
        minio_storage = MinIOStorage(config)
        mongo_storage = MongoStorage(db_connector)
        postgres_storage = PostgresStorage(db_connector)

        # Load company list or single ticker
        if ticker:
            logger.info(f"Processing single ticker: {ticker}")
            companies = [{
                'ticker': ticker,
                'name': ticker,
                'gics_sector': None,
                'gics_industry': None
            }]
        else:
            logger.info("Loading company list...")
            companies = load_company_list(db_connector)
            logger.info(f"Found {len(companies)} companies")

        if not companies:
            logger.warning("No companies to process. Exiting.")
            return

        # ── Extract & store CURRENT Value Factor data ──
        logger.info("Extracting current Value Factor data...")
        current_df = extractor.extract_bulk_data(companies)

        if current_df.empty:
            logger.warning("No current data extracted!")
        else:
            logger.info(f"Extracted {len(current_df)} current records")

            # Store current data in MinIO
            object_name = (
                f"current_data/{run_date.strftime('%Y/%m/%d')}/value_factors.parquet"
            )
            logger.info(f"Storing current data to MinIO: {object_name}")
            minio_storage.store_dataframe(current_df, object_name)

            # Store current data in MongoDB (with upsert)
            logger.info("Storing current data to MongoDB...")
            mongo_storage.store_dataframe(current_df)

            # Store current data in PostgreSQL (with upsert)
            logger.info("Storing current data to PostgreSQL...")
            postgres_storage.upsert_metrics(current_df)

        # ── Extract & store HISTORICAL price data (5 years) ──
        logger.info("Extracting historical price data (5 years)...")
        historical_df = extractor.extract_bulk_historical_data(companies)

        if historical_df.empty:
            logger.warning("No historical data extracted!")
        else:
            logger.info(f"Extracted {len(historical_df)} historical records")

            # Store historical data in MinIO
            hist_object_name = (
                f"historical_data/{run_date.strftime('%Y/%m/%d')}/price_history.parquet"
            )
            logger.info(f"Storing historical data to MinIO: {hist_object_name}")
            minio_storage.store_dataframe(historical_df, hist_object_name)

            # Store in MongoDB
            logger.info("Storing historical data to MongoDB...")
            mongo_storage.store_dataframe(historical_df)

            # Store historical metrics in Postgres
            logger.info("Storing historical metrics to Postgres...")
            postgres_storage.upsert_metrics(historical_df)

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Pipeline execution failed: {e}")
        sys.exit(1)
    finally:
        # Always close database connections
        if db_connector:
            logger.info("Closing database connections...")
            db_connector.close_all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investment Data Pipeline")
    parser.add_argument(
        "--config", required=True,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--date",
        help="Run date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly", "monthly"],
        help="Data extraction frequency"
    )
    parser.add_argument(
        "--ticker",
        help="Run pipeline for a single ticker"
    )

    args = parser.parse_args()
    main(args.config, args.date, args.frequency, args.ticker)