"""
Missing data imputation using the Lepetit et al. (Amundi) method.

Reference:
    Lepetit, A. et al. "Revisiting Quality Investing", Amundi Asset Management.

Method (Equations 10-11):
    Forward:  X̂_{i,t} = X_{i,t-1} × (1 + G_{sector,t})
    Backward: X̂_{i,t} = X_{i,t+1} / (1 + G_{sector,t+1})

    where G_{sector,t} = cross-sectional median YoY growth rate of variable X
                         across all firms j in the same GICS sector at time t
                         that have valid data in both t-1 and t.

Behaviour:
    - Works on Dec-31 annual snapshots to compute yearly growth rates.
    - Applies forward pass first (fill future gaps), then backward pass
      (fill early gaps before the first available statement).
    - Structural NULLs for EBITDA in Financials / Real Estate are excluded
      from imputation (banks and REITs do not report EBITDA).
    - After imputation, all monthly rows for that (ticker, year) are updated.

Usage:
    cd team_RUSSEL/coursework_one
    poetry run python scripts/impute_missing_data.py
"""
import logging
import os
import sys

import numpy as np
import pandas as pd
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from a_pipeline.modules.utils.config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Variables to impute and whether to skip certain sectors
# (sector=None means impute for all sectors)
IMPUTE_CONFIG = {
    "eps":              {"skip_sectors": None},
    "revenue":          {"skip_sectors": None},
    "ebitda":           {"skip_sectors": {"Financials", "Real Estate"}},
    "total_debt":       {"skip_sectors": None},
    "cash":             {"skip_sectors": None},
    "book_value":       {"skip_sectors": None},
    "roe":              {"skip_sectors": None},
    "roa":              {"skip_sectors": None},
    "profit_margin":    {"skip_sectors": None},
    "operating_margin": {"skip_sectors": None},
    "gross_margin":     {"skip_sectors": {"Financials"}},
}


