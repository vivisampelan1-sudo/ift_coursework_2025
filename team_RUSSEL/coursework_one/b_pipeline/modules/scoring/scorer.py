"""
Amundi / JPM Factor Scoring Engine.

Implements the methodology from:
  - Lepetit et al., "Revisiting Quality Investing", Amundi Asset Management
  - JPM quantitative factor construction approach

Pipeline:
    Raw metric
        → Winsorize (5th / 95th percentile)  [clip outliers]
        → Percentile rank  (0 → 1, pct=True)  [cross-sectional]
        → Z-score  (inverse normal, scipy.stats.norm.ppf)  [Amundi Sec 2.3]
        → Weighted average within dimension
        → Re-rank dimension average → dimension Z-score
        → Composite = 0.5 × Value_Z + 0.5 × Quality_Z
        → Quintile Q1 (best) … Q5 (worst)

Value metrics (JPM approach):
    book_to_price  = book_value_per_share / price       weight 15%
    earnings_yield = trailing_EPS / price                weight 35%
    cashflow_yield = free_cash_flow / market_cap         weight 35%
    dividend_yield = annual_dividend / price             weight 15%

Quality metrics (Amundi approach — approximated from available data):
    gpa    = gross_margin   (gross profit proxy; true GPA = gross_profit/assets)   weight 33%
    wca    = current_ratio  (working capital quality proxy)                         weight 17%
    ltde   = -debt_to_equity  (leverage, inverted so lower leverage = better)      weight 33%
    roa    = roa            (return on assets; earnings quality proxy)              weight 17%

Note on approximations:
    True GPA = (Revenue − COGS) / Total Assets.  We derive this as
    gross_margin × roa / profit_margin when all three are available,
    falling back to gross_margin alone.
    True WCA = (Current Assets − Current Liabilities) / Total Assets.
    We approximate with current_ratio (the ratio of the same numerator/denominator
    before dividing by Total Assets).
    True LTDE uses only long-term debt; we use total_debt/equity (more conservative).
    True AccCF requires operating and investing cash flows separately; we
    substitute ROA which is the most available profitability signal.

:module: b_pipeline.modules.scoring.scorer
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ── Building blocks ────────────────────────────────────────────────────────


def winsorize(series: pd.Series, lower: float = 0.05, upper: float = 0.95) -> pd.Series:
    """Clip at 5th/95th percentile to remove outliers (Step 1)."""
    lo = series.quantile(lower)
    hi = series.quantile(upper)
    return series.clip(lower=lo, upper=hi)


def to_percentile(series: pd.Series) -> pd.Series:
    """Rank each stock from 0 to 1 within universe (Step 2)."""
    return series.rank(pct=True)


def percentile_to_zscore(percentile_series: pd.Series) -> pd.Series:
    """
    Convert percentile ranks to z-scores via inverse normal distribution (Step 3).

    Exactly replicates Amundi Section 2.3:  Z = Φ⁻¹(percentile)
    Clipped at [0.001, 0.999] to avoid ±∞ at extremes.
    """
    clipped = percentile_series.clip(0.001, 0.999)
    return pd.Series(stats.norm.ppf(clipped), index=percentile_series.index)


def metric_to_zscore(series: pd.Series) -> pd.Series:
    """Full pipeline for one metric: winsorize → percentile → z-score."""
    valid = series.dropna()
    if len(valid) < 5:
        return pd.Series(np.nan, index=series.index)
    result = pd.Series(np.nan, index=series.index)
    result[valid.index] = percentile_to_zscore(to_percentile(winsorize(valid)))
    return result


# ── Metric derivation ──────────────────────────────────────────────────────


def compute_value_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive Value factor metrics from factor_data columns.

    Returns DataFrame with columns:
        book_to_price, earnings_yield, cashflow_yield, dividend_yield
    """
    out = pd.DataFrame(index=df.index)

    # Book-to-Price = 1 / P/B  (lower P/B = better value = higher B/P)
    out["book_to_price"] = np.where(
        df["close"] > 0,
        df["book_value"] / df["close"],
        np.nan
    )

    # Earnings Yield = EPS / Price  (inverse of P/E)
    out["earnings_yield"] = np.where(
        (df["close"] > 0) & (df["eps"] > 0),
        df["eps"] / df["close"],
        np.nan
    )

    # Cash Flow Yield = Free Cash Flow / Market Cap
    out["cashflow_yield"] = np.where(
        df["market_cap"] > 0,
        df["free_cash_flow"] / df["market_cap"],
        np.nan
    )

    # Dividend Yield (already stored; 0 for non-payers so they don't get penalised)
    out["dividend_yield"] = df["dividend_yield"].fillna(0.0)

    return out


