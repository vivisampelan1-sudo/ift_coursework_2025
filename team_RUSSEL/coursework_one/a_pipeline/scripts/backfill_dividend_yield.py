#!/usr/bin/env python3
"""
Backfill dividend_yield in factor_data from yfinance dividend history.

For each ticker, fetches the historical dividend payments from yfinance,
then computes trailing-12-month DPS / close for every row in factor_data.

Usage:
    cd team_RUSSEL/coursework_one
    poetry run python a_pipeline/scripts/backfill_dividend_yield.py
"""
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import yfinance as yf
import pandas as pd
import numpy as np

from a_pipeline.modules.utils.config_loader import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def compute_ttm_dividend_yield(dividends: pd.Series, dates: pd.Series,
                               closes: pd.Series) -> list:
    """
    Compute trailing-12-month dividend yield for each (date, close) pair.

    :param dividends: yfinance stock.dividends — indexed by ex-date.
    :param dates:     Series of date strings from factor_data.
    :param closes:    Corresponding close prices.
    :returns: List of (dividend_yield or None) in the same order as dates.
    """
    if dividends is None or dividends.empty:
        return [0.0] * len(dates)

    div = dividends.copy()
    div.index = pd.to_datetime(div.index).tz_localize(None)

    results = []
    for date_str, close in zip(dates, closes):
        try:
            dt = pd.to_datetime(date_str)
            ttm_start = dt - pd.DateOffset(months=12)
            ttm_dps = float(div[(div.index > ttm_start) & (div.index <= dt)].sum())
            if close and float(close) > 0 and ttm_dps > 0:
                results.append(ttm_dps / float(close))
            else:
                results.append(0.0)
        except Exception:
            results.append(None)
    return results


def main():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "conf.yaml"
    )
    config = load_config(config_path)
    pg = config["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], dbname=pg["database"],
        user=pg["user"], password=pg["password"]
    )
    cur = conn.cursor()

    # Get all distinct tickers in factor_data
    cur.execute("""
        SELECT DISTINCT ticker
        FROM systematic_equity.factor_data
        ORDER BY ticker
    """)
    tickers = [r[0].strip() for r in cur.fetchall()]
    logger.info(f"Total tickers to process: {len(tickers)}")

    updated_tickers = 0
    updated_rows = 0

    for i, ticker in enumerate(tickers, 1):
        try:
            # Fetch all (date, close) for this ticker
            cur.execute("""
                SELECT date, close
                FROM systematic_equity.factor_data
                WHERE ticker = %s
                ORDER BY date
            """, (ticker,))
            rows = cur.fetchall()
            if not rows:
                continue

            dates = pd.Series([r[0] for r in rows])
            closes = pd.Series([r[1] for r in rows])

            # Fetch yfinance dividend history
            stock = yf.Ticker(ticker)
            dividends = stock.dividends

            yields = compute_ttm_dividend_yield(dividends, dates, closes)

            # Build update batch — only update rows where we have a value
            batch = [
                (y, ticker, str(d))
                for y, d in zip(yields, dates)
                if y is not None
            ]

            if not batch:
                logger.info(f"[{i}/{len(tickers)}] {ticker}: no dividend data")
                continue

            # Count non-zero dividend yields
            non_zero = sum(1 for y, _, _ in batch if y and y > 0)

            cur.executemany("""
                UPDATE systematic_equity.factor_data
                SET dividend_yield = %s
                WHERE ticker = %s AND date::text = %s
            """, batch)
            updated_rows += cur.rowcount
            conn.commit()
            updated_tickers += 1

            if non_zero > 0:
                logger.info(f"[{i}/{len(tickers)}] {ticker}: {len(batch)} rows updated "
                            f"({non_zero} with non-zero yield)")
            else:
                logger.info(f"[{i}/{len(tickers)}] {ticker}: {len(batch)} rows set to 0 (non-payer)")

        except Exception as e:
            conn.rollback()
            logger.warning(f"[{i}/{len(tickers)}] {ticker}: failed — {e}")

    logger.info(f"\nDone — {updated_tickers} tickers, {updated_rows} rows updated")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
