"""PostgreSQL storage handler for Value Factor metrics."""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class PostgresStorage:
    """Handles writing extracted data back to PostgreSQL."""

    def __init__(self, db_connector):
        self.conn = db_connector.get_postgres_connection()

    def upsert_metrics(self, df: pd.DataFrame):
        """Update existing rows in systematic_equity.factor_data matched by symbol + date."""
        if df.empty:
            return
        cursor = self.conn.cursor()

        insert_sql = """
        INSERT INTO systematic_equity.factor_data (
            ticker, date, current_price, market_cap, pe_ratio, pb_ratio, eps,
            ev_to_ebitda, ev_to_revenue, book_value, roe, roa, debt_to_equity,
            current_ratio, profit_margin, operating_margin, gross_margin,
            free_cash_flow, revenue, total_debt, ebitda, dividend_yield,
            forward_pe, ps_ratio
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            current_price    = EXCLUDED.current_price,
            market_cap       = EXCLUDED.market_cap,
            pe_ratio         = EXCLUDED.pe_ratio,
            pb_ratio         = EXCLUDED.pb_ratio,
            eps              = EXCLUDED.eps,
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
            forward_pe       = EXCLUDED.forward_pe,
            ps_ratio         = EXCLUDED.ps_ratio
        """

        for _, row in df.iterrows():
            params = (
                row.get('ticker'),
                row.get('date'),
                row.get('current_price'),
                row.get('market_cap'),
                row.get('pe_ratio'),
                row.get('pb_ratio'),
                row.get('eps'),
                row.get('ev_to_ebitda'),
                row.get('ev_to_revenue'),
                row.get('book_value'),
                row.get('roe'),
                row.get('roa'),
                row.get('debt_to_equity'),
                row.get('current_ratio'),
                row.get('profit_margin'),
                row.get('operating_margin'),
                row.get('gross_margin'),
                row.get('free_cash_flow'),
                row.get('revenue'),
                row.get('total_debt'),
                row.get('ebitda'),
                row.get('dividend_yield'),
                row.get('forward_pe'),
                row.get('ps_ratio'),
            )
            cursor.execute(insert_sql, params)

        self.conn.commit()
        cursor.close()
        logger.info(f"✅ Upserted {len(df)} rows into PostgreSQL")