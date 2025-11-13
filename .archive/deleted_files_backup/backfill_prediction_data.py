#!/usr/bin/env python3
"""
Backfill market prediction data from free sources

Collects:
- Dividends & Stock Splits (yfinance)
- Earnings Announcements (yfinance)
- News Articles (yfinance)
- Options IV (yfinance)
- Company Fundamentals (yfinance)
- Analyst Ratings (Finnhub - if API key available)
- Economic Indicators (FRED - if API key available)
- Technical Indicators (computed)
"""

import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import yfinance as yf
import pandas as pd
import logging
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_batch
from psycopg2.pool import SimpleConnectionPool

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PredictionDataBackfiller:
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.session = None
        self.db_pool = None
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        self.fred_key = os.getenv("FRED_API_KEY", "")
        
    async def init(self):
        self.session = aiohttp.ClientSession()
        # Initialize DB connection pool
        try:
            self.db_pool = SimpleConnectionPool(
                1, 5,
                host=os.getenv("DB_HOST", "localhost"),
                database=os.getenv("DB_NAME", "marketdata"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
                port=int(os.getenv("DB_PORT", 5432))
            )
        except Exception as e:
            logger.error(f"Failed to initialize DB pool: {e}")
            self.db_pool = None
    
    async def close(self):
        if self.session:
            await self.session.close()
        if self.db_pool:
            self.db_pool.closeall()

    # ============== DIVIDENDS & SPLITS ==============
    async def backfill_dividends(self):
        """Fetch and store dividend history"""
        logger.info("Starting dividends backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping dividends")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    dividends = ticker.dividends
                    
                    if dividends is None or len(dividends) == 0:
                        logger.info(f"{symbol}: No dividends found")
                        continue
                    
                    records = []
                    for date, amount in dividends.items():
                        records.append((
                            symbol,
                            date.date(),  # ex_date
                            None,  # record_date
                            None,  # payment_date
                            float(amount),
                            'dividend',
                            'yfinance',
                            datetime.now()
                        ))
                    
                    # Insert with conflict handling
                    query = """
                    INSERT INTO dividends 
                    (symbol, ex_date, record_date, payment_date, dividend_amount, dividend_type, data_source, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, ex_date, dividend_amount) DO NOTHING
                    """
                    
                    execute_batch(cursor, query, records, page_size=1000)
                    conn.commit()
                    logger.info(f"{symbol}: Inserted {len(records)} dividends")
                    
                except Exception as e:
                    logger.error(f"{symbol}: Dividend fetch failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    async def backfill_stock_splits(self):
        """Fetch and store stock split history"""
        logger.info("Starting stock splits backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping splits")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    splits = ticker.splits
                    
                    if splits is None or len(splits) == 0:
                        logger.info(f"{symbol}: No splits found")
                        continue
                    
                    records = []
                    for date, ratio in splits.items():
                        records.append((
                            symbol,
                            date.date(),
                            float(ratio),
                            f"{ratio:.4f} split",
                            'yfinance',
                            datetime.now()
                        ))
                    
                    query = """
                    INSERT INTO stock_splits 
                    (symbol, split_date, split_ratio, description, data_source, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, split_date, split_ratio) DO NOTHING
                    """
                    
                    execute_batch(cursor, query, records, page_size=1000)
                    conn.commit()
                    logger.info(f"{symbol}: Inserted {len(records)} splits")
                    
                except Exception as e:
                    logger.error(f"{symbol}: Split fetch failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    # ============== EARNINGS & FUNDAMENTALS ==============
    async def backfill_company_fundamentals(self):
        """Fetch and cache company fundamental data"""
        logger.info("Starting company fundamentals backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping fundamentals")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    if not info:
                        logger.warning(f"{symbol}: No info available")
                        continue
                    
                    # Extract available fields
                    query = """
                    INSERT INTO company_fundamentals 
                    (symbol, company_name, sector, industry, market_cap, pe_ratio, pb_ratio, 
                     dividend_yield, current_ratio, debt_to_equity, roe, roa, 
                     current_price, data_source, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        market_cap = EXCLUDED.market_cap,
                        pe_ratio = EXCLUDED.pe_ratio,
                        fetched_at = NOW()
                    """
                    
                    cursor.execute(query, (
                        symbol,
                        info.get('longName'),
                        info.get('sector'),
                        info.get('industry'),
                        info.get('marketCap'),
                        info.get('trailingPE'),
                        info.get('priceToBook'),
                        info.get('dividendYield'),
                        info.get('currentRatio'),
                        info.get('debtToEquity'),
                        info.get('returnOnEquity'),
                        info.get('returnOnAssets'),
                        info.get('currentPrice'),
                        'yfinance',
                        datetime.now()
                    ))
                    
                    conn.commit()
                    logger.info(f"{symbol}: Updated fundamentals")
                    
                except Exception as e:
                    logger.error(f"{symbol}: Fundamentals fetch failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    # ============== NEWS ==============
    async def backfill_news(self):
        """Fetch and store news articles"""
        logger.info("Starting news backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping news")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    news = ticker.news
                    
                    if not news:
                        logger.info(f"{symbol}: No news found")
                        continue
                    
                    records = []
                    for article in news[:100]:  # Limit to 100 recent articles
                        records.append((
                            symbol,
                            datetime.fromtimestamp(article.get('providerPublishTime', 0)),
                            article.get('title', '')[:500],
                            article.get('link', '')[:2048],
                            article.get('source', '')[:100],
                            'yfinance',
                            datetime.now()
                        ))
                    
                    query = """
                    INSERT INTO news_articles 
                    (symbol, news_date, title, url, source, data_source, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, url) DO NOTHING
                    """
                    
                    execute_batch(cursor, query, records, page_size=1000)
                    conn.commit()
                    logger.info(f"{symbol}: Inserted {len(records)} news articles")
                    
                except Exception as e:
                    logger.error(f"{symbol}: News fetch failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    # ============== OPTIONS IV ==============
    async def backfill_options_iv(self):
        """Fetch and store options implied volatility"""
        logger.info("Starting options IV backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping options")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    expirations = ticker.options
                    
                    if not expirations:
                        logger.info(f"{symbol}: No options available")
                        continue
                    
                    records = []
                    
                    # Get nearest and next 2 expirations
                    for expiration in expirations[:3]:
                        try:
                            opt_chain = ticker.option_chain(expiration)
                            
                            # Process calls
                            for _, row in opt_chain.calls.iterrows():
                                records.append((
                                    symbol,
                                    datetime.strptime(expiration, '%Y-%m-%d').date(),
                                    float(row['strike']),
                                    'call',
                                    float(row.get('impliedVolatility', 0)),
                                    int(row.get('openInterest', 0)),
                                    int(row.get('volume', 0)),
                                    float(row.get('lastPrice', 0)),
                                    'yfinance',
                                    datetime.now()
                                ))
                            
                            # Process puts
                            for _, row in opt_chain.puts.iterrows():
                                records.append((
                                    symbol,
                                    datetime.strptime(expiration, '%Y-%m-%d').date(),
                                    float(row['strike']),
                                    'put',
                                    float(row.get('impliedVolatility', 0)),
                                    int(row.get('openInterest', 0)),
                                    int(row.get('volume', 0)),
                                    float(row.get('lastPrice', 0)),
                                    'yfinance',
                                    datetime.now()
                                ))
                        
                        except Exception as e:
                            logger.warning(f"{symbol} {expiration}: Option chain failed: {e}")
                            continue
                    
                    if records:
                        query = """
                        INSERT INTO options_iv 
                        (symbol, expiration_date, strike_price, option_type, 
                         implied_volatility, open_interest, volume, last_price,
                         data_source, fetched_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, expiration_date, strike_price, option_type, updated_at::DATE) 
                        DO NOTHING
                        """
                        
                        execute_batch(cursor, query, records, page_size=1000)
                        conn.commit()
                        logger.info(f"{symbol}: Inserted {len(records)} options")
                
                except Exception as e:
                    logger.error(f"{symbol}: Options fetch failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    # ============== TECHNICAL INDICATORS ==============
    async def backfill_technical_indicators(self):
        """Compute and store technical indicators"""
        logger.info("Starting technical indicators backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping indicators")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="2y")  # 2 years of data
                    
                    if hist.empty:
                        logger.warning(f"{symbol}: No price data for indicators")
                        continue
                    
                    # Calculate indicators
                    hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
                    hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
                    hist['SMA_200'] = hist['Close'].rolling(window=200).mean()
                    
                    hist['EMA_12'] = hist['Close'].ewm(span=12, adjust=False).mean()
                    hist['EMA_26'] = hist['Close'].ewm(span=26, adjust=False).mean()
                    hist['MACD'] = hist['EMA_12'] - hist['EMA_26']
                    hist['MACD_Signal'] = hist['MACD'].ewm(span=9, adjust=False).mean()
                    hist['MACD_Histogram'] = hist['MACD'] - hist['MACD_Signal']
                    
                    # RSI
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    hist['RSI_14'] = 100 - (100 / (1 + rs))
                    
                    # Bollinger Bands
                    hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
                    hist['BB_Std'] = hist['Close'].rolling(window=20).std()
                    hist['BB_Upper'] = hist['BB_Middle'] + (hist['BB_Std'] * 2)
                    hist['BB_Lower'] = hist['BB_Middle'] - (hist['BB_Std'] * 2)
                    
                    # ATR
                    hist['H-L'] = hist['High'] - hist['Low']
                    hist['H-C'] = abs(hist['High'] - hist['Close'].shift())
                    hist['L-C'] = abs(hist['Low'] - hist['Close'].shift())
                    hist['TR'] = hist[['H-L', 'H-C', 'L-C']].max(axis=1)
                    hist['ATR_14'] = hist['TR'].rolling(window=14).mean()
                    
                    # Volume SMA
                    hist['Volume_SMA_20'] = hist['Volume'].rolling(window=20).mean()
                    
                    # Prepare records
                    records = []
                    for idx, row in hist.iterrows():
                        records.append((
                            symbol,
                            idx.date(),
                            float(row.get('RSI_14')) if pd.notna(row.get('RSI_14')) else None,
                            float(row.get('MACD')) if pd.notna(row.get('MACD')) else None,
                            float(row.get('MACD_Signal')) if pd.notna(row.get('MACD_Signal')) else None,
                            float(row.get('MACD_Histogram')) if pd.notna(row.get('MACD_Histogram')) else None,
                            float(row.get('SMA_20')) if pd.notna(row.get('SMA_20')) else None,
                            float(row.get('SMA_50')) if pd.notna(row.get('SMA_50')) else None,
                            float(row.get('SMA_200')) if pd.notna(row.get('SMA_200')) else None,
                            float(row.get('EMA_12')) if pd.notna(row.get('EMA_12')) else None,
                            float(row.get('EMA_26')) if pd.notna(row.get('EMA_26')) else None,
                            float(row.get('BB_Upper')) if pd.notna(row.get('BB_Upper')) else None,
                            float(row.get('BB_Middle')) if pd.notna(row.get('BB_Middle')) else None,
                            float(row.get('BB_Lower')) if pd.notna(row.get('BB_Lower')) else None,
                            float(row.get('ATR_14')) if pd.notna(row.get('ATR_14')) else None,
                            int(row.get('Volume_SMA_20')) if pd.notna(row.get('Volume_SMA_20')) else None,
                            datetime.now()
                        ))
                    
                    query = """
                    INSERT INTO technical_indicators
                    (symbol, indicator_date, rsi_14, macd, macd_signal, macd_histogram,
                     sma_20, sma_50, sma_200, ema_12, ema_26, bb_upper, bb_middle, bb_lower,
                     atr_14, volume_sma_20, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, indicator_date) DO UPDATE SET
                        rsi_14 = EXCLUDED.rsi_14,
                        macd = EXCLUDED.macd,
                        macd_signal = EXCLUDED.macd_signal,
                        macd_histogram = EXCLUDED.macd_histogram,
                        sma_20 = EXCLUDED.sma_20,
                        sma_50 = EXCLUDED.sma_50,
                        sma_200 = EXCLUDED.sma_200,
                        computed_at = NOW()
                    """
                    
                    execute_batch(cursor, query, records, page_size=1000)
                    conn.commit()
                    logger.info(f"{symbol}: Computed and stored {len(records)} technical indicators")
                    
                except Exception as e:
                    logger.error(f"{symbol}: Indicators computation failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    # ============== FINNHUB (Optional) ==============
    async def backfill_analyst_ratings(self):
        """Fetch analyst ratings from Finnhub"""
        if not self.finnhub_key:
            logger.info("Skipping analyst ratings - no Finnhub API key")
            return
        
        logger.info("Starting analyst ratings backfill...")
        
        if not self.db_pool:
            logger.warning("No DB connection, skipping ratings")
            return
        
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            for symbol in self.symbols:
                try:
                    url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={self.finnhub_key}"
                    
                    async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            if data and len(data) > 0:
                                latest = data[0]
                                
                                query = """
                                INSERT INTO analyst_ratings
                                (symbol, rating_date, buy_count, hold_count, sell_count, 
                                 strong_buy_count, strong_sell_count, data_source, fetched_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (symbol, rating_date) DO NOTHING
                                """
                                
                                cursor.execute(query, (
                                    symbol,
                                    datetime.fromisoformat(latest['period']),
                                    latest.get('buy'),
                                    latest.get('hold'),
                                    latest.get('sell'),
                                    latest.get('strongBuy'),
                                    latest.get('strongSell'),
                                    'finnhub',
                                    datetime.now()
                                ))
                                
                                conn.commit()
                                logger.info(f"{symbol}: Analyst ratings updated")
                        else:
                            logger.warning(f"{symbol}: Finnhub returned {resp.status}")
                            
                except Exception as e:
                    logger.error(f"{symbol}: Analyst ratings failed: {e}")
                    conn.rollback()
        
        finally:
            self.db_pool.putconn(conn)

    async def run_all(self):
        """Run all backfill tasks"""
        await self.init()
        
        try:
            print("\n" + "="*60)
            print("PREDICTION DATA BACKFILL")
            print("="*60)
            
            await self.backfill_dividends()
            await self.backfill_stock_splits()
            await self.backfill_company_fundamentals()
            await self.backfill_news()
            await self.backfill_options_iv()
            await self.backfill_technical_indicators()
            await self.backfill_analyst_ratings()
            
            print("\n" + "="*60)
            print("BACKFILL COMPLETE")
            print("="*60)
            
        finally:
            await self.close()


async def main():
    import sys
    
    # Default symbols
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    
    if len(sys.argv) > 1:
        symbols = sys.argv[1:].split(",")
    
    backfiller = PredictionDataBackfiller(symbols)
    await backfiller.run_all()


if __name__ == "__main__":
    asyncio.run(main())
