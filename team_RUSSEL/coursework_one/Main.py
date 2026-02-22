#!/usr/bin/env python3
"""
Main application entry point for investment data pipeline.
"""
import argparse
from datetime import datetime
import logging

from modules.utils.config_loader import load_config
from modules.db.db_connection import DatabaseConnector, load_company_list
from modules.input.data_extractor import DataExtractor
from modules.output.minio_storage import MinIOStorage
from modules.output.mongo_storage import MongoStorage
from modules.output.postgres_storage import PostgresStorage


def setup_logging(config):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format=config['logging']['format']
    )
    return logging.getLogger(__name__)


def main(config_path, run_date=None, frequency=None):
    """Main pipeline execution."""
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
        
        # Load company list
        logger.info("Loading company list...")
        companies = load_company_list(db_connector)
        logger.info(f"Found {len(companies)} companies")
        
        # Extract current Value Factor data
        logger.info("Extracting current Value Factor data...")
        current_df = extractor.extract_bulk_data(companies)
        
        if current_df.empty:
            logger.warning("No current data extracted!")
        else:
            logger.info(f"Extracted {len(current_df)} current records")
            
            # Store current data in MinIO
            object_name = f"current_data/{run_date.strftime('%Y/%m/%d')}/value_factors.parquet"
            logger.info(f"Storing current data to MinIO: {object_name}")
            minio_storage.store_dataframe(current_df, object_name)
            
            # Store current data in MongoDB
            logger.info("Storing current data to MongoDB...")
            mongo_storage.store_dataframe(current_df)
        
        # Extract historical data (5 years)
        logger.info("Extracting historical price data (5 years)...")
        historical_df = extractor.extract_bulk_historical_data(companies)
        
        if historical_df.empty:
            logger.warning("No historical data extracted!")
        else:
            logger.info(f"Extracted {len(historical_df)} historical records")
            
            # Store historical data in MinIO
            hist_object_name = f"historical_data/{run_date.strftime('%Y/%m/%d')}/price_history.parquet"
            logger.info(f"Storing historical data to MinIO: {hist_object_name}")
            minio_storage.store_dataframe(historical_df, hist_object_name)
            
            # Optionally store in MongoDB (might be a lot of data)
            logger.info("Storing historical data to MongoDB...")
            mongo_storage.store_dataframe(historical_df)

            # Store historical metrics in Postgres
            logger.info("Storing historical data to Postgres...")
            postgres_storage.upsert_metrics(historical_df)
        
        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info(f"  - Current records: {len(current_df) if not current_df.empty else 0}")
        logger.info(f"  - Historical records: {len(historical_df) if not historical_df.empty else 0}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise
    
    finally:
        db_connector.close_all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investment Data Pipeline")
    parser.add_argument('--config', default='config/conf.yaml', help='Path to configuration file')
    parser.add_argument('--date', help='Run date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly'], help='Run frequency (overrides config)')
    
    args = parser.parse_args()
    
    main(args.config, args.date, args.frequency)


