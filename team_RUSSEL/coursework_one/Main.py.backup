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


def setup_logging(config):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format=config['logging']['format']
    )
    return logging.getLogger(__name__)


def main(config_path, run_date=None, frequency=None):
    """Main pipeline execution."""
    # Load configuration
    config = load_config(config_path)
    logger = setup_logging(config)
    
    logger.info("=" * 60)
    logger.info("Starting Investment Data Pipeline")
    logger.info("=" * 60)
    
    # Override frequency if provided
    if frequency:
        config['extraction']['frequency'] = frequency
        logger.info(f"Frequency set to: {frequency}")
    
    # Parse run date
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
        
        # Load company list
        logger.info("Loading company list...")
        companies = load_company_list(db_connector)
        logger.info(f"Found {len(companies)} companies")
        
        # Extract data
        logger.info("Extracting data...")
        df = extractor.extract_bulk_data(companies)
        
        if df.empty:
            logger.warning("No data extracted!")
            return
        
        logger.info(f"Extracted {len(df)} records")
        
        # Store in MinIO (data lake)
        object_name = f"raw_data/{run_date.strftime('%Y/%m/%d')}/data.parquet"
        logger.info(f"Storing to MinIO: {object_name}")
        minio_storage.store_dataframe(df, object_name)
        
        # Store in MongoDB (for easy querying)
        logger.info("Storing to MongoDB...")
        mongo_storage.store_dataframe(df)
        
        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise
    
    finally:
        # Clean up
        db_connector.close_all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investment Data Pipeline")
    parser.add_argument('--config', default='config/conf.yaml', help='Path to configuration file')
    parser.add_argument('--date', help='Run date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly'], help='Run frequency (overrides config)')
    
    args = parser.parse_args()
    
    main(args.config, args.date, args.frequency)
