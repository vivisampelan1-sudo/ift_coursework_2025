"""
Unit tests for b_pipeline.modules.scoring.scorer

Covers the full Amundi/JPM scoring pipeline:
  winsorize → to_percentile → percentile_to_zscore → metric_to_zscore
  compute_value_metrics → compute_quality_metrics → compute_scores
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from b_pipeline.modules.scoring.scorer import (
    _MIN_GROUP_SIZE,
    _score_dimension,
    compute_quality_metrics,
    compute_scores,
    compute_value_metrics,
    metric_to_zscore,
    percentile_to_zscore,
    to_percentile,
    winsorize,
    VALUE_WEIGHTS,
    QUALITY_WEIGHTS,
)


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def uniform_series():
    """10 evenly-spaced values, no NaNs."""
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])


@pytest.fixture
def series_with_outliers():
    """8 normal values + 2 extreme outliers."""
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 1000.0, -1000.0])


@pytest.fixture
def cross_section_df():
    """
    Minimal cross-sectional DataFrame for 10 fictitious firms.
    All required columns present; no NaNs; EPS > 0.
    """
    np.random.seed(42)
    n = 10
    tickers = [f"T{i:02d}" for i in range(n)]
    return pd.DataFrame({
        "close":         [10, 20, 15, 25, 30, 12, 18, 22, 28, 35],
        "eps":           [1.0, 2.5, 1.2, 3.0, 4.0, 0.8, 1.8, 2.0, 3.5, 5.0],
        "book_value":    [8, 15, 10, 18, 20, 9, 14, 16, 22, 28],
        "free_cash_flow":[5e6, 12e6, 8e6, 20e6, 30e6, 4e6, 10e6, 15e6, 25e6, 40e6],
        "market_cap":    [50e6, 120e6, 80e6, 200e6, 300e6, 40e6, 100e6, 150e6, 250e6, 400e6],
        "dividend_yield":[0.02, 0.0, 0.015, 0.03, 0.01, 0.0, 0.025, 0.0, 0.02, 0.035],
        "gross_margin":  [0.50, 0.40, 0.45, 0.55, 0.60, 0.35, 0.48, 0.52, 0.58, 0.65],
        "profit_margin": [0.10, 0.12, 0.08, 0.15, 0.20, 0.06, 0.10, 0.13, 0.18, 0.25],
        "roa":           [0.08, 0.10, 0.07, 0.12, 0.15, 0.05, 0.09, 0.11, 0.14, 0.18],
        "debt_to_equity":[0.5, 1.0, 0.8, 0.3, 0.2, 1.5, 0.7, 0.6, 0.4, 0.1],
        "current_ratio": [1.5, 2.0, 1.8, 2.5, 3.0, 1.2, 1.9, 2.2, 2.8, 3.5],
        "db_sector":     ["Tech"] * 5 + ["Health"] * 5,
    }, index=tickers)


@pytest.fixture
def cross_section_no_sector(cross_section_df):
    """Same DataFrame without db_sector column."""
    return cross_section_df.drop(columns=["db_sector"])


# ── winsorize ──────────────────────────────────────────────────────────────


class TestWinsorize:
    def test_clips_upper_outlier(self, series_with_outliers):
        result = winsorize(series_with_outliers)
        assert result.max() < 1000.0

    def test_clips_lower_outlier(self, series_with_outliers):
        result = winsorize(series_with_outliers)
        assert result.min() > -1000.0

    def test_preserves_middle_values(self, uniform_series):
        result = winsorize(uniform_series)
        # Inner values should be unchanged (only tails are clipped)
        assert float(result[4]) == pytest.approx(5.0)
        assert float(result[5]) == pytest.approx(6.0)

    def test_no_change_when_no_outliers(self):
        s = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
        result = winsorize(s)
        pd.testing.assert_series_equal(result, s)

    def test_custom_bounds(self, uniform_series):
        result = winsorize(uniform_series, lower=0.10, upper=0.90)
        lo = uniform_series.quantile(0.10)
        hi = uniform_series.quantile(0.90)
        assert result.min() >= lo
        assert result.max() <= hi


# ── to_percentile ──────────────────────────────────────────────────────────


class TestToPercentile:
    def test_range_zero_to_one(self, uniform_series):
        result = to_percentile(uniform_series)
        assert result.min() > 0.0
        assert result.max() <= 1.0

    def test_monotone(self, uniform_series):
        result = to_percentile(uniform_series)
        assert list(result) == sorted(result)

    def test_median_near_half(self, uniform_series):
        result = to_percentile(uniform_series)
        # Middle ranks should be near 0.5
        assert abs(result.iloc[4] - 0.5) < 0.15

    def test_tied_values_equal_ranks(self):
        s = pd.Series([1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0, 5.0, 5.0])
        result = to_percentile(s)
        assert result.iloc[0] == result.iloc[1]
        assert result.iloc[2] == result.iloc[3]


# ── percentile_to_zscore ───────────────────────────────────────────────────


class TestPercentileToZscore:
    def test_median_maps_to_zero(self):
        s = pd.Series([0.5])
        result = percentile_to_zscore(s)
        assert float(result.iloc[0]) == pytest.approx(0.0, abs=1e-10)

    def test_high_percentile_positive_z(self):
        s = pd.Series([0.9])
        result = percentile_to_zscore(s)
        assert float(result.iloc[0]) > 0

    def test_low_percentile_negative_z(self):
        s = pd.Series([0.1])
        result = percentile_to_zscore(s)
        assert float(result.iloc[0]) < 0

    def test_clips_at_boundaries(self):
        s = pd.Series([0.0, 1.0])
        result = percentile_to_zscore(s)
        # Should not produce ±inf — clipped at 0.001 / 0.999
        assert np.isfinite(float(result.iloc[0]))
        assert np.isfinite(float(result.iloc[1]))

    def test_symmetric(self):
        lo = percentile_to_zscore(pd.Series([0.1]))
        hi = percentile_to_zscore(pd.Series([0.9]))
        assert float(lo.iloc[0]) == pytest.approx(-float(hi.iloc[0]), abs=1e-6)

    def test_matches_scipy_ppf(self):
        s = pd.Series([0.25, 0.5, 0.75])
        result = percentile_to_zscore(s)
        expected = stats.norm.ppf([0.25, 0.5, 0.75])
        np.testing.assert_allclose(result.values, expected, rtol=1e-6)


# ── metric_to_zscore ──────────────────────────────────────────────────────


class TestMetricToZscore:
    def test_universe_wide_no_sectors(self, uniform_series):
        result = metric_to_zscore(uniform_series)
        # All values should be scored
        assert result.notna().all()

    def test_universe_wide_approx_zero_mean(self, uniform_series):
        result = metric_to_zscore(uniform_series)
        assert abs(result.mean()) < 0.5

    def test_nan_inputs_propagate_as_nan(self):
        s = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = metric_to_zscore(s)
        assert np.isnan(result.iloc[2])

    def test_below_min_group_size_all_nan(self):
        s = pd.Series([1.0, 2.0, 3.0])  # < _MIN_GROUP_SIZE=5
        result = metric_to_zscore(s)
        assert result.isna().all()

    def test_sector_neutral_computed_within_sector(self, uniform_series):
        # Two sectors of 5 firms each; sector-neutral z-scores should differ
        # from universe-wide when group distributions differ.
        sectors = pd.Series(["A"] * 5 + ["B"] * 5, index=uniform_series.index)
        result_sector = metric_to_zscore(uniform_series, sectors=sectors)
        result_universe = metric_to_zscore(uniform_series)
        # Results should differ because each sector is scored independently
        assert not result_sector.equals(result_universe)

    def test_sector_neutral_all_firms_scored_when_sector_large_enough(self, uniform_series):
        sectors = pd.Series(["A"] * 5 + ["B"] * 5, index=uniform_series.index)
        result = metric_to_zscore(uniform_series, sectors=sectors)
        assert result.notna().all()

    def test_small_sector_pooled_into_residual(self):
        # 7 firms in "A", 2 in "B" (below min), 2 in "C" (below min)
        # B and C are pooled → 4 firms < 5, so they remain NaN
        s = pd.Series(range(11), dtype=float)
        sectors = pd.Series(["A"] * 7 + ["B"] * 2 + ["C"] * 2, index=s.index)
        result = metric_to_zscore(s, sectors=sectors)
        # A firms (7) should be scored
        assert result.iloc[:7].notna().all()
        # B+C firms (4 pooled) < MIN_GROUP_SIZE → NaN
        assert result.iloc[7:].isna().all()

    def test_nan_sectors_included_via_unknown_fallback(self):
        # 5 firms with real sector, 5 with NaN sector (go to __unknown__ group)
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        sectors = pd.Series(["Tech"] * 5 + [np.nan] * 5, index=s.index)
        result = metric_to_zscore(s, sectors=sectors)
        # Both groups have 5 firms — all should be scored
        assert result.notna().all()


# ── compute_value_metrics ─────────────────────────────────────────────────


class TestComputeValueMetrics:
    def test_book_to_price_formula(self):
        df = pd.DataFrame({
            "close": [10.0], "eps": [1.0], "book_value": [5.0],
            "free_cash_flow": [1e6], "market_cap": [1e7], "dividend_yield": [0.02],
        })
        result = compute_value_metrics(df)
        assert float(result["book_to_price"].iloc[0]) == pytest.approx(5.0 / 10.0)

    def test_earnings_yield_formula(self):
        df = pd.DataFrame({
            "close": [20.0], "eps": [2.0], "book_value": [10.0],
            "free_cash_flow": [1e6], "market_cap": [1e7], "dividend_yield": [0.0],
        })
        result = compute_value_metrics(df)
        assert float(result["earnings_yield"].iloc[0]) == pytest.approx(2.0 / 20.0)

    def test_earnings_yield_nan_when_eps_negative(self):
        df = pd.DataFrame({
            "close": [10.0], "eps": [-1.0], "book_value": [5.0],
            "free_cash_flow": [1e6], "market_cap": [1e7], "dividend_yield": [0.0],
        })
        result = compute_value_metrics(df)
        assert np.isnan(result["earnings_yield"].iloc[0])

    def test_cashflow_yield_formula(self):
        df = pd.DataFrame({
            "close": [10.0], "eps": [1.0], "book_value": [5.0],
            "free_cash_flow": [2e6], "market_cap": [10e6], "dividend_yield": [0.0],
        })
        result = compute_value_metrics(df)
        assert float(result["cashflow_yield"].iloc[0]) == pytest.approx(2e6 / 10e6)

    def test_dividend_yield_nan_filled_to_zero(self):
        df = pd.DataFrame({
            "close": [10.0], "eps": [1.0], "book_value": [5.0],
            "free_cash_flow": [1e6], "market_cap": [1e7],
            "dividend_yield": [np.nan],
        })
        result = compute_value_metrics(df)
        assert float(result["dividend_yield"].iloc[0]) == 0.0

    def test_book_to_price_nan_when_close_zero(self):
        df = pd.DataFrame({
            "close": [0.0], "eps": [1.0], "book_value": [5.0],
            "free_cash_flow": [1e6], "market_cap": [1e7], "dividend_yield": [0.0],
        })
        result = compute_value_metrics(df)
        assert np.isnan(result["book_to_price"].iloc[0])

    def test_output_columns(self, cross_section_df):
        result = compute_value_metrics(cross_section_df)
        assert set(result.columns) == {"book_to_price", "earnings_yield",
                                       "cashflow_yield", "dividend_yield"}

    def test_output_index_preserved(self, cross_section_df):
        result = compute_value_metrics(cross_section_df)
        assert list(result.index) == list(cross_section_df.index)


# ── compute_quality_metrics ───────────────────────────────────────────────


class TestComputeQualityMetrics:
    def _make_df(self, **kwargs):
        defaults = {
            "gross_margin": 0.5, "profit_margin": 0.1, "roa": 0.08,
            "current_ratio": 1.5, "debt_to_equity": 0.5,
        }
        defaults.update(kwargs)
        return pd.DataFrame([defaults])

    def test_gpa_full_formula(self):
        df = self._make_df(gross_margin=0.5, roa=0.1, profit_margin=0.2)
        result = compute_quality_metrics(df)
        expected_gpa = 0.5 * 0.1 / 0.2
        assert float(result["gpa"].iloc[0]) == pytest.approx(expected_gpa)

    def test_gpa_fallback_to_gross_margin(self):
        # profit_margin = 0 → division would fail → fall back to gross_margin
        df = self._make_df(gross_margin=0.6, roa=0.1, profit_margin=0.0)
        result = compute_quality_metrics(df)
        assert float(result["gpa"].iloc[0]) == pytest.approx(0.6)

    def test_wca_is_current_ratio(self):
        df = self._make_df(current_ratio=2.3)
        result = compute_quality_metrics(df)
        assert float(result["wca"].iloc[0]) == pytest.approx(2.3)

    def test_ltde_is_inverted_debt_to_equity(self):
        df = self._make_df(debt_to_equity=1.5)
        result = compute_quality_metrics(df)
        assert float(result["ltde"].iloc[0]) == pytest.approx(-1.5)

    def test_roa_passthrough(self):
        df = self._make_df(roa=0.12)
        result = compute_quality_metrics(df)
        assert float(result["roa"].iloc[0]) == pytest.approx(0.12)

    def test_output_columns(self, cross_section_df):
        result = compute_quality_metrics(cross_section_df)
        assert set(result.columns) == {"gpa", "wca", "ltde", "roa"}

    def test_output_index_preserved(self, cross_section_df):
        result = compute_quality_metrics(cross_section_df)
        assert list(result.index) == list(cross_section_df.index)

    def test_ltde_nan_passthrough(self):
        df = self._make_df(debt_to_equity=np.nan)
        result = compute_quality_metrics(df)
        assert np.isnan(result["ltde"].iloc[0])


# ── compute_scores (end-to-end) ───────────────────────────────────────────


class TestComputeScores:
    def test_output_columns_present(self, cross_section_df):
        result = compute_scores(cross_section_df)
        expected_cols = {
            "book_to_price", "earnings_yield", "cashflow_yield", "dividend_yield",
            "gpa", "wca", "ltde", "roa_q",
            "book_to_price_z", "earnings_yield_z", "cashflow_yield_z", "dividend_yield_z",
            "gpa_z", "wca_z", "ltde_z", "roa_z",
            "value_score", "quality_score", "composite_score",
            "composite_percentile", "quintile",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_output_index_preserved(self, cross_section_df):
        result = compute_scores(cross_section_df)
        assert list(result.index) == list(cross_section_df.index)

    def test_quintile_labels(self, cross_section_df):
        result = compute_scores(cross_section_df)
        valid_quintiles = {"Q1", "Q2", "Q3", "Q4", "Q5", ""}
        assert set(result["quintile"].unique()).issubset(valid_quintiles)

    def test_q1_is_best_highest_composite(self, cross_section_df):
        result = compute_scores(cross_section_df)
        q1_mean = result[result["quintile"] == "Q1"]["composite_score"].mean()
        q5_mean = result[result["quintile"] == "Q5"]["composite_score"].mean()
        assert q1_mean > q5_mean

    def test_composite_percentile_range(self, cross_section_df):
        result = compute_scores(cross_section_df)
        valid_pct = result["composite_percentile"].dropna()
        assert valid_pct.between(0.0, 1.0).all()

    def test_all_firms_get_scores_when_data_complete(self, cross_section_df):
        result = compute_scores(cross_section_df)
        assert result["composite_score"].notna().all()

    def test_sector_neutral_when_db_sector_present(self, cross_section_df, cross_section_no_sector):
        result_with = compute_scores(cross_section_df)
        result_without = compute_scores(cross_section_no_sector)
        # Scores differ because sector-neutral vs universe-wide z-scoring
        assert not result_with["value_score"].equals(result_without["value_score"])

    def test_below_min_firms_returns_all_nan_scores(self):
        # Only 3 firms — below _MIN_GROUP_SIZE for any reliable z-score
        df = pd.DataFrame({
            "close": [10.0, 20.0, 30.0],
            "eps": [1.0, 2.0, 3.0],
            "book_value": [5.0, 10.0, 15.0],
            "free_cash_flow": [1e6, 2e6, 3e6],
            "market_cap": [10e6, 20e6, 30e6],
            "dividend_yield": [0.01, 0.02, 0.03],
            "gross_margin": [0.4, 0.5, 0.6],
            "profit_margin": [0.1, 0.15, 0.2],
            "roa": [0.05, 0.08, 0.12],
            "debt_to_equity": [0.5, 1.0, 0.3],
            "current_ratio": [1.5, 2.0, 2.5],
        }, index=["A", "B", "C"])
        result = compute_scores(df)
        assert result["composite_score"].isna().all()

    def test_negative_eps_excluded_from_earnings_yield(self, cross_section_df):
        df = cross_section_df.copy()
        df.loc["T00", "eps"] = -1.0  # set one firm's EPS negative
        result = compute_scores(df)
        # earnings_yield should be NaN for the loss-making firm
        assert np.isnan(result.loc["T00", "earnings_yield"])

    def test_value_score_is_z_score(self, cross_section_df):
        result = compute_scores(cross_section_df)
        # Value score is a z-score (inverse-normal transformed) — should span roughly ±2
        vs = result["value_score"].dropna()
        assert vs.abs().max() < 4.0

    def test_no_inf_values_in_output(self, cross_section_df):
        result = compute_scores(cross_section_df)
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            assert not np.isinf(result[col].dropna()).any(), f"Inf found in {col}"


# ── _score_dimension ──────────────────────────────────────────────────────


class TestScoreDimension:
    def _make_metrics_df(self, n=10):
        np.random.seed(0)
        return pd.DataFrame({
            "book_to_price": np.random.uniform(0.1, 1.0, n),
            "earnings_yield": np.random.uniform(0.02, 0.15, n),
            "cashflow_yield": np.random.uniform(0.01, 0.10, n),
            "dividend_yield": np.random.uniform(0.0, 0.05, n),
        }, index=[f"T{i}" for i in range(n)])

    def test_returns_series_and_dataframe(self):
        metrics = self._make_metrics_df()
        dim_z, detail = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        assert isinstance(dim_z, pd.Series)
        assert isinstance(detail, pd.DataFrame)

    def test_detail_has_all_metric_columns(self):
        metrics = self._make_metrics_df()
        _, detail = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        for col in VALUE_WEIGHTS:
            assert col in detail.columns

    def test_dim_z_all_finite_complete_data(self):
        metrics = self._make_metrics_df()
        dim_z, _ = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        assert dim_z.notna().all()
        assert np.isfinite(dim_z).all()

    def test_skipna_weighted_average_handles_nan_metric(self):
        metrics = self._make_metrics_df()
        # Set one metric to NaN for all firms — remaining weights should renormalise
        metrics["dividend_yield"] = np.nan
        dim_z, _ = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        # Firms should still receive a score from the other 3 metrics
        assert dim_z.notna().all()

    def test_all_nan_metric_still_scores_firms(self):
        metrics = self._make_metrics_df()
        # Even with 2 metrics NaN, remaining 2 should still produce scores
        metrics["dividend_yield"] = np.nan
        metrics["book_to_price"] = np.nan
        dim_z, _ = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        assert dim_z.notna().all()

    def test_sector_neutral_passed_correctly(self):
        metrics = self._make_metrics_df(n=10)
        sectors = pd.Series(["A"] * 5 + ["B"] * 5, index=metrics.index)
        dim_z_sector, _ = _score_dimension(metrics, VALUE_WEIGHTS, "Value", sectors=sectors)
        dim_z_universe, _ = _score_dimension(metrics, VALUE_WEIGHTS, "Value")
        # Sector-neutral should differ from universe-wide
        assert not dim_z_sector.equals(dim_z_universe)


# ── VALUE_WEIGHTS and QUALITY_WEIGHTS constants ───────────────────────────


class TestWeightConstants:
    def test_value_weights_sum_to_one(self):
        assert sum(VALUE_WEIGHTS.values()) == pytest.approx(1.0)

    def test_quality_weights_sum_to_one(self):
        assert sum(QUALITY_WEIGHTS.values()) == pytest.approx(1.0, abs=0.01)

    def test_value_metrics_covered(self):
        assert set(VALUE_WEIGHTS.keys()) == {
            "book_to_price", "earnings_yield", "cashflow_yield", "dividend_yield"
        }

    def test_quality_metrics_covered(self):
        assert set(QUALITY_WEIGHTS.keys()) == {"gpa", "wca", "ltde", "roa"}
