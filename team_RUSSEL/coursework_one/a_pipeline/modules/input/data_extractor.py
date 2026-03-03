"""
Data extraction module for financial data.

Extracts Value Factor and Quality Factor metrics using ``yfinance``.
Current data uses the ``stock.info`` snapshot. Historical data combines
monthly OHLCV prices with a **hybrid approach**:

- **Quarterly** financial statements (~5 most recent quarters) provide
  the highest-granularity point-in-time fundamentals.
- **Annual** financial statements (~4 fiscal years) extend coverage
  further back, filling the gap where quarterly data is unavailable.

Both are merged onto monthly price rows using an as-of (backward)
join, so each month gets the most recent fundamentals known at that
time.

:module: modules.input.data_extractor
"""
from datetime import datetime
import pandas as pd
import numpy as np
from typing import List
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class DataExtractor:
    """
    Extracts financial data using Value Factor and Quality Factor metrics.

    :param config: Configuration dictionary with ``extraction.lookback_years``.
    :type config: dict
    """

    def __init__(self, config: dict):
        """
        Initialise data extractor.

        :param config: Configuration dictionary.
        :type config: dict
        """
        self.config = config
        self.lookback_years = config['extraction']['lookback_years']

    # ────────────────────────────────────────────────────────────────
    # Helper utilities
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_info_value(info: dict, key: str):
        """
        Safely extract a scalar from a yfinance info dict.

        :param info: ``stock.info`` dictionary.
        :type info: dict
        :param key: Key to look up.
        :type key: str
        :returns: Scalar or ``None``.
        """
        try:
            val = info.get(key, None) if isinstance(info, dict) else None
            if val is not None and hasattr(val, 'item'):
                val = val.item()
            if not isinstance(val, (int, float, str)):
                val = None
            if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                val = None
            return val
        except Exception:
            return None

    @staticmethod
    def _safe_scalar(val):
        """Convert to plain Python scalar; ``None`` for NaN/Inf/NA."""
        if val is None:
            return None
        try:
            if hasattr(val, 'item'):
                val = val.item()
            if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                return None
            if pd.isna(val):
                return None
            return val
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_divide(num, den):
        """Safely divide; returns ``None`` on error/zero/NaN."""
        try:
            if num is None or den is None or den == 0:
                return None
            result = float(num) / float(den)
            if np.isnan(result) or np.isinf(result):
                return None
            return result
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def _get_stmt_value(self, df, row_name, col):
        """
        Safely get a value from a financial statement DataFrame.

        :param df: Financial statement (rows = line items, cols = dates).
        :param row_name: Line item name.
        :param col: Date column.
        :returns: Scalar or ``None``.
        """
        try:
            if df is not None and row_name in df.index and col in df.columns:
                return self._safe_scalar(df.loc[row_name, col])
        except Exception:
            pass
        return None

    # ────────────────────────────────────────────────────────────────
    # Current data extraction
    # ────────────────────────────────────────────────────────────────

    def extract_company_data(self, company: dict) -> pd.DataFrame:
        """
        Extract current Value/Quality Factor data for a single company.

        :param company: Dict with ``ticker``, ``name`` keys.
        :type company: dict
        :returns: Single-row DataFrame.
        :rtype: pandas.DataFrame
        """
        ticker = company['ticker']
        try:
            stock = yf.Ticker(ticker)
            info = stock.info if isinstance(stock.info, dict) else {}

            def _v(key):
                return self._safe_info_value(info, key)

            data = {
                'company_id': ticker, 'ticker': ticker,
                'company_name': company['name'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'open': None, 'high': None, 'low': None,
                'close': None, 'volume': None,
                'current_price': _v('currentPrice'),
                'market_cap': _v('marketCap'),
                'pe_ratio': _v('trailingPE'),
                'forward_pe': _v('forwardPE'),
                'pb_ratio': _v('priceToBook'),
                'ps_ratio': _v('priceToSalesTrailing12Months'),
                'book_value': _v('bookValue'),
                'eps': _v('trailingEps'),
                'forward_eps': _v('forwardEps'),
                'enterprise_value': _v('enterpriseValue'),
                'ev_to_ebitda': _v('enterpriseToEbitda'),
                'ev_to_revenue': _v('enterpriseToRevenue'),
                'roe': _v('returnOnEquity'),
                'roa': _v('returnOnAssets'),
                'debt_to_equity': _v('debtToEquity'),
                'current_ratio': _v('currentRatio'),
                'quick_ratio': _v('quickRatio'),
                'profit_margin': _v('profitMargins'),
                'operating_margin': _v('operatingMargins'),
                'gross_margin': _v('grossMargins'),
                'free_cash_flow': _v('freeCashflow'),
                'operating_cash_flow': _v('operatingCashflow'),
                'revenue_growth': _v('revenueGrowth'),
                'earnings_growth': _v('earningsGrowth'),
                'revenue': _v('totalRevenue'),
                'total_debt': _v('totalDebt'),
                'total_cash': _v('totalCash'),
                'ebitda': _v('ebitda'),
                'dividend_yield': _v('dividendYield'),
                'sector': _v('sector'), 'industry': _v('industry'),
                'db_sector': company.get('gics_sector'),
                'db_industry': company.get('gics_industry'),
            }
            logger.info(f"Successfully extracted current data for {ticker}")
            return pd.DataFrame([data])

        except Exception as e:
            logger.error(f"Failed to extract {ticker}: {e}")
            return pd.DataFrame([{
                'company_id': ticker, 'ticker': ticker,
                'company_name': company['name'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'error': str(e)
            }])

    # ────────────────────────────────────────────────────────────────
    # Build fundamentals time-series (annual + quarterly)
    # ────────────────────────────────────────────────────────────────

    def _build_fundamentals_from_statements(self, stmt_inc, stmt_bal, stmt_cf,
                                            is_annual: bool) -> pd.DataFrame:
        """
        Build fundamentals from either annual or quarterly statements.

        For annual statements, EPS/revenue/etc. are already full-year
        figures. For quarterly, TTM (trailing 4 quarters) is computed.

        :param stmt_inc: Income statement DataFrame.
        :param stmt_bal: Balance sheet DataFrame.
        :param stmt_cf: Cash flow DataFrame.
        :param is_annual: If True, values are already annualised.
        :returns: DataFrame with one row per period-end date.
        :rtype: pandas.DataFrame
        """
        _get = self._get_stmt_value

        if stmt_inc is None or stmt_inc.empty or stmt_bal is None or stmt_bal.empty:
            return pd.DataFrame()

        periods = sorted(stmt_inc.columns)
        records = []

        for i, p_date in enumerate(periods):
            # --- EPS ---
            if is_annual:
                # Annual EPS is already full-year
                eps_val = _get(stmt_inc, 'Diluted EPS', p_date)
                if eps_val is None:
                    eps_val = _get(stmt_inc, 'Basic EPS', p_date)
                net_income_val = _get(stmt_inc, 'Net Income', p_date)
                revenue_val = _get(stmt_inc, 'Total Revenue', p_date)
                ebitda_val = _get(stmt_inc, 'EBITDA', p_date)
                op_income_val = _get(stmt_inc, 'Operating Income', p_date)
                gross_profit_val = _get(stmt_inc, 'Gross Profit', p_date)
            else:
                # Quarterly: need TTM (sum of last 4 quarters)
                def _ttm(row_name, fallback=None):
                    if i < 3:
                        return None
                    vals = []
                    for j in range(4):
                        v = _get(stmt_inc, row_name, periods[i - j])
                        if v is None and fallback:
                            v = _get(stmt_inc, fallback, periods[i - j])
                        if v is not None:
                            vals.append(v)
                    return sum(vals) if len(vals) == 4 else None

                eps_val = _ttm('Diluted EPS', 'Basic EPS')
                net_income_val = _ttm('Net Income')
                revenue_val = _ttm('Total Revenue')
                ebitda_val = _ttm('EBITDA')
                op_income_val = _ttm('Operating Income')
                gross_profit_val = _ttm('Gross Profit')

            # --- Balance Sheet (always point-in-time) ---
            equity = _get(stmt_bal, 'Stockholders Equity', p_date)
            if equity is None:
                equity = _get(stmt_bal, 'Common Stock Equity', p_date)
            total_assets = _get(stmt_bal, 'Total Assets', p_date)
            total_debt = _get(stmt_bal, 'Total Debt', p_date)
            # Cash & cash equivalents (needed for proper EV = MC + Debt - Cash)
            cash = _get(stmt_bal, 'Cash And Cash Equivalents', p_date)
            if cash is None:
                cash = _get(stmt_bal, 'Cash Cash Equivalents And Short Term Investments', p_date)
            shares = _get(stmt_bal, 'Ordinary Shares Number', p_date)
            if shares is None:
                shares = _get(stmt_bal, 'Share Issued', p_date)
            # Current ratio = Current Assets / Current Liabilities (from balance sheet)
            current_assets = _get(stmt_bal, 'Current Assets', p_date)
            current_liabilities = _get(stmt_bal, 'Current Liabilities', p_date)
            current_ratio_val = self._safe_divide(current_assets, current_liabilities)

            # Skip periods where key data is all NaN
            if eps_val is None and equity is None and shares is None:
                continue

            book_value_ps = self._safe_divide(equity, shares)
            roe = self._safe_divide(net_income_val, equity)
            roa = self._safe_divide(net_income_val, total_assets)
            d2e = self._safe_divide(total_debt, equity)
            profit_margin = self._safe_divide(net_income_val, revenue_val)
            operating_margin = self._safe_divide(op_income_val, revenue_val)
            gross_margin = self._safe_divide(gross_profit_val, revenue_val)

            # Cash flow
            fcf = None
            if stmt_cf is not None and not stmt_cf.empty:
                fcf = _get(stmt_cf, 'Free Cash Flow', p_date)

            records.append({
                'f_date': p_date,
                'eps': eps_val,
                'net_income': net_income_val,
                'revenue': revenue_val,
                'ebitda': ebitda_val,
                'book_value': book_value_ps,
                'shares': shares,
                'total_debt': total_debt,
                'cash': cash,
                'roe': roe,
                'roa': roa,
                'debt_to_equity': d2e,
                'current_ratio': current_ratio_val,
                'profit_margin': profit_margin,
                'operating_margin': operating_margin,
                'gross_margin': gross_margin,
                'free_cash_flow': fcf,
            })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.sort_values('f_date').reset_index(drop=True)
        return df

    def _build_combined_fundamentals(self, stock) -> pd.DataFrame:
        """
        Build a combined fundamentals time-series using annual data
        for older periods and quarterly data for recent periods.

        Quarterly data takes priority where both exist (higher granularity).

        :param stock: yfinance Ticker object.
        :returns: Combined fundamentals DataFrame sorted by date.
        :rtype: pandas.DataFrame
        """
        # Build annual fundamentals
        annual_df = self._build_fundamentals_from_statements(
            stock.income_stmt, stock.balance_sheet, stock.cashflow,
            is_annual=True
        )

        # Build quarterly fundamentals
        quarterly_df = self._build_fundamentals_from_statements(
            stock.quarterly_income_stmt, stock.quarterly_balance_sheet,
            stock.quarterly_cashflow, is_annual=False
        )

        if annual_df.empty and quarterly_df.empty:
            return pd.DataFrame()

        if annual_df.empty:
            return quarterly_df

        if quarterly_df.empty:
            return annual_df

        # Combine: use quarterly where available, annual for older periods
        # Find the earliest quarterly date
        earliest_quarterly = pd.to_datetime(quarterly_df['f_date']).min()

        # Keep only annual rows BEFORE the earliest quarterly date
        annual_df['_dt'] = pd.to_datetime(annual_df['f_date'])
        annual_older = annual_df[annual_df['_dt'] < earliest_quarterly].drop(columns=['_dt'])

        # Concatenate: older annual + all quarterly
        combined = pd.concat([annual_older, quarterly_df], ignore_index=True)
        combined = combined.sort_values('f_date').reset_index(drop=True)

        logger.debug(
            f"Combined fundamentals: {len(annual_older)} annual + "
            f"{len(quarterly_df)} quarterly = {len(combined)} total periods"
        )
        return combined

    # ────────────────────────────────────────────────────────────────
    # Merge fundamentals onto monthly prices
    # ────────────────────────────────────────────────────────────────

    def _merge_fundamentals_to_monthly(self, hist_df: pd.DataFrame,
                                       fund_df: pd.DataFrame) -> pd.DataFrame:
        """
        Forward-fill fundamentals onto monthly price rows via as-of join.

        :param hist_df: Monthly OHLCV with ``date`` and ``close`` columns.
        :param fund_df: Fundamentals with ``f_date`` column.
        :returns: Enriched DataFrame.
        :rtype: pandas.DataFrame
        """
        if fund_df.empty:
            for col in ['pe_ratio', 'pb_ratio', 'ps_ratio', 'eps', 'forward_eps',
                        'ev_to_ebitda', 'ev_to_revenue', 'book_value', 'market_cap',
                        'roe', 'roa', 'debt_to_equity', 'profit_margin',
                        'operating_margin', 'gross_margin', 'free_cash_flow',
                        'revenue', 'total_debt', 'ebitda', 'dividend_yield',
                        'forward_pe', 'current_ratio']:
                hist_df[col] = None
            return hist_df

        # Normalise datetimes to same dtype (datetime64[ns], no timezone)
        hist_df['_date_dt'] = pd.to_datetime(hist_df['date']).dt.tz_localize(None).astype('datetime64[ns]')
        fund_df['_f_date_dt'] = pd.to_datetime(fund_df['f_date']).dt.tz_localize(None).astype('datetime64[ns]')

        hist_df = hist_df.sort_values('_date_dt').reset_index(drop=True)
        fund_df = fund_df.sort_values('_f_date_dt').reset_index(drop=True)

        # As-of merge: each monthly row gets the most recent fundamentals
        merged = pd.merge_asof(
            hist_df,
            fund_df,
            left_on='_date_dt',
            right_on='_f_date_dt',
            direction='backward'
        )

        # Backfill raw fundamentals so months before the earliest statement
        # date (which would otherwise be NULL) receive the earliest available
        # values.  ffill() handles any residual mid-series gaps.
        # This is done on raw inputs BEFORE price-dependent ratios are
        # computed, so ratios still reflect the actual price at each date.
        raw_fund_cols = [
            'eps', 'book_value', 'shares', 'revenue', 'ebitda', 'total_debt',
            'cash', 'roe', 'roa', 'debt_to_equity', 'current_ratio',
            'profit_margin', 'operating_margin', 'gross_margin',
            'free_cash_flow', 'net_income',
        ]
        for col in raw_fund_cols:
            if col in merged.columns:
                merged[col] = merged[col].bfill().ffill()

        # Price-dependent ratios
        merged['pe_ratio'] = merged.apply(
            lambda r: self._safe_divide(r.get('close'), r.get('eps')), axis=1)
        merged['pb_ratio'] = merged.apply(
            lambda r: self._safe_divide(r.get('close'), r.get('book_value')), axis=1)
        merged['ps_ratio'] = merged.apply(
            lambda r: self._safe_divide(
                r.get('close') * r.get('shares') if r.get('close') and r.get('shares') else None,
                r.get('revenue')),
            axis=1)
        merged['market_cap'] = merged.apply(
            lambda r: r.get('close') * r.get('shares')
            if r.get('close') and r.get('shares') else None,
            axis=1)
        # EV = Market Cap + Total Debt - Cash  (per investment spec)
        merged['enterprise_value'] = merged.apply(
            lambda r: (r.get('market_cap') or 0) + (r.get('total_debt') or 0) - (r.get('cash') or 0)
            if r.get('market_cap') else None, axis=1)
        merged['ev_to_ebitda'] = merged.apply(
            lambda r: self._safe_divide(r.get('enterprise_value'), r.get('ebitda')), axis=1)
        merged['ev_to_revenue'] = merged.apply(
            lambda r: self._safe_divide(r.get('enterprise_value'), r.get('revenue')), axis=1)

        # Not available historically
        merged['forward_pe'] = None
        merged['forward_eps'] = None

        # Clean up
        drop_cols = ['_date_dt', '_f_date_dt', 'f_date', 'shares',
                     'net_income', 'enterprise_value']
        merged.drop(columns=[c for c in drop_cols if c in merged.columns],
                    inplace=True, errors='ignore')

        return merged

    # ────────────────────────────────────────────────────────────────
    # Historical extraction
    # ────────────────────────────────────────────────────────────────

    def extract_historical_data(self, company: dict) -> pd.DataFrame:
        """
        Extract historical monthly OHLCV with point-in-time fundamentals.

        Uses annual statements for older periods and quarterly for recent,
        merged onto monthly prices via as-of join.

        :param company: Dict with ``ticker`` and ``name``.
        :type company: dict
        :returns: DataFrame with one row per month.
        :rtype: pandas.DataFrame
        """
        ticker = company['ticker']
        try:
            from dateutil.relativedelta import relativedelta

            end_date = datetime.now()
            start_date = end_date - relativedelta(years=self.lookback_years)

            stock = yf.Ticker(ticker)
            info = stock.info if isinstance(stock.info, dict) else {}

            # Skip non-USD stocks
            currency = info.get('currency', None) if isinstance(info, dict) else None
            if isinstance(currency, str) and currency != 'USD':
                logger.info(f"Skipping {ticker} - currency {currency}, not USD")
                return pd.DataFrame()

            # Monthly price history
            hist = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1mo'
            )

            if hist.empty:
                logger.warning(f"No historical data for {ticker}")
                return pd.DataFrame()

            hist['company_id'] = ticker
            hist['ticker'] = ticker
            hist['company_name'] = company['name']
            hist['db_sector'] = company.get('gics_sector')
            hist['db_industry'] = company.get('gics_industry')
            hist = hist.reset_index()

            # Snap dates to month-end, strip timezone
            hist['date'] = (
                pd.to_datetime(hist['Date'])
                .dt.tz_localize(None)
                .dt.to_period('M')
                .dt.to_timestamp('M')
                .dt.strftime('%Y-%m-%d')
            )
            hist['current_price'] = hist['Close']
            hist.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            }, inplace=True)

            # Build combined annual + quarterly fundamentals
            fund_df = self._build_combined_fundamentals(stock)

            if fund_df.empty:
                logger.warning(f"No financial statements for {ticker} — fallback to info")

                def _v(key):
                    return self._safe_info_value(info, key)
                hist['pe_ratio'] = _v('trailingPE')
                hist['forward_pe'] = _v('forwardPE')
                hist['pb_ratio'] = _v('priceToBook')
                hist['ps_ratio'] = _v('priceToSalesTrailing12Months')
                hist['market_cap'] = _v('marketCap')
                hist['eps'] = _v('trailingEps')
                hist['forward_eps'] = _v('forwardEps')
                hist['ev_to_ebitda'] = _v('enterpriseToEbitda')
                hist['ev_to_revenue'] = _v('enterpriseToRevenue')
                hist['book_value'] = _v('bookValue')
                hist['roe'] = _v('returnOnEquity')
                hist['roa'] = _v('returnOnAssets')
                hist['debt_to_equity'] = _v('debtToEquity')
                hist['current_ratio'] = _v('currentRatio')
                hist['profit_margin'] = _v('profitMargins')
                hist['operating_margin'] = _v('operatingMargins')
                hist['gross_margin'] = _v('grossMargins')
                hist['free_cash_flow'] = _v('freeCashflow')
                hist['revenue'] = _v('totalRevenue')
                hist['total_debt'] = _v('totalDebt')
                hist['ebitda'] = _v('ebitda')
                hist['dividend_yield'] = _v('dividendYield')
            else:
                hist = self._merge_fundamentals_to_monthly(hist, fund_df)

            # Compute trailing 12-month dividend yield from actual dividend payments.
            # This replaces any placeholder None and gives a proper historical time
            # series — non-payers receive 0.0 so they are not penalised.
            try:
                dividends = stock.dividends
                if dividends is not None and not dividends.empty:
                    div = dividends.copy()
                    div.index = pd.to_datetime(div.index).tz_localize(None)
                    hist_dates = pd.to_datetime(hist['date'])
                    ttm_divs = []
                    for dt in hist_dates:
                        ttm_start = dt - pd.DateOffset(months=12)
                        ttm_divs.append(
                            float(div[(div.index > ttm_start) & (div.index <= dt)].sum())
                        )
                    ttm_series = pd.Series(ttm_divs, index=hist.index)
                    close_num = pd.to_numeric(hist['close'], errors='coerce')
                    hist['dividend_yield'] = np.where(
                        (close_num > 0) & (ttm_series > 0),
                        ttm_series / close_num,
                        0.0,
                    )
                else:
                    hist['dividend_yield'] = 0.0
            except Exception:
                hist['dividend_yield'] = pd.to_numeric(
                    hist.get('dividend_yield', pd.Series(0.0, index=hist.index)),
                    errors='coerce',
                ).fillna(0.0)

            logger.info(f"Extracted {len(hist)} historical records for {ticker}")
            return hist

        except Exception as e:
            logger.exception(f"Failed historical extraction for {ticker}: {e}")
            return pd.DataFrame()

    # ────────────────────────────────────────────────────────────────
    # Bulk extraction
    # ────────────────────────────────────────────────────────────────

    def extract_bulk_data(self, companies: List[dict]) -> pd.DataFrame:
        """
        Extract current data for multiple companies.

        :param companies: List of company dicts.
        :returns: Combined DataFrame.
        """
        all_data = []
        for i, c in enumerate(companies, 1):
            df = self.extract_company_data(c)
            all_data.append(df)
            logger.info(f"[{i}/{len(companies)}] Current: {c['ticker']}")
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def extract_bulk_historical_data(self, companies: List[dict]) -> pd.DataFrame:
        """
        Extract historical data for multiple companies.

        :param companies: List of company dicts.
        :returns: Combined DataFrame.
        """
        all_data = []
        for i, c in enumerate(companies, 1):
            df = self.extract_historical_data(c)
            if not df.empty:
                all_data.append(df)
                logger.info(f"[{i}/{len(companies)}] Historical: {c['ticker']}")
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
