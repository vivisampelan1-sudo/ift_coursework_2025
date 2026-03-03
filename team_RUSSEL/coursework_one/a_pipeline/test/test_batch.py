#!/usr/bin/env python3
"""
Test batch: run pipeline for first N companies from company_static.
Default N=50. Pass a number as argument to change.

Usage:
    poetry run python test_batch.py          # 50 companies
    poetry run python test_batch.py 20       # 20 companies
    poetry run python test_batch.py --all    # all companies
"""
import sys
import time
from datetime import datetime

from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.db.db_connection import DatabaseConnector, load_company_list
from a_pipeline.modules.input.data_extractor import DataExtractor
from a_pipeline.modules.output.minio_storage import MinIOStorage
from a_pipeline.modules.output.mongo_storage import MongoStorage
from a_pipeline.modules.output.postgres_storage import PostgresStorage


def main():
    # Parse batch size
    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            batch_size = None
        else:
            batch_size = int(sys.argv[1])
    else:
        batch_size = 50

    config = load_config('a_pipeline/config/conf.yaml')
    db_connector = DatabaseConnector(config)

    try:
        # Load companies
        all_companies = load_company_list(db_connector)
        if batch_size:
            companies = all_companies[:batch_size]
        else:
            companies = all_companies

        print(f"{'=' * 60}")
        print(f"BATCH TEST: {len(companies)} / {len(all_companies)} companies")
        print(f"{'=' * 60}")

        extractor = DataExtractor(config)
        minio_storage = MinIOStorage(config)
        mongo_storage = MongoStorage(db_connector)
        postgres_storage = PostgresStorage(db_connector)
        run_date = datetime.now()

        # --- Current data ---
        print(f"\n--- Extracting CURRENT data ---")
        start = time.time()
        current_df = extractor.extract_bulk_data(companies)
        elapsed = time.time() - start
        print(f"✅ Extracted {len(current_df)} current records in {elapsed:.1f}s")

        if not current_df.empty:
            obj = f"current_data/{run_date.strftime('%Y/%m/%d')}/value_factors.parquet"
            minio_storage.store_dataframe(current_df, obj)
            mongo_storage.store_dataframe(current_df)
            postgres_storage.upsert_metrics(current_df)
            print(f"✅ Stored current data to all 3 backends")

        # --- Historical data ---
        print(f"\n--- Extracting HISTORICAL data (5 years, with quarterly fundamentals) ---")
        start = time.time()
        historical_df = extractor.extract_bulk_historical_data(companies)
        elapsed = time.time() - start
        print(f"✅ Extracted {len(historical_df)} historical records in {elapsed:.1f}s")

        if not historical_df.empty:
            obj = f"historical_data/{run_date.strftime('%Y/%m/%d')}/price_history.parquet"
            minio_storage.store_dataframe(historical_df, obj)
            mongo_storage.store_dataframe(historical_df)
            postgres_storage.upsert_metrics(historical_df)
            print(f"✅ Stored historical data to all 3 backends")

        # --- Summary ---
        print(f"\n{'=' * 60}")
        print(f"SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Companies processed: {len(companies)}")
        print(f"  Current rows:        {len(current_df)}")
        print(f"  Historical rows:     {len(historical_df)}")

        if not historical_df.empty:
            # Check variation in fundamentals
            pe_unique = historical_df.groupby('ticker')['pe_ratio'].nunique()
            varying = (pe_unique > 1).sum()
            print(f"  Tickers with varying P/E: {varying}/{len(pe_unique)}")

        # Errors
        if 'error' in current_df.columns:
            errors = current_df[current_df['error'].notna()]
            if not errors.empty:
                print(f"\n  ⚠️ {len(errors)} extraction errors:")
                for _, row in errors.iterrows():
                    print(f"    {row['ticker']}: {row['error'][:80]}")

    finally:
        db_connector.close_all()
        print(f"\n✅ Done! Connections closed.")


if __name__ == '__main__':
    main()