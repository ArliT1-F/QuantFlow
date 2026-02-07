"""
Main entry point for the Automated Coin Trading Bot
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import api_router
from app.services.trading_engine import TradingEngine
from app.services.data_service import DataService
from app.services.notification_service import NotificationService
from app.services.risk_manager import RiskManager
from app.services.portfolio_manager import PortfolioManager
from app.services.okx_client import OkxClient
from app.services.backtest_service import BacktestService

# Ensure log directory exists before configuring logging
log_dir = os.path.dirname(settings.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global services
trading_engine = None
data_service = None
notification_service = None
backtest_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global trading_engine, data_service, notification_service, backtest_service
    
    logger.info("Starting Automated Coin Trading Bot...")
    
    # Initialize database
    await init_db()
    
    # Initialize services
    data_service = DataService()
    notification_service = NotificationService()
    okx_client = None
    if settings.OKX_ENABLED:
        okx_client = OkxClient(
            api_key=settings.OKX_API_KEY,
            secret_key=settings.OKX_SECRET_KEY,
            passphrase=settings.OKX_PASSPHRASE,
            base_url=settings.OKX_BASE_URL,
            demo=settings.OKX_DEMO_TRADING
        )
    portfolio_manager = PortfolioManager(okx_client=okx_client)
    await portfolio_manager.initialize()
    risk_manager = RiskManager(portfolio_manager=portfolio_manager)
    backtest_service = BacktestService(data_service)
    trading_engine = TradingEngine(
        data_service,
        notification_service,
        risk_manager=risk_manager,
        portfolio_manager=portfolio_manager
    )
    from app.api.routes import set_services
    set_services(trading_engine, data_service, portfolio_manager, risk_manager, notification_service, backtest_service)
    
    # Start background tasks (data only; trading is manual for safety)
    asyncio.create_task(data_service.start_data_collection())
    
    logger.info("Trading bot started successfully!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down trading bot...")
    if trading_engine:
        await trading_engine.stop()
    if data_service:
        await data_service.stop_data_collection()
    logger.info("Trading bot stopped.")

# Create FastAPI app
app = FastAPI(
    title="Automated Coin Trading Bot",
    description="An educational paper-trading system for coins",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Automated Coin Trading Bot API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "trading_engine": trading_engine.is_running() if trading_engine else False,
        "data_service": data_service.is_running() if data_service else False
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
