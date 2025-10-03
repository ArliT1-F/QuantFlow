# API Reference

## Base URL

All API endpoints are prefixed with `/api/v1`

## Authentication

Currently, the API does not require authentication. In production, implement proper authentication.

## Response Format

All responses are in JSON format with the following structure:

```json
{
  "data": {...},
  "message": "Success message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Error Handling

Errors return HTTP status codes and error details:

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Endpoints

### Trading Engine

#### Get Trading Status
```http
GET /api/v1/trading/status
```

**Response:**
```json
{
  "status": "running",
  "is_running": true,
  "strategies": ["momentum", "mean_reversion", "technical_analysis", "ml_strategy"],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Start Trading
```http
POST /api/v1/trading/start
```

**Response:**
```json
{
  "message": "Trading engine started successfully"
}
```

#### Stop Trading
```http
POST /api/v1/trading/stop
```

**Response:**
```json
{
  "message": "Trading engine stopped successfully"
}
```

### Portfolio Management

#### Get Portfolio Overview
```http
GET /api/v1/portfolio/overview
```

**Response:**
```json
{
  "portfolio_metrics": {
    "total_value": 10500.00,
    "cash_balance": 2000.00,
    "invested_amount": 8500.00,
    "total_realized_pnl": 150.00,
    "total_unrealized_pnl": 50.00,
    "total_pnl": 200.00,
    "total_return_percent": 2.0,
    "sharpe_ratio": 1.2,
    "max_drawdown": 0.05,
    "num_positions": 3,
    "num_trades": 15
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get Active Positions
```http
GET /api/v1/portfolio/positions
```

**Response:**
```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 10,
      "average_price": 150.00,
      "current_price": 155.00,
      "unrealized_pnl": 50.00,
      "realized_pnl": 0.00,
      "total_pnl": 50.00,
      "pnl_percentage": 3.33,
      "stop_loss": 142.50,
      "take_profit": 172.50,
      "opened_at": "2024-01-01T00:00:00Z"
    }
  ],
  "count": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get Trading History
```http
GET /api/v1/portfolio/trades?limit=100
```

**Parameters:**
- `limit` (optional): Number of trades to return (default: 100)

