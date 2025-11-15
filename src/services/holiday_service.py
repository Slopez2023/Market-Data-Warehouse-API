"""Holiday service for market calendar management"""

import logging
from datetime import datetime, date
from typing import Set, Optional
import holidays

logger = logging.getLogger(__name__)


class HolidayService:
    """Manages market holidays and trading days"""

    def __init__(self):
        """Initialize holiday service with US stock market holidays"""
        self.us_holidays = holidays.US(years=range(2020, 2035))
        self.additional_closures = {
            # Add custom market closures
            # Format: date(YYYY, M, D)
        }
        logger.info("✓ Holiday service initialized")

    def is_market_closed(self, trading_date: date) -> bool:
        """
        Check if market is closed on given date
        
        Args:
            trading_date: Date to check
            
        Returns:
            True if market is closed, False if open
        """
        # Check weekends
        if trading_date.weekday() >= 5:  # Saturday=5, Sunday=6
            return True
        
        # Check US federal holidays
        if trading_date in self.us_holidays:
            return True
        
        # Check additional custom closures
        if trading_date in self.additional_closures:
            return True
        
        return False

    def is_market_open(self, trading_date: date) -> bool:
        """
        Check if market is open on given date
        
        Args:
            trading_date: Date to check
            
        Returns:
            True if market is open, False if closed
        """
        return not self.is_market_closed(trading_date)

    def get_next_trading_day(self, from_date: date) -> date:
        """
        Get next trading day after given date
        
        Args:
            from_date: Starting date
            
        Returns:
            Next open trading day
        """
        current = from_date.replace(day=from_date.day + 1) if from_date.day < 28 else from_date.replace(month=from_date.month + 1, day=1)
        
        while self.is_market_closed(current):
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        
        return current

    def get_previous_trading_day(self, from_date: date) -> date:
        """
        Get previous trading day before given date
        
        Args:
            from_date: Starting date
            
        Returns:
            Previous open trading day
        """
        from datetime import timedelta
        current = from_date - timedelta(days=1)
        
        while self.is_market_closed(current):
            current -= timedelta(days=1)
        
        return current

    def add_custom_closure(self, closure_date: date, reason: str = "Custom Closure"):
        """
        Add custom market closure
        
        Args:
            closure_date: Date to mark as closed
            reason: Reason for closure (optional)
        """
        self.additional_closures[closure_date] = reason
        logger.info(f"Added custom market closure: {closure_date} ({reason})")

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """
        Get all trading days between two dates (inclusive)
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of trading days
        """
        from datetime import timedelta
        trading_days = []
        current = start_date
        
        while current <= end_date:
            if self.is_market_open(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days

    def count_trading_days(self, start_date: date, end_date: date) -> int:
        """
        Count trading days between two dates
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Number of trading days
        """
        return len(self.get_trading_days(start_date, end_date))

    def get_holiday_name(self, holiday_date: date) -> Optional[str]:
        """
        Get holiday name if date is a holiday
        
        Args:
            holiday_date: Date to check
            
        Returns:
            Holiday name or None if not a holiday
        """
        if holiday_date in self.us_holidays:
            return self.us_holidays.get(holiday_date)
        
        if holiday_date in self.additional_closures:
            return self.additional_closures[holiday_date]
        
        return None


# Global instance
_holiday_service: Optional[HolidayService] = None


def get_holiday_service() -> HolidayService:
    """Get or create global holiday service instance"""
    global _holiday_service
    if _holiday_service is None:
        _holiday_service = HolidayService()
    return _holiday_service
