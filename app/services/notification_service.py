"""
Notification service for sending alerts and trade notifications
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications and alerts"""
    
    def __init__(self):
        self.email_enabled = settings.EMAIL_ENABLED
        self.email_config = {
            "host": settings.EMAIL_HOST,
            "port": settings.EMAIL_PORT,
            "user": settings.EMAIL_USER,
            "password": settings.EMAIL_PASSWORD
        }
        
        logger.info("Notification service initialized")
    
    async def send_alert(self, title: str, message: str, priority: str = "MEDIUM") -> bool:
        """
        Send an alert notification
        
        Args:
            title: Alert title
            message: Alert message
            priority: Alert priority (LOW, MEDIUM, HIGH, CRITICAL)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Log the alert
            logger.info(f"ALERT [{priority}]: {title} - {message}")
            
            # Send email if enabled
            if self.email_enabled:
                await self._send_email(title, message, priority)
            
            # In a real implementation, you might also send:
            # - SMS notifications
            # - Push notifications
            # - Webhook notifications
            # - Slack/Discord messages
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    async def send_trade_notification(self, trade_data: Dict[str, Any]) -> bool:
        """
        Send trade execution notification
        
        Args:
            trade_data: Trade data dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            symbol = trade_data.get("symbol", "")
            side = trade_data.get("side", "")
            quantity = trade_data.get("quantity", 0)
            price = trade_data.get("price", 0)
            strategy = trade_data.get("strategy", "")
            
            title = f"Trade Executed: {symbol} {side}"
            message = f"""
Trade Details:
- Symbol: {symbol}
- Action: {side}
- Quantity: {quantity}
- Price: ${price:.2f}
- Strategy: {strategy}
- Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
- Status: {trade_data.get('status', 'FILLED')}
"""
            
            return await self.send_alert(title, message, "HIGH")
            
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
            return False
    
    async def send_performance_report(self, metrics: Dict[str, Any]) -> bool:
        """
        Send performance report
        
        Args:
            metrics: Performance metrics dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            title = "Daily Performance Report"
            
            message = f"""
Portfolio Performance Report
============================

Portfolio Value: ${metrics.get('total_value', 0):,.2f}
Cash Balance: ${metrics.get('cash_balance', 0):,.2f}
Invested Amount: ${metrics.get('invested_amount', 0):,.2f}

P&L Summary:
- Realized P&L: ${metrics.get('total_realized_pnl', 0):,.2f}
- Unrealized P&L: ${metrics.get('total_unrealized_pnl', 0):,.2f}
- Total P&L: ${metrics.get('total_pnl', 0):,.2f}
- Total Return: {metrics.get('total_return_percent', 0):.2f}%

Performance Metrics:
- Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}
- Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%
- Number of Positions: {metrics.get('num_positions', 0)}
- Number of Trades: {metrics.get('num_trades', 0)}

Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            return await self.send_alert(title, message, "MEDIUM")
            
        except Exception as e:
            logger.error(f"Error sending performance report: {e}")
            return False
    
    async def send_risk_alert(self, risk_type: str, message: str) -> bool:
        """
        Send risk management alert
        
        Args:
            risk_type: Type of risk alert
            message: Risk alert message
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            title = f"Risk Alert: {risk_type}"
            
            full_message = f"""
RISK ALERT - {risk_type.upper()}
===============================

{message}

Alert Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

Please review your trading parameters and risk management settings.
"""
            
            return await self.send_alert(title, full_message, "CRITICAL")
            
        except Exception as e:
            logger.error(f"Error sending risk alert: {e}")
            return False
    
    async def send_strategy_alert(self, strategy_name: str, alert_type: str, message: str) -> bool:
        """
        Send strategy-specific alert
        
        Args:
            strategy_name: Name of the strategy
            alert_type: Type of strategy alert
            message: Alert message
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            title = f"Strategy Alert: {strategy_name} - {alert_type}"
            
            full_message = f"""
Strategy Alert
==============

Strategy: {strategy_name}
Alert Type: {alert_type}

{message}

Alert Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            return await self.send_alert(title, full_message, "MEDIUM")
            
        except Exception as e:
            logger.error(f"Error sending strategy alert: {e}")
            return False
    
    async def _send_email(self, subject: str, body: str, priority: str = "MEDIUM") -> bool:
        """
        Send email notification
        
        Args:
            subject: Email subject
            body: Email body
            priority: Message priority
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self.email_enabled or not all([
                self.email_config["user"],
                self.email_config["password"],
                self.email_config["host"]
            ]):
                logger.warning("Email notifications not configured")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config["user"]
            msg['To'] = self.email_config["user"]  # Send to self for now
            msg['Subject'] = f"[{priority}] {subject}"
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.email_config["host"], self.email_config["port"])
            server.starttls()
            server.login(self.email_config["user"], self.email_config["password"])
            
            text = msg.as_string()
            server.sendmail(self.email_config["user"], self.email_config["user"], text)
            server.quit()
            
            logger.info(f"Email sent successfully: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """
        Send daily trading summary
        
        Args:
            summary_data: Daily summary data
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            title = "Daily Trading Summary"
            
            message = f"""
Daily Trading Summary
=====================

Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Trading Activity:
- Total Trades: {summary_data.get('total_trades', 0)}
- Winning Trades: {summary_data.get('winning_trades', 0)}
- Losing Trades: {summary_data.get('losing_trades', 0)}
- Win Rate: {summary_data.get('win_rate', 0):.2f}%

Portfolio Performance:
- Portfolio Value: ${summary_data.get('portfolio_value', 0):,.2f}
- Daily P&L: ${summary_data.get('daily_pnl', 0):,.2f}
- Daily Return: {summary_data.get('daily_return', 0):.2f}%

Risk Metrics:
- Daily Risk Used: {summary_data.get('daily_risk', 0):.2f}%
- Max Drawdown: {summary_data.get('max_drawdown', 0):.2f}%
- VaR (95%): ${summary_data.get('var_95', 0):,.2f}

Active Positions: {summary_data.get('active_positions', 0)}
Active Strategies: {summary_data.get('active_strategies', 0)}

Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            return await self.send_alert(title, message, "LOW")
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
            return False
    
    def is_email_enabled(self) -> bool:
        """Check if email notifications are enabled"""
        return self.email_enabled and all([
            self.email_config["user"],
            self.email_config["password"],
            self.email_config["host"]
        ])
    
    async def test_notification(self) -> bool:
        """Send test notification to verify configuration"""
        try:
            title = "Test Notification"
            message = "This is a test notification to verify the notification system is working correctly."
            
            result = await self.send_alert(title, message, "LOW")
            
            if result:
                logger.info("Test notification sent successfully")
            else:
                logger.warning("Test notification failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False