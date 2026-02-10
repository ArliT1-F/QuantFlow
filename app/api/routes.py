"""
API routes for the trading bot
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from pydantic import ValidationError

from app.services.trading_engine import TradingEngine
from app.services.data_service import DataService
from app.services.portfolio_manager import PortfolioManager
from app.services.risk_manager import RiskManager
from app.services.notification_service import NotificationService
from app.services.backtest_service import BacktestService
from app.services.runtime_settings_service import RuntimeSettingsService
from app.core.config import settings
from app.api.security import require_api_key
from app.api.schemas import (
    DexScreenerBoostQuery,
    DexScreenerBoostResponse,
    MarketHealthResponse,
)
import os
from collections import deque

logger = logging.getLogger(__name__)

# Create router
api_router = APIRouter(dependencies=[Depends(require_api_key)])

# Global services (will be injected)
trading_engine: Optional[TradingEngine] = None
data_service: Optional[DataService] = None
portfolio_manager: Optional[PortfolioManager] = None
risk_manager: Optional[RiskManager] = None
notification_service: Optional[NotificationService] = None
backtest_service: Optional[BacktestService] = None
runtime_settings_service = RuntimeSettingsService()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def market_http_error(status_code: int, error_code: str, message: str, errors: Optional[List[Dict[str, Any]]] = None):
    detail: Dict[str, Any] = {
        "error_code": error_code,
        "message": message,
    }
    if errors:
        detail["errors"] = errors
    raise HTTPException(status_code=status_code, detail=detail)

def set_services(te: TradingEngine, ds: DataService, pm: PortfolioManager, 
                rm: RiskManager, ns: NotificationService, bs: Optional[BacktestService] = None):
    """Set global services"""
    global trading_engine, data_service, portfolio_manager, risk_manager, notification_service, backtest_service
    trading_engine = te
    data_service = ds
    portfolio_manager = pm
    risk_manager = rm
    notification_service = ns
    backtest_service = bs

# Trading Engine Routes
@api_router.get("/trading/status")
async def get_trading_status():
    """Get trading engine status"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    market_source = "Offline"
    market_chain = settings.DEXSCREENER_CHAIN.strip().lower()
    if settings.DEXSCREENER_ENABLED:
        market_source = f"DexScreener ({market_chain})" if market_chain else "DexScreener"
    elif settings.OKX_ENABLED and settings.OKX_MARKET_DATA_ENABLED:
        market_source = "OKX"
    elif settings.YAHOO_FINANCE_ENABLED:
        market_source = "Yahoo Finance"
    elif settings.ALPHA_VANTAGE_ENABLED:
        market_source = "Alpha Vantage"

    return {
        "status": trading_engine.state.value,
        "is_running": trading_engine.is_running(),
        "strategies": list(trading_engine.strategies.keys()),
        "market_source": market_source,
        "market_chain": market_chain,
        "okx_enabled": settings.OKX_ENABLED and settings.OKX_MARKET_DATA_ENABLED,
        "okx_demo": settings.OKX_DEMO_TRADING,
        "dexscreener_enabled": settings.DEXSCREENER_ENABLED,
        "yahoo_enabled": settings.YAHOO_FINANCE_ENABLED,
        "alpha_vantage_enabled": settings.ALPHA_VANTAGE_ENABLED,
        "timestamp": utcnow_iso()
    }