def load_annual_snapshots(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """
    Load Dec-31 annual snapshots from factor_data.

    Uses month-end December rows as a proxy for yearly fundamentals.
    Each row represents one firm-year data point.
    """
    query = """
        SELECT
            ticker,
            date,
            db_sector,
            eps, revenue, ebitda, total_debt, cash, book_value,
            roe, roa, profit_margin, operating_margin, gross_margin
        FROM systematic_equity.factor_data
        WHERE EXTRACT(MONTH FROM date) = 12
          AND EXTRACT(DAY FROM date) = 31
          AND date <= CURRENT_DATE
        ORDER BY ticker, date
    """
    df = pd.read_sql(query, conn, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    logger.info(
        f"Loaded {len(df)} annual snapshots for {df['ticker'].nunique()} tickers "
        f"across years {df['year'].min()}–{df['year'].max()}"
    )
    return df


def compute_sector_growth_rates(
    df: pd.DataFrame, var: str, skip_sectors: set | None
) -> dict:
    """
    Compute median YoY growth rates per sector per year for variable `var`.

    Returns dict: {year_t -> pd.Series(sector -> median_growth_rate)}
    """
    # Build wide pivot: index=ticker, columns=year
    pivot = df.pivot(index="ticker", columns="year", values=var)
    sector_map = df.drop_duplicates("ticker").set_index("ticker")["db_sector"]

    years = sorted(pivot.columns)
    sector_growth = {}

    for i in range(1, len(years)):
        t_prev, t = years[i - 1], years[i]

        # Firms with valid data in both years
        valid = pivot[[t_prev, t]].dropna()
        # Exclude zero base (would produce inf growth)
        valid = valid[valid[t_prev] != 0]

        if valid.empty:
            continue

        valid = valid.copy()
        valid["growth"] = valid[t] / valid[t_prev] - 1
        valid["sector"] = valid.index.map(sector_map)

        # Exclude structural-NULL sectors from growth calculation too
        if skip_sectors:
            valid = valid[~valid["sector"].isin(skip_sectors)]

        if valid.empty:
            continue

        # Clip extreme growth rates (>500% or <-80%) to reduce outlier distortion
        valid["growth"] = valid["growth"].clip(-0.80, 5.00)

        sector_medians = valid.groupby("sector")["growth"].median()
        sector_growth[t] = sector_medians

    return sector_growth


def impute_variable(
    df: pd.DataFrame,
    var: str,
    sector_growth: dict,
    skip_sectors: set | None
) -> pd.DataFrame:
    """
    Apply Lepetit forward then backward imputation for one variable.

    Returns a DataFrame with columns [ticker, year, {var}_imputed].
    Only rows that were originally NULL and are now filled are returned
    (rows already populated are unchanged).
    """
    pivot = df.pivot(index="ticker", columns="year", values=var).copy()
    sector_map = df.drop_duplicates("ticker").set_index("ticker")["db_sector"]
    years = sorted(pivot.columns)

    # Track which values were originally NULL
    originally_null = pivot.isna().copy()

    # ── Forward pass: X̂_{i,t} = X_{i,t-1} × (1 + G_{sector,t}) ──
    for i in range(1, len(years)):
        t_prev, t = years[i - 1], years[i]
        if t not in sector_growth:
            continue
        for ticker in pivot.index:
            if not originally_null.loc[ticker, t]:
                continue  # not missing — leave unchanged
            if pd.isna(pivot.loc[ticker, t_prev]):
                continue  # no anchor value available
            sector = sector_map.get(ticker)
            if skip_sectors and sector in skip_sectors:
                continue
            g = sector_growth[t].get(sector, np.nan)
            if pd.notna(g) and not np.isinf(g):
                pivot.loc[ticker, t] = pivot.loc[ticker, t_prev] * (1 + g)

    # ── Backward pass: X̂_{i,t} = X_{i,t+1} / (1 + G_{sector,t+1}) ──
    for i in range(len(years) - 2, -1, -1):
        t, t_next = years[i], years[i + 1]
        if t_next not in sector_growth:
            continue
        for ticker in pivot.index:
            if not originally_null.loc[ticker, t]:
                continue  # not missing — leave unchanged
            if pd.isna(pivot.loc[ticker, t]):
                # Still NULL after forward pass — try backward
                if pd.isna(pivot.loc[ticker, t_next]):
                    continue  # no anchor value available
                sector = sector_map.get(ticker)
                if skip_sectors and sector in skip_sectors:
                    continue
                g = sector_growth[t_next].get(sector, np.nan)
                if pd.notna(g) and not np.isinf(g) and abs(1 + g) > 1e-9:
                    pivot.loc[ticker, t] = pivot.loc[ticker, t_next] / (1 + g)

    # Return only originally-NULL rows that are now filled
    imputed_mask = originally_null & pivot.notna()
    result_rows = []
    for ticker in pivot.index:
        for year in years:
            if imputed_mask.loc[ticker, year]:
                result_rows.append({
                    "ticker": ticker,
                    "year": year,
                    f"{var}_imputed": pivot.loc[ticker, year],
                })

    return pd.DataFrame(result_rows) if result_rows else pd.DataFrame(
        columns=["ticker", "year", f"{var}_imputed"]
    )


def update_database(
    conn: psycopg2.extensions.connection,
    imputed_df: pd.DataFrame,
    var: str
) -> int:
    """
    Write imputed values back to factor_data for all monthly rows
    within the same (ticker, year) where the variable was NULL.
    """
    if imputed_df.empty:
        return 0

    cur = conn.cursor()
    updated = 0

    for _, row in imputed_df.iterrows():
        val = row[f"{var}_imputed"]
        if pd.isna(val) or np.isinf(val):
            continue
        cur.execute(
            f"""
            UPDATE systematic_equity.factor_data
            SET {var} = %s
            WHERE ticker = %s
              AND EXTRACT(YEAR FROM date) = %s
              AND {var} IS NULL
            """,
            (float(val), row["ticker"], int(row["year"]))
        )
        updated += cur.rowcount

    conn.commit()
    cur.close()
    return updated


def null_rate_report(conn: psycopg2.extensions.connection) -> None:
    """Print NULL rates for imputed variables before and after."""
    query = """
        SELECT
            EXTRACT(YEAR FROM date)::int AS year,
            COUNT(*) AS total,
            ROUND(100.0 * COUNT(eps)            / COUNT(*), 1) AS eps_pct,
            ROUND(100.0 * COUNT(revenue)        / COUNT(*), 1) AS rev_pct,
            ROUND(100.0 * COUNT(ebitda)         / COUNT(*), 1) AS ebitda_pct,
            ROUND(100.0 * COUNT(roe)            / COUNT(*), 1) AS roe_pct,
            ROUND(100.0 * COUNT(profit_margin)  / COUNT(*), 1) AS pm_pct
        FROM systematic_equity.factor_data
        WHERE date BETWEEN '2021-01-01' AND '2025-12-31'
          AND EXTRACT(MONTH FROM date) = 12
          AND EXTRACT(DAY FROM date) = 31
        GROUP BY 1 ORDER BY 1
    """
    df = pd.read_sql(query, conn)
    print("\n── Coverage Report (Dec-31 snapshots) ──")
    print(df.to_string(index=False))
    print()


def main() -> None:
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

    try:
        logger.info("=" * 60)
        logger.info("Lepetit et al. Missing Data Imputation")
        logger.info("=" * 60)

        logger.info("\n── Before imputation ──")
        null_rate_report(conn)

        df = load_annual_snapshots(conn)

        total_imputed = 0
        for var, cfg in IMPUTE_CONFIG.items():
            skip = cfg["skip_sectors"]
            null_count = df[var].isna().sum()

            if null_count == 0:
                logger.info(f"{var:20s}: no NULLs — skipping")
                continue

            logger.info(
                f"{var:20s}: {null_count} NULLs across "
                f"{df['ticker'].nunique()} tickers — imputing..."
            )

            growth_rates = compute_sector_growth_rates(df, var, skip)
            imputed_df = impute_variable(df, var, growth_rates, skip)

            if imputed_df.empty:
                logger.info(f"{var:20s}: no values could be imputed")
                continue

            n_updated = update_database(conn, imputed_df, var)
            logger.info(
                f"{var:20s}: imputed {len(imputed_df)} firm-years "
                f"→ updated {n_updated} monthly rows in DB"
            )
            total_imputed += n_updated

        logger.info(f"\nTotal monthly rows updated: {total_imputed}")

        logger.info("\n── After imputation ──")
        null_rate_report(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
