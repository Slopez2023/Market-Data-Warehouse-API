#!/usr/bin/env python3
"""
Test script for free data sources beyond OHLCV

Tested data sources:
1. yfinance - News, Earnings, Dividends, Splits, Balance Sheet, Income Statement
2. Alpha Vantage - Technical Indicators, Intraday, Fundamentals
3. FRED API - Economic Indicators
4. CoinGecko - Crypto fundamentals, historical prices
5. Finnhub - News, Company Profile, Financials
6. IEX Cloud - Company data (limited free tier)
7. Polygon.io - Options, Technicals, News
"""

import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pandas as pd
import json


class FreeDataSourceTester:
    def __init__(self):
        self.results = {
            "yfinance": {},
            "alpha_vantage": {},
            "fred": {},
            "coingecko": {},
            "finnhub": {},
            "iex_cloud": {},
            "polygon": {}
        }
        self.session = None

    async def init_session(self):
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()

    # YFINANCE TESTS
    async def test_yfinance(self):
        """Test yfinance for news, financials, dividends, etc."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker("AAPL")
            
            # Get news
            try:
                news = ticker.news
                self.results["yfinance"]["news"] = {
                    "status": "success",
                    "count": len(news) if news else 0,
                    "sample": news[:2] if news else []
                }
            except Exception as e:
                self.results["yfinance"]["news"] = {"status": "failed", "error": str(e)}

            # Get balance sheet
            try:
                bs = ticker.balance_sheet
                self.results["yfinance"]["balance_sheet"] = {
                    "status": "success",
                    "shape": bs.shape if bs is not None else None
                }
            except Exception as e:
                self.results["yfinance"]["balance_sheet"] = {"status": "failed", "error": str(e)}

            # Get income statement
            try:
                income = ticker.income_stmt
                self.results["yfinance"]["income_statement"] = {
                    "status": "success",
                    "shape": income.shape if income is not None else None
                }
            except Exception as e:
                self.results["yfinance"]["income_statement"] = {"status": "failed", "error": str(e)}

            # Get dividend history
            try:
                dividends = ticker.dividends
                self.results["yfinance"]["dividends"] = {
                    "status": "success",
                    "count": len(dividends) if dividends is not None else 0
                }
            except Exception as e:
                self.results["yfinance"]["dividends"] = {"status": "failed", "error": str(e)}

            # Get splits
            try:
                splits = ticker.splits
                self.results["yfinance"]["splits"] = {
                    "status": "success",
                    "count": len(splits) if splits is not None else 0
                }
            except Exception as e:
                self.results["yfinance"]["splits"] = {"status": "failed", "error": str(e)}

            # Get info (fundamentals)
            try:
                info = ticker.info
                self.results["yfinance"]["fundamentals"] = {
                    "status": "success",
                    "keys_available": len(info) if info else 0,
                    "sample_keys": list(info.keys())[:5] if info else []
                }
            except Exception as e:
                self.results["yfinance"]["fundamentals"] = {"status": "failed", "error": str(e)}

            # Get options chain
            try:
                expirations = ticker.options
                if expirations:
                    options = ticker.option_chain(expirations[0])
                    self.results["yfinance"]["options"] = {
                        "status": "success",
                        "expirations_available": len(expirations),
                        "calls_count": len(options.calls),
                        "puts_count": len(options.puts)
                    }
                else:
                    self.results["yfinance"]["options"] = {"status": "no_data"}
            except Exception as e:
                self.results["yfinance"]["options"] = {"status": "failed", "error": str(e)}

        except ImportError:
            self.results["yfinance"]["status"] = "library_not_installed"

    # ALPHA VANTAGE TESTS
    async def test_alpha_vantage(self):
        """Test Alpha Vantage API"""
        api_key = os.getenv("ALPHA_VANTAGE_KEY", "demo")
        
        endpoints = {
            "intraday": "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=5min&apikey=" + api_key,
            "daily": "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey=" + api_key,
            "macd": "https://www.alphavantage.co/query?function=MACD&symbol=IBM&interval=daily&apikey=" + api_key,
            "rsi": "https://www.alphavantage.co/query?function=RSI&symbol=IBM&interval=daily&apikey=" + api_key,
            "bbands": "https://www.alphavantage.co/query?function=BBANDS&symbol=IBM&interval=daily&apikey=" + api_key,
        }

        for endpoint_name, url in endpoints.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.results["alpha_vantage"][endpoint_name] = {
                            "status": "success",
                            "keys": list(data.keys())[:5]
                        }
                    else:
                        self.results["alpha_vantage"][endpoint_name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["alpha_vantage"][endpoint_name] = {"status": "failed", "error": str(e)[:50]}

    # FRED API TESTS (Economic Data)
    async def test_fred(self):
        """Test FRED API for economic indicators"""
        api_key = os.getenv("FRED_API_KEY", "")
        
        if not api_key:
            self.results["fred"]["status"] = "no_api_key"
            return

        series_ids = {
            "gdp": "A191RL1Q225SBEA",  # GDP
            "unemployment": "UNRATE",  # Unemployment rate
            "inflation": "CPIAUCSL",  # CPI
            "interest_rate": "DFF",  # Fed Funds Rate
        }

        for name, series_id in series_ids.items():
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        obs = data.get("observations", [])
                        self.results["fred"][name] = {
                            "status": "success",
                            "observations_count": len(obs),
                            "latest_value": obs[-1] if obs else None
                        }
                    else:
                        self.results["fred"][name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["fred"][name] = {"status": "failed", "error": str(e)[:50]}

    # COINGECKO TESTS (Crypto data)
    async def test_coingecko(self):
        """Test CoinGecko API for crypto data"""
        endpoints = {
            "bitcoin_simple": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true",
            "bitcoin_market_chart": "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30",
            "top_100": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1",
            "global_data": "https://api.coingecko.com/api/v3/global",
        }

        for endpoint_name, url in endpoints.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict):
                            keys = list(data.keys())
                        else:
                            keys = len(data) if isinstance(data, list) else 0
                        
                        self.results["coingecko"][endpoint_name] = {
                            "status": "success",
                            "data_type": type(data).__name__,
                            "keys_or_items": keys
                        }
                    else:
                        self.results["coingecko"][endpoint_name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["coingecko"][endpoint_name] = {"status": "failed", "error": str(e)[:50]}

    # FINNHUB TESTS
    async def test_finnhub(self):
        """Test Finnhub API"""
        api_key = os.getenv("FINNHUB_API_KEY", "")
        
        if not api_key:
            self.results["finnhub"]["status"] = "no_api_key"
            return

        endpoints = {
            "company_profile": f"https://finnhub.io/api/v1/stock/profile2?symbol=AAPL&token={api_key}",
            "quote": f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={api_key}",
            "news": f"https://finnhub.io/api/v1/company-news?symbol=AAPL&from=2024-01-01&to=2024-12-31&token={api_key}",
            "peers": f"https://finnhub.io/api/v1/stock/peers?symbol=AAPL&token={api_key}",
        }

        for endpoint_name, url in endpoints.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.results["finnhub"][endpoint_name] = {
                            "status": "success",
                            "keys": list(data.keys())[:5] if isinstance(data, dict) else f"list_{len(data)}"
                        }
                    else:
                        self.results["finnhub"][endpoint_name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["finnhub"][endpoint_name] = {"status": "failed", "error": str(e)[:50]}

    # IEX CLOUD TESTS
    async def test_iex_cloud(self):
        """Test IEX Cloud free tier"""
        token = os.getenv("IEX_CLOUD_TOKEN", "")
        
        if not token:
            self.results["iex_cloud"]["status"] = "no_token"
            return

        endpoints = {
            "quote": f"https://cloud.iexapis.com/stable/stock/AAPL/quote?token={token}",
            "company": f"https://cloud.iexapis.com/stable/stock/AAPL/company?token={token}",
            "stats": f"https://cloud.iexapis.com/stable/stock/AAPL/stats?token={token}",
        }

        for endpoint_name, url in endpoints.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.results["iex_cloud"][endpoint_name] = {
                            "status": "success",
                            "keys": list(data.keys())[:5] if isinstance(data, dict) else f"list_{len(data)}"
                        }
                    else:
                        self.results["iex_cloud"][endpoint_name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["iex_cloud"][endpoint_name] = {"status": "failed", "error": str(e)[:50]}

    # POLYGON.IO TESTS
    async def test_polygon(self):
        """Test Polygon.io API"""
        api_key = os.getenv("POLYGON_API_KEY", "")
        
        if not api_key:
            self.results["polygon"]["status"] = "no_api_key"
            return

        endpoints = {
            "daily": f"https://api.polygon.io/v1/open-close/AAPL/2024-01-01?adjusted=true&apikey={api_key}",
            "technical": f"https://api.polygon.io/v1/indicators/sma/AAPL?timestamp=gte_2024-01-01&window=50&apikey={api_key}",
            "news": f"https://api.polygon.io/v2/reference/news?query=AAPL&apikey={api_key}",
            "options": f"https://api.polygon.io/v3/snapshot/options/AAPL?apikey={api_key}",
        }

        for endpoint_name, url in endpoints.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.results["polygon"][endpoint_name] = {
                            "status": "success",
                            "keys": list(data.keys())[:5] if isinstance(data, dict) else f"list_{len(data)}"
                        }
                    else:
                        self.results["polygon"][endpoint_name] = {"status": f"http_{resp.status}"}
            except Exception as e:
                self.results["polygon"][endpoint_name] = {"status": "failed", "error": str(e)[:50]}

    async def run_all_tests(self):
        """Run all data source tests"""
        print("\n" + "="*60)
        print("FREE DATA SOURCES TEST SUITE")
        print("="*60)
        
        await self.init_session()
        
        try:
            print("\n[1/7] Testing yfinance...")
            await self.test_yfinance()
            
            print("[2/7] Testing Alpha Vantage...")
            await self.test_alpha_vantage()
            
            print("[3/7] Testing FRED (Economic Data)...")
            await self.test_fred()
            
            print("[4/7] Testing CoinGecko...")
            await self.test_coingecko()
            
            print("[5/7] Testing Finnhub...")
            await self.test_finnhub()
            
            print("[6/7] Testing IEX Cloud...")
            await self.test_iex_cloud()
            
            print("[7/7] Testing Polygon.io...")
            await self.test_polygon()
            
        finally:
            await self.close_session()

        self.print_results()
        self.save_results()

    def print_results(self):
        """Print test results in readable format"""
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        for source, tests in self.results.items():
            print(f"\n{source.upper()}:")
            if isinstance(tests, dict):
                for test_name, result in tests.items():
                    status = result.get("status", "unknown")
                    print(f"  ✓ {test_name}: {status}")
                    if "error" in result:
                        print(f"    Error: {result['error']}")
            else:
                print(f"  {tests}")

    def save_results(self):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"datasource_test_results_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nResults saved to: {filename}")


async def main():
    tester = FreeDataSourceTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