@api_router.post("/trading/start")
async def start_trading():
    """Start trading engine"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    try:
        await trading_engine.start()
        return {"message": "Trading engine started successfully"}
    except Exception as e:
        logger.error(f"Error starting trading engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/trading/stop")
async def stop_trading():
    """Stop trading engine"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    try:
        await trading_engine.stop()
        return {"message": "Trading engine stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping trading engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Portfolio Routes
@api_router.get("/portfolio/overview")
async def get_portfolio_overview():
    """Get portfolio overview"""
    if not portfolio_manager:
        raise HTTPException(status_code=503, detail="Portfolio manager not available")
    
    try:
        metrics = await portfolio_manager.get_performance_metrics()
        return {
            "portfolio_metrics": metrics,
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting portfolio overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/portfolio/positions")
async def get_portfolio_positions():
    """Get active positions"""
    if not portfolio_manager:
        raise HTTPException(status_code=503, detail="Portfolio manager not available")
    
    try:
        positions = await portfolio_manager.get_active_positions()
        return {
            "positions": positions,
            "count": len(positions),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting portfolio positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/portfolio/trades")
async def get_trading_history(limit: int = 100):
    """Get trading history"""
    if not portfolio_manager:
        raise HTTPException(status_code=503, detail="Portfolio manager not available")
    
    try:
        trades = await portfolio_manager.get_trading_history(limit)
        return {
            "trades": trades,
            "count": len(trades),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting trading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/portfolio/performance")
async def get_portfolio_performance(limit: int = 100):
    """Get portfolio performance history"""
    if not portfolio_manager:
        raise HTTPException(status_code=503, detail="Portfolio manager not available")

    try:
        performance = await portfolio_manager.get_performance_history(limit)
        return {
            "performance": performance,
            "count": len(performance),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting portfolio performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Market Data Routes
@api_router.get("/market/data")
async def get_market_data():
    """Get current market data"""
    if not data_service:
        raise HTTPException(status_code=503, detail="Data service not available")
    
    try:
        data = await data_service.get_latest_data()
        return {
            "market_data": data,
            "symbols": list(data.keys()),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/market/dexscreener/boosts", response_model=DexScreenerBoostResponse)
async def get_dexscreener_boosts(
    limit: Optional[str] = None,
    page: str = "1",
    page_size: str = "50",
    mode: str = "top",
    sort: str = "boosts",
    chain: str = "",
    min_liquidity: Optional[str] = None
):
    """Get DexScreener boosted tokens with market data."""
    if not data_service:
        market_http_error(503, "market.unavailable", "Data service not available")
    if not settings.DEXSCREENER_ENABLED:
        market_http_error(503, "market.source_disabled", "DexScreener is not enabled")

    try:
        query = DexScreenerBoostQuery(
            limit=limit,
            page=page,
            page_size=page_size,
            mode=mode,
            sort=sort,
            chain=chain,
            min_liquidity=min_liquidity,
        )
    except ValidationError as error:
        market_http_error(422, "market.invalid_query", "Invalid market query parameters", error.errors())

    try:
        selected_page_size = query.limit if query.limit is not None else query.page_size
        requested_min_liquidity = (
            query.min_liquidity
            if query.min_liquidity is not None
            else settings.DEXSCREENER_MIN_LIQUIDITY_USD
        )
        payload = await data_service.get_dexscreener_boosted_pairs(
            page=query.page,
            page_size=selected_page_size,
            mode=query.mode,
            sort_by=query.sort,
            chain=query.chain,
            min_liquidity=requested_min_liquidity
        )
        effective_min_liquidity = requested_min_liquidity

        # Auto-relax liquidity floor for richer results when user didn't pin a value.
        # Goal: avoid "only a few rows" while still preferring cleaner liquidity.
        if query.min_liquidity is None and requested_min_liquidity > 0:
            desired_min_results = min(max(int(selected_page_size) // 2, 12), int(selected_page_size))
            best_payload = payload
            best_min_liquidity = requested_min_liquidity
            best_total = int(payload.get("total", 0))

            if best_total < desired_min_results:
                for fallback_min in (10000.0, 5000.0, 1000.0, 0.0):
                    if fallback_min >= best_min_liquidity:
                        continue
                    candidate = await data_service.get_dexscreener_boosted_pairs(
                        page=query.page,
                        page_size=selected_page_size,
                        mode=query.mode,
                        sort_by=query.sort,
                        chain=query.chain,
                        min_liquidity=fallback_min
                    )
                    candidate_total = int(candidate.get("total", 0))
                    if candidate_total > best_total:
                        best_payload = candidate
                        best_total = candidate_total
                        best_min_liquidity = fallback_min
                    if best_total >= desired_min_results:
                        break

            payload = best_payload
            effective_min_liquidity = best_min_liquidity

        total = int(payload.get("total", 0))
        size = max(int(selected_page_size), 1)
        total_pages = (total + size - 1) // size

        return DexScreenerBoostResponse(
            results=payload.get("items", []),
            count=len(payload.get("items", [])),
            total=total,
            page=max(query.page, 1),
            page_size=size,
            total_pages=total_pages,
            mode=query.mode,
            sort=query.sort,
            chain=query.chain or settings.DEXSCREENER_CHAIN,
            min_liquidity=requested_min_liquidity,
            effective_min_liquidity=effective_min_liquidity,
            summary=payload.get("summary", {}),
            meta=payload.get("meta", {
                "as_of": utcnow_iso(),
                "is_stale": True,
                "age_seconds": 0,
                "source_counts": {},
            }),
            timestamp=utcnow_iso()
        ).model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting DexScreener boosts: {e}")
        market_http_error(500, "market.fetch_failed", str(e))


@api_router.get("/market/health", response_model=MarketHealthResponse)
async def get_market_health():
    if not data_service:
        market_http_error(503, "market.unavailable", "Data service not available")

    try:
        payload = data_service.get_market_health()
        return MarketHealthResponse(**payload).model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting market health: {e}")
        market_http_error(500, "market.health_failed", str(e))

@api_router.get("/market/data/{symbol}")
async def get_symbol_data(symbol: str):
    """Get data for specific symbol"""
    if not data_service:
        raise HTTPException(status_code=503, detail="Data service not available")
    
    try:
        data = await data_service.get_latest_data_for_symbol(symbol.upper())
        if not data:
            raise HTTPException(status_code=404, detail=f"Data not found for symbol {symbol}")
        
        return {
            "symbol": symbol.upper(),
            "data": data,
            "timestamp": utcnow_iso()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting data for symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/market/historical/{symbol}")
async def get_historical_data(symbol: str, period: str = "1y"):
    """Get historical data for symbol"""
    if not data_service:
        raise HTTPException(status_code=503, detail="Data service not available")
    
    try:
        data = await data_service.get_historical_data(symbol.upper(), period)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Historical data not found for symbol {symbol}")
        
        # Convert DataFrame to dict for JSON response
        data_dict = data.to_dict('records')
        
        return {
            "symbol": symbol.upper(),
            "period": period,
            "data": data_dict,
            "count": len(data_dict),
            "timestamp": utcnow_iso()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting historical data for symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Risk Management Routes
@api_router.get("/risk/metrics")
async def get_risk_metrics():
    """Get risk management metrics"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="Risk manager not available")
    
    try:
        metrics = risk_manager.get_risk_metrics()
        return {
            "risk_metrics": metrics,
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/settings/trading")
async def get_trading_settings():
    """Get persisted trading settings."""
    try:
        runtime = runtime_settings_service.get_trading_settings()
        return {
            "settings": runtime_settings_service.to_percent_response(runtime),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting trading settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/settings/trading")
async def update_trading_settings(payload: Dict[str, Any]):
    """Update and persist trading settings."""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="Risk manager not available")

    try:
        runtime = runtime_settings_service.update_trading_settings(payload, risk_manager=risk_manager)
        return {
            "message": "Trading settings updated successfully",
            "settings": runtime_settings_service.to_percent_response(runtime),
            "timestamp": utcnow_iso()
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating trading settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/risk/limits")
async def update_risk_limits(limits: Dict[str, Any]):
    """Update risk limits"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="Risk manager not available")
    
    try:
        risk_manager.update_risk_limits(limits)
        return {"message": "Risk limits updated successfully"}
    except Exception as e:
        logger.error(f"Error updating risk limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Strategy Routes
@api_router.get("/strategies")
async def get_strategies():
    """Get available strategies"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    try:
        strategies = []
        for name, strategy in trading_engine.strategies.items():
            strategies.append({
                "name": name,
                "class_name": strategy.__class__.__name__,
                "parameters": strategy.parameters,
                "performance": strategy.get_performance_metrics()
            })
        
        return {
            "strategies": strategies,
            "count": len(strategies),
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/strategies/{strategy_name}/performance")
async def get_strategy_performance(strategy_name: str):
    """Get performance metrics for specific strategy"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    try:
        if strategy_name not in trading_engine.strategies:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")
        
        strategy = trading_engine.strategies[strategy_name]
        performance = strategy.get_performance_metrics()
        
        return {
            "strategy": strategy_name,
            "performance": performance,
            "timestamp": utcnow_iso()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Recent events
@api_router.get("/trading/events")
async def get_trading_events():
    """Get recent trade/signal events"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    return {
        "events": list(trading_engine.recent_events),
        "count": len(trading_engine.recent_events),
        "timestamp": utcnow_iso()
    }

# Backtest Routes
@api_router.post("/backtest/run")
async def run_backtest(payload: Dict[str, Any]):
    """Run backtest for selected strategies and symbols"""
    if not backtest_service:
        raise HTTPException(status_code=503, detail="Backtest service not available")
    
    try:
        symbols = payload.get("symbols")
        strategies = payload.get("strategies")
        days = int(payload.get("days", 180))
        initial_capital = float(payload.get("initial_capital", 10000))

        result = await backtest_service.run_backtest(
            symbols=symbols,
            days=days,
            strategies=strategies,
            initial_capital=initial_capital
        )
        return {
            "backtest": result,
            "timestamp": utcnow_iso()
        }
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Notification Routes
@api_router.post("/notifications/test")
async def test_notification():
    """Send test notification"""
    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    
    try:
        result = await notification_service.test_notification()
        return {"message": "Test notification sent successfully" if result else "Test notification failed"}
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/notifications/alert")
async def send_alert(title: str, message: str, priority: str = "MEDIUM"):
    """Send custom alert"""
    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    
    try:
        result = await notification_service.send_alert(title, message, priority)
        return {"message": "Alert sent successfully" if result else "Alert failed"}
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System Routes
@api_router.get("/system/health")
async def system_health():
    """Get system health status"""
    try:
        health_status = {
            "trading_engine": trading_engine.is_running() if trading_engine else False,
            "data_service": data_service.is_running() if data_service else False,
            "portfolio_manager": portfolio_manager is not None,
            "risk_manager": risk_manager is not None,
            "notification_service": notification_service is not None,
            "backtest_service": backtest_service is not None,
            "timestamp": utcnow_iso()
        }
        
        # Overall health
        health_status["overall_health"] = all([
            health_status["trading_engine"],
            health_status["data_service"],
            health_status["portfolio_manager"],
            health_status["risk_manager"],
            health_status["notification_service"],
            health_status["backtest_service"]
        ])
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/system/logs")
async def get_system_logs(limit: int = 100):
    """Get recent system logs"""
    try:
        logs = []
        if os.path.exists(settings.LOG_FILE):
            with open(settings.LOG_FILE, "r") as f:
                for line in deque(f, maxlen=limit):
                    logs.append({"message": line.strip()})
        
        return {
            "logs": logs,
            "count": len(logs),
            "timestamp": utcnow_iso()
        }
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
