"""
API routes for the trading bot
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from app.services.trading_engine import TradingEngine
from app.services.data_service import DataService
from app.services.portfolio_manager import PortfolioManager
from app.services.risk_manager import RiskManager
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Create router
api_router = APIRouter()

# Global services (will be injected)
trading_engine: Optional[TradingEngine] = None
data_service: Optional[DataService] = None
portfolio_manager: Optional[PortfolioManager] = None
risk_manager: Optional[RiskManager] = None
notification_service: Optional[NotificationService] = None

def set_services(te: TradingEngine, ds: DataService, pm: PortfolioManager, 
                rm: RiskManager, ns: NotificationService):
    """Set global services"""
    global trading_engine, data_service, portfolio_manager, risk_manager, notification_service
    trading_engine = te
    data_service = ds
    portfolio_manager = pm
    risk_manager = rm
    notification_service = ns

# Trading Engine Routes
@api_router.get("/trading/status")
async def get_trading_status():
    """Get trading engine status"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    return {
        "status": trading_engine.state.value,
        "is_running": trading_engine.is_running(),
        "strategies": list(trading_engine.strategies.keys()),
        "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting trading history: {e}")
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}")
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
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Overall health
        health_status["overall_health"] = all([
            health_status["trading_engine"],
            health_status["data_service"],
            health_status["portfolio_manager"],
            health_status["risk_manager"],
            health_status["notification_service"]
        ])
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/system/logs")
async def get_system_logs(limit: int = 100):
    """Get recent system logs"""
    try:
        # In a real implementation, this would read from log files
        # For now, return a placeholder
        logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "System running normally",
                "source": "trading_engine"
            }
        ]
        
        return {
            "logs": logs,
            "count": len(logs),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))