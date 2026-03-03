-- ============================================================================
-- factor_data Table: Value + Quality Factor Data
-- ============================================================================
-- Stores current and historical Value Factor and Quality Factor metrics
-- for all companies in the investable universe.
--
-- Populated by: team_RUSSEL/coursework_one/modules/output/postgres_storage.py
-- Upsert key:   (ticker, date)
-- ============================================================================

CREATE TABLE IF NOT EXISTS systematic_equity.factor_data (
    id               SERIAL PRIMARY KEY,
    company_id       VARCHAR(12),
    company_name     TEXT,
    ticker           VARCHAR(12)    NOT NULL,
    date             DATE           NOT NULL,

    -- OHLCV (NULL for current-snapshot rows)
    open             NUMERIC(15, 6),
    high             NUMERIC(15, 6),
    low              NUMERIC(15, 6),
    close            NUMERIC(15, 6),
    volume           BIGINT,
    current_price    NUMERIC(15, 6),

    -- ── Value Factors ────────────────────────────────────────────────
    market_cap       NUMERIC(22, 2),   -- Market capitalisation (USD)
    pe_ratio         NUMERIC(12, 6),   -- Trailing P/E  = Price / EPS
    forward_pe       NUMERIC(12, 6),   -- Forward P/E   = Price / Forward EPS
    pb_ratio         NUMERIC(12, 6),   -- P/B           = Price / Book Value per Share
    ps_ratio         NUMERIC(12, 6),   -- P/S           = Market Cap / Revenue
    eps              NUMERIC(15, 6),   -- Trailing EPS  (diluted)
    forward_eps      NUMERIC(15, 6),   -- Forward EPS   (analyst estimate)
    ev_to_ebitda     NUMERIC(12, 6),   -- EV / EBITDA
    ev_to_revenue    NUMERIC(12, 6),   -- EV / Revenue
    book_value       NUMERIC(15, 6),   -- Book Value per Share
    dividend_yield   NUMERIC(10, 6),   -- Dividend Yield (decimal, e.g. 0.015 = 1.5%)

    -- ── Quality Factors ──────────────────────────────────────────────
    roe              NUMERIC(10, 6),   -- Return on Equity     = Net Income / Equity
    roa              NUMERIC(10, 6),   -- Return on Assets     = Net Income / Total Assets
    debt_to_equity   NUMERIC(10, 6),   -- Leverage             = Total Debt / Equity
    current_ratio    NUMERIC(10, 6),   -- Liquidity            = Current Assets / Current Liabilities
    profit_margin    NUMERIC(10, 6),   -- Net Profit Margin    = Net Income / Revenue
    operating_margin NUMERIC(10, 6),   -- Operating Margin     = Operating Income / Revenue
    gross_margin     NUMERIC(10, 6),   -- Gross Margin         = Gross Profit / Revenue
    free_cash_flow   NUMERIC(22, 2),   -- Free Cash Flow       = Operating CF - CapEx

    -- ── Supporting Fundamentals ───────────────────────────────────────
    revenue          NUMERIC(22, 2),   -- Total Revenue (TTM)
    total_debt       NUMERIC(22, 2),   -- Total Debt
    ebitda           NUMERIC(22, 2),   -- EBITDA (TTM)

    -- ── Metadata ─────────────────────────────────────────────────────
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Upsert key: one row per company per date
    CONSTRAINT uq_factor_data_ticker_date UNIQUE (ticker, date),

    -- Referential integrity to company universe
    CONSTRAINT fk_factor_data_ticker
        FOREIGN KEY (ticker)
        REFERENCES systematic_equity.company_static (symbol)
        ON DELETE CASCADE
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_factor_data_ticker
    ON systematic_equity.factor_data (ticker);

CREATE INDEX IF NOT EXISTS idx_factor_data_date
    ON systematic_equity.factor_data (date);

CREATE INDEX IF NOT EXISTS idx_factor_data_ticker_date
    ON systematic_equity.factor_data (ticker, date);

CREATE INDEX IF NOT EXISTS idx_factor_data_pe_ratio
    ON systematic_equity.factor_data (pe_ratio)
    WHERE pe_ratio IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_factor_data_roe
    ON systematic_equity.factor_data (roe)
    WHERE roe IS NOT NULL;

-- ── Trigger: keep updated_at current ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION systematic_equity.update_factor_data_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_factor_data_updated_at ON systematic_equity.factor_data;
CREATE TRIGGER trg_factor_data_updated_at
    BEFORE UPDATE ON systematic_equity.factor_data
    FOR EACH ROW EXECUTE FUNCTION systematic_equity.update_factor_data_updated_at();

-- ── View: latest snapshot per company ────────────────────────────────────────
CREATE OR REPLACE VIEW systematic_equity.factor_data_latest AS
SELECT DISTINCT ON (fd.ticker)
    fd.ticker,
    cs.security        AS company_name,
    cs.gics_sector,
    cs.gics_industry,
    cs.country,
    cs.region,
    fd.date,
    -- Value Factors
    fd.current_price,
    fd.market_cap,
    fd.pe_ratio,
    fd.forward_pe,
    fd.pb_ratio,
    fd.ps_ratio,
    fd.ev_to_ebitda,
    fd.ev_to_revenue,
    fd.eps,
    fd.book_value,
    fd.dividend_yield,
    -- Quality Factors
    fd.roe,
    fd.roa,
    fd.debt_to_equity,
    fd.current_ratio,
    fd.profit_margin,
    fd.operating_margin,
    fd.gross_margin,
    fd.free_cash_flow,
    -- Fundamentals
    fd.revenue,
    fd.total_debt,
    fd.ebitda
FROM systematic_equity.factor_data fd
LEFT JOIN systematic_equity.company_static cs ON fd.ticker = cs.symbol
ORDER BY fd.ticker, fd.date DESC;

-- ── View: value factor ranking (lower = cheaper) ──────────────────────────────
CREATE OR REPLACE VIEW systematic_equity.value_factor_ranks AS
SELECT
    ticker,
    date,
    pe_ratio,
    pb_ratio,
    ps_ratio,
    ev_to_ebitda,
    ev_to_revenue,
    dividend_yield,
    -- Rank within each cross-section (lower multiple = better value rank)
    RANK() OVER (PARTITION BY date ORDER BY pe_ratio      ASC NULLS LAST) AS pe_rank,
    RANK() OVER (PARTITION BY date ORDER BY pb_ratio      ASC NULLS LAST) AS pb_rank,
    RANK() OVER (PARTITION BY date ORDER BY ps_ratio      ASC NULLS LAST) AS ps_rank,
    RANK() OVER (PARTITION BY date ORDER BY ev_to_ebitda  ASC NULLS LAST) AS ev_ebitda_rank,
    RANK() OVER (PARTITION BY date ORDER BY ev_to_revenue ASC NULLS LAST) AS ev_revenue_rank,
    RANK() OVER (PARTITION BY date ORDER BY dividend_yield DESC NULLS LAST) AS div_yield_rank
FROM systematic_equity.factor_data
WHERE pe_ratio IS NOT NULL
   OR pb_ratio IS NOT NULL
   OR ps_ratio IS NOT NULL;

-- ── View: quality factor ranking (higher = better quality) ────────────────────
CREATE OR REPLACE VIEW systematic_equity.quality_factor_ranks AS
SELECT
    ticker,
    date,
    roe,
    roa,
    profit_margin,
    operating_margin,
    gross_margin,
    debt_to_equity,
    current_ratio,
    free_cash_flow,
    -- Rank within each cross-section (higher profitability = better quality rank)
    RANK() OVER (PARTITION BY date ORDER BY roe              DESC NULLS LAST) AS roe_rank,
    RANK() OVER (PARTITION BY date ORDER BY roa              DESC NULLS LAST) AS roa_rank,
    RANK() OVER (PARTITION BY date ORDER BY profit_margin    DESC NULLS LAST) AS profit_margin_rank,
    RANK() OVER (PARTITION BY date ORDER BY operating_margin DESC NULLS LAST) AS operating_margin_rank,
    RANK() OVER (PARTITION BY date ORDER BY gross_margin     DESC NULLS LAST) AS gross_margin_rank,
    RANK() OVER (PARTITION BY date ORDER BY debt_to_equity   ASC  NULLS LAST) AS low_leverage_rank,
    RANK() OVER (PARTITION BY date ORDER BY current_ratio    DESC NULLS LAST) AS liquidity_rank
FROM systematic_equity.factor_data
WHERE roe IS NOT NULL
   OR roa IS NOT NULL
   OR profit_margin IS NOT NULL;

-- ── Sample Queries ─────────────────────────────────────────────────────────────

-- Latest Value + Quality snapshot for all companies:
-- SELECT * FROM systematic_equity.factor_data_latest ORDER BY ticker;

-- Top 20 cheapest stocks by P/E on the most recent date:
-- SELECT ticker, date, pe_ratio, pb_ratio, roe, profit_margin
-- FROM systematic_equity.factor_data_latest
-- WHERE pe_ratio > 0
-- ORDER BY pe_ratio ASC
-- LIMIT 20;

-- Companies ranking in top quartile for BOTH value AND quality (combined score):
-- SELECT v.ticker, v.date,
--        v.pe_rank, v.pb_rank, q.roe_rank, q.profit_margin_rank,
--        (v.pe_rank + v.pb_rank + q.roe_rank + q.profit_margin_rank) AS combined_rank
-- FROM systematic_equity.value_factor_ranks  v
-- JOIN systematic_equity.quality_factor_ranks q
--   ON v.ticker = q.ticker AND v.date = q.date
-- WHERE v.date = (SELECT MAX(date) FROM systematic_equity.factor_data)
-- ORDER BY combined_rank ASC
-- LIMIT 30;

COMMIT;