def compute_quality_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive Quality factor metrics from factor_data columns.

    Returns DataFrame with columns:
        gpa, wca, ltde, roa
    """
    out = pd.DataFrame(index=df.index)

    # GPA (Gross Profit Asset) proxy.
    # True: (Revenue - COGS) / Total Assets
    # Derived: gross_margin × roa / profit_margin   [when profit_margin ≠ 0]
    # Fallback: gross_margin  (Novy-Marx 2013 profitability measure)
    gpa_full = np.where(
        (df["profit_margin"].notna()) & (df["profit_margin"] != 0) & df["roa"].notna(),
        df["gross_margin"] * df["roa"] / df["profit_margin"],
        np.nan
    )
    gpa_fallback = df["gross_margin"]
    out["gpa"] = np.where(pd.notna(gpa_full), gpa_full, gpa_fallback)

    # WCA (Working Capital Asset) proxy.
    # True: (Current Assets - Current Liabilities) / Total Assets
    # Proxy: current_ratio  (higher = more liquid = better quality)
    out["wca"] = df["current_ratio"]

    # LTDE (Long-term Debt / Equity) — inverted so higher = better quality.
    # We use total_debt/equity (debt_to_equity) as long-term debt is unavailable.
    out["ltde"] = -pd.to_numeric(df["debt_to_equity"], errors="coerce")  # invert

    # AccCF proxy: ROA (Return on Assets)
    # True AccCF = -(Net Income - Operating CFO - Investing CFO) / Avg NOA
    # Higher ROA = higher asset efficiency = better quality
    out["roa"] = df["roa"]

    return out


# ── Score computation ──────────────────────────────────────────────────────


VALUE_WEIGHTS = {
    "book_to_price":  0.15,
    "earnings_yield": 0.35,
    "cashflow_yield": 0.35,
    "dividend_yield": 0.15,
}

QUALITY_WEIGHTS = {
    "gpa":  0.33,
    "wca":  0.17,
    "ltde": 0.33,
    "roa":  0.17,
}


def _score_dimension(
    metrics_df: pd.DataFrame,
    weights: dict,
    label: str,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Score one dimension (value or quality):
        1. Per-metric z-score
        2. Weighted average of z-scores
        3. Re-rank → dimension z-score

    Returns (dimension_zscore, per_metric_zscore_df).
    """
    zscores = {}
    for col, w in weights.items():
        if col not in metrics_df.columns:
            logger.warning(f"{label}: column '{col}' missing — skipping")
            continue
        zscores[col] = metric_to_zscore(metrics_df[col])
        valid_n = metrics_df[col].notna().sum()
        logger.debug(f"  {col}: {valid_n} valid firms")

    z_df = pd.DataFrame(zscores)

    # Per-firm weighted average — skip NaN metrics rather than propagating them.
    # For each firm, the weight is re-normalised to the sum of available metrics.
    weight_row = pd.Series({c: weights[c] for c in z_df.columns})
    weighted_sum  = z_df.mul(weight_row).sum(axis=1, skipna=True)
    available_w   = z_df.notna().mul(weight_row).sum(axis=1)
    dim_avg = weighted_sum / available_w.replace(0, np.nan)

    # Re-rank dimension average → dimension z-score
    valid_dim = dim_avg.dropna()
    dim_z = pd.Series(np.nan, index=dim_avg.index)
    if len(valid_dim) >= 5:
        dim_z[valid_dim.index] = percentile_to_zscore(to_percentile(valid_dim))

    return dim_z, z_df


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute full Amundi/JPM composite scores for a cross-sectional universe.

    :param df: DataFrame with Dec-31 snapshot data from factor_data.
               Must include: close, eps, book_value, free_cash_flow,
               market_cap, dividend_yield, gross_margin, revenue,
               profit_margin, roa, debt_to_equity, current_ratio.
    :returns: DataFrame with all metric z-scores, value_score, quality_score,
              composite_score, composite_percentile, quintile.
    """
    val_metrics = compute_value_metrics(df)
    qual_metrics = compute_quality_metrics(df)

    val_z, val_detail = _score_dimension(val_metrics, VALUE_WEIGHTS, "Value")
    qual_z, qual_detail = _score_dimension(qual_metrics, QUALITY_WEIGHTS, "Quality")

    # Composite: 50% Value + 50% Quality  (Section 7 of the spec)
    composite_raw = pd.Series(np.nan, index=df.index)
    both = val_z.notna() & qual_z.notna()
    val_only = val_z.notna() & qual_z.isna()
    qual_only = val_z.isna() & qual_z.notna()

    composite_raw[both]     = 0.5 * val_z[both] + 0.5 * qual_z[both]
    composite_raw[val_only] = val_z[val_only]
    composite_raw[qual_only] = qual_z[qual_only]

    # Final re-rank → composite z-score
    valid_comp = composite_raw.dropna()
    composite_z = pd.Series(np.nan, index=df.index)
    if len(valid_comp) >= 5:
        composite_pct = to_percentile(valid_comp)
        composite_z[valid_comp.index] = percentile_to_zscore(composite_pct)
        # Composite percentile (0–1, higher = better)
        comp_percentile = pd.Series(np.nan, index=df.index)
        comp_percentile[valid_comp.index] = composite_pct
    else:
        comp_percentile = pd.Series(np.nan, index=df.index)

    # Quintile: Q1 = best (top 20%), Q5 = worst (bottom 20%)
    quintile = pd.Series("", index=df.index)
    valid_pct = comp_percentile.dropna()
    if len(valid_pct) >= 5:
        labels = ["Q5", "Q4", "Q3", "Q2", "Q1"]   # ascending pct → Q5 lowest
        quintile[valid_pct.index] = pd.qcut(
            valid_pct, q=5, labels=labels
        ).astype(str)

    result = pd.DataFrame({
        # Raw metrics
        "book_to_price":  val_metrics["book_to_price"],
        "earnings_yield": val_metrics["earnings_yield"],
        "cashflow_yield": val_metrics["cashflow_yield"],
        "dividend_yield": val_metrics["dividend_yield"],
        "gpa":   qual_metrics["gpa"],
        "wca":   qual_metrics["wca"],
        "ltde":  qual_metrics["ltde"],
        "roa_q": qual_metrics["roa"],
        # Per-metric z-scores
        **{f"{c}_z": val_detail[c] for c in val_detail.columns},
        **{f"{c}_z": qual_detail[c] for c in qual_detail.columns},
        # Dimension and composite scores
        "value_score":           val_z,
        "quality_score":         qual_z,
        "composite_score":       composite_z,
        "composite_percentile":  comp_percentile,
        "quintile":              quintile,
    }, index=df.index)

    return result
