"""
PostgreSQL storage handler for Value Factor and Quality Factor metrics.

Upserts extracted data into ``systematic_equity.factor_data`` using
an ``ON CONFLICT (ticker, date) DO UPDATE`` strategy, ensuring
idempotent pipeline runs.

:module: modules.output.postgres_storage
"""
import math
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class PostgresStorage:
    """
    Handles writing extracted data back to PostgreSQL.

    Uses upsert (INSERT ... ON CONFLICT DO UPDATE) on the
    ``(ticker, date)`` composite key to allow safe re-runs.

    :param db_connector: An initialised DatabaseConnector instance.
    :type db_connector: modules.db.db_connection.DatabaseConnector
    """

    # SQL template for upsert into factor_data
    UPSERT_SQL = """
    INSERT INTO systematic_equity.factor_data (
        company_id, company_name, ticker, date,
        open, high, low, close, volume, current_price,
        market_cap, pe_ratio, forward_pe, pb_ratio, ps_ratio, eps, forward_eps,
        ev_to_ebitda, ev_to_revenue, book_value, roe, roa, debt_to_equity,
        current_ratio, profit_margin, operating_margin, gross_margin,
        free_cash_flow, revenue, total_debt, ebitda, dividend_yield,
        sector, industry, db_sector, db_industry, cash
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
    ON CONFLICT (ticker, date) DO UPDATE SET
        company_id       = EXCLUDED.company_id,
        company_name     = EXCLUDED.company_name,
        open             = EXCLUDED.open,
        high             = EXCLUDED.high,
        low              = EXCLUDED.low,
        close            = EXCLUDED.close,
        volume           = EXCLUDED.volume,
        current_price    = EXCLUDED.current_price,
        market_cap       = EXCLUDED.market_cap,
        pe_ratio         = EXCLUDED.pe_ratio,
        forward_pe       = EXCLUDED.forward_pe,
        pb_ratio         = EXCLUDED.pb_ratio,
        ps_ratio         = EXCLUDED.ps_ratio,
        eps              = EXCLUDED.eps,
        forward_eps      = EXCLUDED.forward_eps,
        ev_to_ebitda     = EXCLUDED.ev_to_ebitda,
        ev_to_revenue    = EXCLUDED.ev_to_revenue,
        book_value       = EXCLUDED.book_value,
        roe              = EXCLUDED.roe,
        roa              = EXCLUDED.roa,
        debt_to_equity   = EXCLUDED.debt_to_equity,
        current_ratio    = EXCLUDED.current_ratio,
        profit_margin    = EXCLUDED.profit_margin,
        operating_margin = EXCLUDED.operating_margin,
        gross_margin     = EXCLUDED.gross_margin,
        free_cash_flow   = EXCLUDED.free_cash_flow,
        revenue          = EXCLUDED.revenue,
        total_debt       = EXCLUDED.total_debt,
        ebitda           = EXCLUDED.ebitda,
        dividend_yield   = EXCLUDED.dividend_yield,
        sector           = COALESCE(EXCLUDED.sector, factor_data.sector),
        industry         = COALESCE(EXCLUDED.industry, factor_data.industry),
        db_sector        = COALESCE(EXCLUDED.db_sector, factor_data.db_sector),
        db_industry      = COALESCE(EXCLUDED.db_industry, factor_data.db_industry),
        cash             = EXCLUDED.cash
    """

    def __init__(self, db_connector):
        """
        Initialise PostgreSQL storage handler.

        :param db_connector: DatabaseConnector instance.
        :type db_connector: modules.db.db_connection.DatabaseConnector
        """
        self.db_connector = db_connector
        self.conn = db_connector.get_postgres_connection()

    @staticmethod
    def _to_python_scalar(val):
        """
        Convert a value to a plain Python scalar safe for psycopg2.

        Handles numpy types, pandas NA, and infinity values.

        :param val: Value to convert.
        :returns: Python scalar or ``None``.
        """
        if val is None:
            return None
        # Normalise numpy/pandas scalars to plain Python types first
        if hasattr(val, 'item'):
            val = val.item()
        # Use math.isfinite — catches inf, -inf, nan for any Python float
        if isinstance(val, float):
            if not math.isfinite(val):
                return None
        try:
            # Catch pandas NA / NaT
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        return val

    def _extract_row_params(self, row):
        """
        Extract an ordered tuple of parameters from a DataFrame row.

        Handles both lowercase (current data) and capitalised (historical)
        column names for OHLCV fields.

        :param row: A single row from a pandas DataFrame.
        :type row: pandas.Series
        :returns: Tuple of values matching the UPSERT_SQL column order.
        :rtype: tuple
        """
        s = self._to_python_scalar

        # Handle both column naming conventions for OHLCV
        open_val = row.get('open') if row.get('open') is not None else row.get('Open')
        high_val = row.get('high') if row.get('high') is not None else row.get('High')
        low_val = row.get('low') if row.get('low') is not None else row.get('Low')
        close_val = row.get('close') if row.get('close') is not None else row.get('Close')
        volume_val = row.get('volume') if row.get('volume') is not None else row.get('Volume')

        return (
            s(row.get('company_id')),
            s(row.get('company_name')),
            s(row.get('ticker')),
            s(row.get('date')),
            s(open_val),
            s(high_val),
            s(low_val),
            s(close_val),
            s(volume_val),
            s(row.get('current_price')),
            s(row.get('market_cap')),
            s(row.get('pe_ratio')),
            s(row.get('forward_pe')),
            s(row.get('pb_ratio')),
            s(row.get('ps_ratio')),
            s(row.get('eps')),
            s(row.get('forward_eps')),
            s(row.get('ev_to_ebitda')),
            s(row.get('ev_to_revenue')),
            s(row.get('book_value')),
            s(row.get('roe')),
            s(row.get('roa')),
            s(row.get('debt_to_equity')),
            s(row.get('current_ratio')),
            s(row.get('profit_margin')),
            s(row.get('operating_margin')),
            s(row.get('gross_margin')),
            s(row.get('free_cash_flow')),
            s(row.get('revenue')),
            s(row.get('total_debt')),
            s(row.get('ebitda')),
            s(row.get('dividend_yield')),
            s(row.get('sector')),
            s(row.get('industry')),
            s(row.get('db_sector')),
            s(row.get('db_industry')),
            s(row.get('cash')),
        )

    def upsert_metrics(self, df: pd.DataFrame):
        """
        Upsert rows into ``systematic_equity.factor_data``.

        Inserts new rows or updates existing rows matched by ``(ticker, date)``.
        The entire batch is committed as a single transaction; on failure the
        transaction is rolled back.

        :param df: DataFrame with extracted metrics.
        :type df: pandas.DataFrame
        :raises Exception: Re-raises any database error after rollback.
        """
        if df.empty:
            logger.info("Empty DataFrame — nothing to upsert to PostgreSQL.")
            return

        # Sanitise numeric columns: force inf/-inf → NaN using numpy directly
        for col in df.select_dtypes(include=[np.number]).columns:
            mask = np.isinf(df[col].to_numpy(dtype=float, na_value=np.nan))
            if mask.any():
                df.loc[mask, col] = np.nan

        cursor = self.conn.cursor()
        row_count = 0
        skipped = 0

        for _, row in df.iterrows():
            try:
                params = self._extract_row_params(row)
                cursor.execute(self.UPSERT_SQL, params)
                row_count += 1
            except Exception as e:
                self.conn.rollback()
                logger.warning(f"Skipped ticker {row.get('ticker', '?')} on {row.get('date', '?')}: {e}")
                skipped += 1
                cursor = self.conn.cursor()

        try:
            self.conn.commit()
            logger.info(f"Upserted {row_count} rows into PostgreSQL (skipped {skipped})")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Final commit failed: {e}")
            raise
        finally:
            cursor.close()