**Response:**
```json
{
  "trades": [
    {
      "id": 1,
      "symbol": "AAPL",
      "side": "BUY",
      "quantity": 10,
      "price": 150.00,
      "timestamp": "2024-01-01T00:00:00Z",
      "strategy": "momentum",
      "status": "FILLED",
      "fees": 1.50,
      "stop_loss": 142.50,
      "take_profit": 172.50
    }
  ],
  "count": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Market Data

#### Get All Market Data
```http
GET /api/v1/market/data
```

**Response:**
```json
{
  "market_data": {
    "AAPL": {
      "symbol": "AAPL",
      "price": 155.00,
      "open": 150.00,
      "high": 156.00,
      "low": 149.00,
      "volume": 1000000,
      "change": 5.00,
      "change_percent": 3.33,
      "market_cap": 2500000000000,
      "pe_ratio": 25.5,
      "dividend_yield": 0.5,
      "beta": 1.2,
      "timestamp": "2024-01-01T00:00:00Z"
    }
  },
  "symbols": ["AAPL"],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get Symbol Data
```http
GET /api/v1/market/data/{symbol}
```

**Parameters:**
- `symbol`: Stock symbol (e.g., AAPL, MSFT)

**Response:**
```json
{
  "symbol": "AAPL",
  "data": {
    "symbol": "AAPL",
    "price": 155.00,
    "open": 150.00,
    "high": 156.00,
    "low": 149.00,
    "volume": 1000000,
    "change": 5.00,
    "change_percent": 3.33,
    "market_cap": 2500000000000,
    "pe_ratio": 25.5,
    "dividend_yield": 0.5,
    "beta": 1.2,
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get Historical Data
```http
GET /api/v1/market/historical/{symbol}?period=1y
```

**Parameters:**
- `symbol`: Stock symbol
- `period` (optional): Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

**Response:**
```json
{
  "symbol": "AAPL",
  "period": "1y",
  "data": [
    {
      "Date": "2023-01-01",
      "Open": 150.00,
      "High": 155.00,
      "Low": 148.00,
      "Close": 152.00,
      "Volume": 1000000,
      "SMA_20": 151.00,
      "SMA_50": 150.00,
      "RSI": 55.0,
      "MACD": 0.5
    }
  ],
  "count": 252,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Risk Management

#### Get Risk Metrics
```http
GET /api/v1/risk/metrics
```

**Response:**
```json
{
  "risk_metrics": {
    "daily_trades": 5,
    "daily_pnl": 100.00,
    "max_daily_trades": 10,
    "max_daily_loss": 0.05,
    "max_position_size": 0.1,
    "max_portfolio_risk": 0.02,
    "position_correlations": {
      "AAPL": {
        "MSFT": 0.3,
        "GOOGL": 0.2
      }
    },
    "sector_exposures": {
      "AAPL": 0.05
    },
    "last_reset_date": "2024-01-01"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Update Risk Limits
```http
POST /api/v1/risk/limits
```

**Request Body:**
```json
{
  "max_position_size": 0.15,
  "max_portfolio_risk": 0.03,
  "max_daily_loss": 0.08
}
```

**Response:**
```json
{
  "message": "Risk limits updated successfully"
}
```

### Trading Strategies

#### Get Strategies
```http
GET /api/v1/strategies
```

**Response:**
```json
{
  "strategies": [
    {
      "name": "momentum",
      "class_name": "MomentumStrategy",
      "parameters": {
        "lookback_period": 20,
        "momentum_threshold": 0.05,
        "volume_threshold": 1.5,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "min_confidence": 0.6
      },
      "performance": {
        "total_trades": 25,
        "winning_trades": 15,
        "losing_trades": 10,
        "win_rate": 0.6,
        "total_pnl": 500.00,
        "sharpe_ratio": 1.2,
        "max_drawdown": 0.05
      }
    }
  ],
  "count": 4,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get Strategy Performance
```http
GET /api/v1/strategies/{strategy_name}/performance
```

**Parameters:**
- `strategy_name`: Name of the strategy (momentum, mean_reversion, technical_analysis, ml_strategy)

**Response:**
```json
{
  "strategy": "momentum",
  "performance": {
    "total_trades": 25,
    "winning_trades": 15,
    "losing_trades": 10,
    "win_rate": 0.6,
    "total_pnl": 500.00,
    "sharpe_ratio": 1.2,
    "max_drawdown": 0.05
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Notifications

#### Send Test Notification
```http
POST /api/v1/notifications/test
```

**Response:**
```json
{
  "message": "Test notification sent successfully"
}
```

#### Send Custom Alert
```http
POST /api/v1/notifications/alert
```

**Request Body:**
```json
{
  "title": "Custom Alert",
  "message": "This is a custom alert message",
  "priority": "HIGH"
}
```

**Parameters:**
- `title`: Alert title
- `message`: Alert message
- `priority` (optional): Alert priority (LOW, MEDIUM, HIGH, CRITICAL)

**Response:**
```json
{
  "message": "Alert sent successfully"
}
```

### System

#### Get System Health
```http
GET /api/v1/system/health
```

**Response:**
```json
{
  "trading_engine": true,
  "data_service": true,
  "portfolio_manager": true,
  "risk_manager": true,
  "notification_service": true,
  "overall_health": true,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Get System Logs
```http
GET /api/v1/system/logs?limit=100
```

**Parameters:**
- `limit` (optional): Number of log entries to return (default: 100)

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "level": "INFO",
      "message": "System running normally",
      "source": "trading_engine"
    }
  ],
  "count": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Rate Limiting

Currently, there are no rate limits implemented. In production, implement appropriate rate limiting.

## WebSocket Support

WebSocket support for real-time updates is planned for future releases.

## Error Codes

- `400`: Bad Request - Invalid parameters
- `404`: Not Found - Resource not found
- `500`: Internal Server Error - Server error
- `503`: Service Unavailable - Service not available

## Examples

### Python Client Example

```python
import requests
import json

base_url = "http://localhost:8000/api/v1"

# Get portfolio overview
response = requests.get(f"{base_url}/portfolio/overview")
portfolio = response.json()

# Start trading
response = requests.post(f"{base_url}/trading/start")
result = response.json()

# Get market data
response = requests.get(f"{base_url}/market/data")
market_data = response.json()

# Send custom alert
alert_data = {
    "title": "Portfolio Alert",
    "message": "Portfolio value exceeded $10,000",
    "priority": "HIGH"
}
response = requests.post(f"{base_url}/notifications/alert", json=alert_data)
```

### JavaScript Client Example

```javascript
const baseUrl = 'http://localhost:8000/api/v1';

// Get portfolio overview
fetch(`${baseUrl}/portfolio/overview`)
  .then(response => response.json())
  .then(data => console.log(data));

// Start trading
fetch(`${baseUrl}/trading/start`, { method: 'POST' })
  .then(response => response.json())
  .then(data => console.log(data));

// Get market data
fetch(`${baseUrl}/market/data`)
  .then(response => response.json())
  .then(data => console.log(data));
```

### cURL Examples

```bash
# Get portfolio overview
curl http://localhost:8000/api/v1/portfolio/overview

# Start trading
curl -X POST http://localhost:8000/api/v1/trading/start

# Get market data for specific symbol
curl http://localhost:8000/api/v1/market/data/AAPL

# Send test notification
curl -X POST http://localhost:8000/api/v1/notifications/test
```