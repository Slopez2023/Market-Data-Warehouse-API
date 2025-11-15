#!/usr/bin/env python3
"""Backfill dividends, earnings, and other enrichment data."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.services.database_service import DatabaseService
from src.clients.polygon_client import PolygonClient

async def backfill_dividends(db, polygon_client, symbols):
    """Backfill dividends for symbols."""
    print(f"\n{'='*60}")
    print(f"BACKFILLING DIVIDENDS for {len(symbols)} symbols")
    print(f"{'='*60}\n")
    
    success = 0
    failed = 0
    total_records = 0
    
    start_date = (datetime.utcnow() - timedelta(days=365*5)).date().isoformat()
    end_date = datetime.utcnow().date().isoformat()
    
    for symbol in symbols:
        try:
            divs = await polygon_client.fetch_dividends(symbol, start_date, end_date)
            if divs:
                session = db.SessionLocal()
                try:
                    from sqlalchemy import text
                    for div in divs:
                        session.execute(text("""
                            INSERT INTO dividends 
                            (symbol, ex_dividend_date, payment_date, record_date, declared_date, amount, currency)
                            VALUES (:symbol, :ex_date, :pay_date, :rec_date, :decl_date, :amount, 'USD')
                            ON CONFLICT DO NOTHING
                        """), {
                            'symbol': symbol,
                            'ex_date': div.get('exDividendDate'),
                            'pay_date': div.get('paymentDate'),
                            'rec_date': div.get('recordDate'),
                            'decl_date': div.get('declaredDate'),
                            'amount': float(div.get('dividend', 0))
                        })
                    session.commit()
                    success += 1
                    total_records += len(divs)
                    print(f"  ✓ {symbol}: {len(divs)} dividends")
                except Exception as e:
                    session.rollback()
                    failed += 1
                    print(f"  ✗ {symbol}: {e}")
                finally:
                    session.close()
            else:
                success += 1
                print(f"  - {symbol}: No dividends")
        except Exception as e:
            failed += 1
            print(f"  ✗ {symbol}: {e}")
        
        await asyncio.sleep(0.5)  # Rate limit
    
    print(f"\nDividends: {success} success, {failed} failed, {total_records} total records")
    return success, failed

async def backfill_earnings(db, polygon_client, symbols):
    """Backfill earnings for symbols."""
    print(f"\n{'='*60}")
    print(f"BACKFILLING EARNINGS for {len(symbols)} symbols")
    print(f"{'='*60}\n")
    
    success = 0
    failed = 0
    total_records = 0
    
    for symbol in symbols:
        try:
            earnings = await polygon_client.fetch_earnings(symbol, "", "")
            if earnings:
                session = db.SessionLocal()
                try:
                    from sqlalchemy import text
                    for earn in earnings:
                        session.execute(text("""
                            INSERT INTO earnings 
                            (symbol, report_date, earnings_per_share, revenue)
                            VALUES (:symbol, :date, :eps, :rev)
                            ON CONFLICT DO NOTHING
                        """), {
                            'symbol': symbol,
                            'date': earn.get('reportDate') or earn.get('actualEPS'),
                            'eps': float(earn.get('actualEPS', 0)),
                            'rev': None
                        })
                    session.commit()
                    success += 1
                    total_records += len(earnings)
                    print(f"  ✓ {symbol}: {len(earnings)} earnings")
                except Exception as e:
                    session.rollback()
                    failed += 1
                    print(f"  ✗ {symbol}: {e}")
                finally:
                    session.close()
            else:
                success += 1
                print(f"  - {symbol}: No earnings")
        except Exception as e:
            failed += 1
            print(f"  ✗ {symbol}: {e}")
        
        await asyncio.sleep(0.5)
    
    print(f"\nEarnings: {success} success, {failed} failed, {total_records} total records")
    return success, failed

async def backfill_stock_splits(db, polygon_client, symbols):
    """Backfill stock splits for symbols."""
    print(f"\n{'='*60}")
    print(f"BACKFILLING STOCK SPLITS for {len(symbols)} symbols")
    print(f"{'='*60}\n")
    
    success = 0
    failed = 0
    total_records = 0
    
    start_date = (datetime.utcnow() - timedelta(days=365*5)).date().isoformat()
    end_date = datetime.utcnow().date().isoformat()
    
    for symbol in symbols:
        try:
            splits = await polygon_client.fetch_splits(symbol, start_date, end_date)
            if splits:
                session = db.SessionLocal()
                try:
                    from sqlalchemy import text
                    for split in splits:
                        session.execute(text("""
                            INSERT INTO stock_splits 
                            (symbol, split_from, split_to, execution_date)
                            VALUES (:symbol, :from, :to, :date)
                            ON CONFLICT DO NOTHING
                        """), {
                            'symbol': symbol,
                            'from': int(split.get('splitFrom', 1)),
                            'to': int(split.get('splitTo', 1)),
                            'date': split.get('executionDate')
                        })
                    session.commit()
                    success += 1
                    total_records += len(splits)
                    print(f"  ✓ {symbol}: {len(splits)} splits")
                except Exception as e:
                    session.rollback()
                    failed += 1
                    print(f"  ✗ {symbol}: {e}")
                finally:
                    session.close()
            else:
                success += 1
                print(f"  - {symbol}: No splits")
        except Exception as e:
            failed += 1
            print(f"  ✗ {symbol}: {e}")
        
        await asyncio.sleep(0.5)
    
    print(f"\nStock Splits: {success} success, {failed} failed, {total_records} total records")
    return success, failed

async def main():
    """Run backfill."""
    db = DatabaseService(config.database_url)
    polygon_client = PolygonClient(config.polygon_api_key)
    
    # Get symbols
    session = db.SessionLocal()
    try:
        from sqlalchemy import text
        symbols = [s[0] for s in session.execute(text("SELECT DISTINCT symbol FROM tracked_symbols LIMIT 25")).fetchall()]
    finally:
        session.close()
    
    print(f"Backfilling for {len(symbols)} symbols: {', '.join(symbols)}")
    
    # Backfill each data type
    await backfill_dividends(db, polygon_client, symbols)
    await backfill_stock_splits(db, polygon_client, symbols)
    await backfill_earnings(db, polygon_client, symbols)
    
    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
