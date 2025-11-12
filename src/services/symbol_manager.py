"""Symbol management service - CRUD for tracked symbols"""

from typing import List, Optional
import asyncpg
from datetime import datetime

from src.services.structured_logging import StructuredLogger
from src.config import ALLOWED_TIMEFRAMES, DEFAULT_TIMEFRAMES

logger = StructuredLogger(__name__)


class SymbolManager:
    """Manages tracked symbols in database"""
    
    def __init__(self, database_url: str):
        """
        Initialize symbol manager.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
    
    async def add_symbol(self, symbol: str, asset_class: str = "stock") -> dict:
        """
        Add a new symbol to tracking.
        
        Args:
            symbol: Stock ticker or crypto symbol (e.g., AAPL, BTC)
            asset_class: Type of asset (stock, crypto, etf)
        
        Returns:
            Dict with inserted symbol info
        
        Raises:
            ValueError: If symbol already exists
        """
        symbol = symbol.upper()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Check if symbol already exists
            existing = await conn.fetchrow(
                "SELECT id FROM tracked_symbols WHERE symbol = $1",
                symbol
            )
            
            if existing:
                await conn.close()
                raise ValueError(f"Symbol {symbol} already tracked")
            
            # Insert new symbol
            row = await conn.fetchrow(
                """
                INSERT INTO tracked_symbols (symbol, asset_class, active)
                VALUES ($1, $2, TRUE)
                RETURNING id, symbol, asset_class, active, date_added, backfill_status, timeframes
                """,
                symbol, asset_class
            )
            
            await conn.close()
            
            result = {
                'id': row['id'],
                'symbol': row['symbol'],
                'asset_class': row['asset_class'],
                'active': row['active'],
                'date_added': row['date_added'].isoformat() if row['date_added'] else None,
                'backfill_status': row['backfill_status'],
                'timeframes': list(row['timeframes']) if row['timeframes'] else DEFAULT_TIMEFRAMES
            }
            
            logger.info(f"Symbol added: {symbol}", extra=result)
            return result
        
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error adding symbol {symbol}", extra={"error": str(e)})
            raise
    
    async def get_all_symbols(self, active_only: bool = True) -> List[dict]:
        """
        Get all tracked symbols with timeframes.
        
        Args:
            active_only: If True, only return active symbols
        
        Returns:
            List of symbol dicts
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            query = "SELECT id, symbol, asset_class, active, date_added, last_backfill, backfill_status, timeframes FROM tracked_symbols"
            
            if active_only:
                query += " WHERE active = TRUE"
            
            query += " ORDER BY symbol ASC"
            
            rows = await conn.fetch(query)
            await conn.close()
            
            return [
                {
                    'id': row['id'],
                    'symbol': row['symbol'],
                    'asset_class': row['asset_class'],
                    'active': row['active'],
                    'date_added': row['date_added'].isoformat() if row['date_added'] else None,
                    'last_backfill': row['last_backfill'].isoformat() if row['last_backfill'] else None,
                    'backfill_status': row['backfill_status'],
                    'timeframes': list(row['timeframes']) if row['timeframes'] else DEFAULT_TIMEFRAMES
                }
                for row in rows
            ]
        
        except Exception as e:
            logger.error("Error fetching symbols", extra={"error": str(e)})
            raise
    
    async def get_symbol(self, symbol: str) -> Optional[dict]:
        """
        Get a specific symbol with timeframes.
        
        Args:
            symbol: Symbol to fetch
        
        Returns:
            Symbol dict or None if not found
        """
        symbol = symbol.upper()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            row = await conn.fetchrow(
                "SELECT id, symbol, asset_class, active, date_added, last_backfill, backfill_status, timeframes FROM tracked_symbols WHERE symbol = $1",
                symbol
            )
            
            await conn.close()
            
            if not row:
                return None
            
            # PostgreSQL array comes back as list, use default if None
            timeframes = list(row['timeframes']) if row['timeframes'] else DEFAULT_TIMEFRAMES
            
            return {
                'id': row['id'],
                'symbol': row['symbol'],
                'asset_class': row['asset_class'],
                'active': row['active'],
                'date_added': row['date_added'].isoformat() if row['date_added'] else None,
                'last_backfill': row['last_backfill'].isoformat() if row['last_backfill'] else None,
                'backfill_status': row['backfill_status'],
                'timeframes': timeframes
            }
        
        except Exception as e:
            logger.error(f"Error fetching symbol {symbol}", extra={"error": str(e)})
            raise
    
    async def update_symbol_status(
        self,
        symbol: str,
        active: Optional[bool] = None,
        backfill_status: Optional[str] = None,
        backfill_error: Optional[str] = None
    ) -> bool:
        """
        Update symbol status/metadata.
        
        Args:
            symbol: Symbol to update
            active: Active status
            backfill_status: Backfill status (pending, in_progress, completed, failed)
            backfill_error: Error message if backfill failed
        
        Returns:
            Success boolean
        """
        symbol = symbol.upper()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Build dynamic update query
            updates = []
            params = [symbol]
            param_idx = 2
            
            if active is not None:
                updates.append(f"active = ${param_idx}")
                params.append(active)
                param_idx += 1
            
            if backfill_status is not None:
                updates.append(f"backfill_status = ${param_idx}")
                params.append(backfill_status)
                param_idx += 1
                
                # Update last_backfill if status is completed
                if backfill_status == "completed":
                    updates.append(f"last_backfill = NOW()")
            
            if backfill_error is not None:
                updates.append(f"backfill_error = ${param_idx}")
                params.append(backfill_error)
                param_idx += 1
            
            if not updates:
                await conn.close()
                return True  # Nothing to update
            
            query = f"UPDATE tracked_symbols SET {', '.join(updates)} WHERE symbol = $1"
            
            await conn.execute(query, *params)
            await conn.close()
            
            logger.info(f"Symbol updated: {symbol}", extra={
                "active": active,
                "backfill_status": backfill_status
            })
            return True
        
        except Exception as e:
            logger.error(f"Error updating symbol {symbol}", extra={"error": str(e)})
            raise
    
    async def update_symbol_timeframes(
        self,
        symbol: str,
        timeframes: List[str]
    ) -> Optional[dict]:
        """
        Update a symbol's configured timeframes.
        
        Args:
            symbol: Symbol to update
            timeframes: List of timeframes (e.g., ['1h', '1d', '4h'])
        
        Returns:
            Updated symbol dict or None if not found
            
        Raises:
            ValueError: If invalid timeframes provided
        """
        symbol = symbol.upper()
        
        # Validate timeframes
        invalid = [tf for tf in timeframes if tf not in ALLOWED_TIMEFRAMES]
        if invalid:
            raise ValueError(
                f"Invalid timeframes: {invalid}. "
                f"Allowed: {', '.join(ALLOWED_TIMEFRAMES)}"
            )
        
        # Remove duplicates and sort
        timeframes = sorted(list(set(timeframes)))
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            row = await conn.fetchrow(
                """
                UPDATE tracked_symbols 
                SET timeframes = $2
                WHERE symbol = $1
                RETURNING id, symbol, asset_class, active, date_added, last_backfill, backfill_status, timeframes
                """,
                symbol, timeframes
            )
            
            await conn.close()
            
            if not row:
                logger.warning(f"Symbol not found: {symbol}")
                return None
            
            result = {
                'id': row['id'],
                'symbol': row['symbol'],
                'asset_class': row['asset_class'],
                'active': row['active'],
                'date_added': row['date_added'].isoformat() if row['date_added'] else None,
                'last_backfill': row['last_backfill'].isoformat() if row['last_backfill'] else None,
                'backfill_status': row['backfill_status'],
                'timeframes': list(row['timeframes']) if row['timeframes'] else DEFAULT_TIMEFRAMES
            }
            
            logger.info(f"Symbol timeframes updated: {symbol}", extra={
                "timeframes": result['timeframes']
            })
            return result
        
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating symbol timeframes {symbol}", extra={"error": str(e)})
            raise
    
    async def remove_symbol(self, symbol: str) -> bool:
        """
        Deactivate a symbol (soft delete, keeps historical data).
        
        Args:
            symbol: Symbol to remove
        
        Returns:
            Success boolean
        """
        symbol = symbol.upper()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            result = await conn.execute(
                "UPDATE tracked_symbols SET active = FALSE WHERE symbol = $1",
                symbol
            )
            
            await conn.close()
            
            if result == "UPDATE 0":
                logger.warning(f"Symbol not found: {symbol}")
                return False
            
            logger.info(f"Symbol removed: {symbol}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing symbol {symbol}", extra={"error": str(e)})
            raise


# Global instance holder
_symbol_manager: Optional[SymbolManager] = None


def init_symbol_manager(database_url: str) -> SymbolManager:
    """Initialize global symbol manager"""
    global _symbol_manager
    _symbol_manager = SymbolManager(database_url)
    return _symbol_manager


def get_symbol_manager() -> SymbolManager:
    """Get global symbol manager instance"""
    if _symbol_manager is None:
        raise RuntimeError("Symbol manager not initialized. Call init_symbol_manager() first.")
    return _symbol_manager
