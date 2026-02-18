#!/usr/bin/env python3
"""
Repair corrupted portfolio state caused by anomalous symbol/price mismatches.

This script:
1. Detects anomalous SELL trades that explode notional (e.g. canonical symbols
   sold at unrelated prices).
2. Removes the anomalous SELL and its matching BUY leg.
3. Rebuilds positions, portfolio totals, and snapshots from the remaining trades.
"""
from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class LotState:
    quantity: float = 0.0
    average_price: float = 0.0
    realized_pnl_open: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: str | None = None


def _to_float(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def detect_anomalous_trade_ids(rows: List[sqlite3.Row]) -> Tuple[List[int], List[Dict[str, float]]]:
    """
    Flag anomalous SELL events and matching BUY legs.

    Heuristic:
    - canonical symbol with '-'
    - very large sell notional (> 1000)
    - matching previous BUY quantity
    - extreme price multiple (> 100x)
    """
    open_buys: Dict[str, List[sqlite3.Row]] = {}
    remove_ids: set[int] = set()
    events: List[Dict[str, float]] = []

    for row in rows:
        trade_id = int(row["id"])
        symbol = str(row["symbol"] or "")
        side = str(row["side"] or "").upper()
        qty = _to_float(row["quantity"])
        px = _to_float(row["price"])
        notional = qty * px

        if side == "BUY":
            open_buys.setdefault(symbol, []).append(row)
            continue
        if side != "SELL":
            continue
        if "-" not in symbol:
            continue
        if notional <= 1000.0:
            continue

        candidates = open_buys.get(symbol, [])
        matched = None
        for buy in reversed(candidates):
            buy_qty = _to_float(buy["quantity"])
            buy_px = _to_float(buy["price"])
            if buy_qty <= 0 or buy_px <= 0:
                continue
            if abs(buy_qty - qty) > max(1e-6, qty * 1e-6):
                continue
            if (px / buy_px) <= 100.0:
                continue
            matched = buy
            break

        if matched is None:
            continue

        remove_ids.add(trade_id)
        remove_ids.add(int(matched["id"]))
        events.append(
            {
                "sell_id": float(trade_id),
                "buy_id": float(int(matched["id"])),
                "symbol": symbol,
                "buy_price": _to_float(matched["price"]),
                "sell_price": px,
                "sell_notional": notional,
            }
        )

    return sorted(remove_ids), events


def rebuild_state(conn: sqlite3.Connection, portfolio_id: int, removed_ids: List[int]) -> Dict[str, float]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if removed_ids:
        marks = ",".join("?" for _ in removed_ids)
        trades = cur.execute(
            f"""
            SELECT id, timestamp, symbol, side, quantity, price, fees, strategy, status, stop_loss, take_profit
            FROM trades
            WHERE portfolio_id = ? AND id NOT IN ({marks})
            ORDER BY timestamp ASC, id ASC
            """,
            [portfolio_id, *removed_ids],
        ).fetchall()
    else:
        trades = cur.execute(
            """
            SELECT id, timestamp, symbol, side, quantity, price, fees, strategy, status, stop_loss, take_profit
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            [portfolio_id],
        ).fetchall()

    portfolio = cur.execute(
        "SELECT id, total_value, created_at FROM portfolios WHERE id = ?",
        [portfolio_id],
    ).fetchone()
    if portfolio is None:
        raise RuntimeError(f"Portfolio {portfolio_id} not found")

    earliest_snapshot = cur.execute(
        """
        SELECT total_value FROM portfolio_snapshots
        WHERE portfolio_id = ?
        ORDER BY timestamp ASC LIMIT 1
        """,
        [portfolio_id],
    ).fetchone()
    initial_capital = _to_float(earliest_snapshot["total_value"]) if earliest_snapshot else 100.0
    if initial_capital <= 0:
        initial_capital = 100.0

    current_price_hint: Dict[str, float] = {
        str(r["symbol"]): _to_float(r["current_price"])
        for r in cur.execute(
            "SELECT symbol, current_price FROM positions WHERE portfolio_id = ?",
            [portfolio_id],
        ).fetchall()
    }

    cash = initial_capital
    realized_total = 0.0
    lots: Dict[str, LotState] = {}
    snapshots_to_insert: List[Dict[str, float]] = []

    for tr in trades:
        symbol = str(tr["symbol"] or "")
        side = str(tr["side"] or "").upper()
        qty = _to_float(tr["quantity"])
        price = _to_float(tr["price"])
        fees = _to_float(tr["fees"])
        if qty <= 0 or price <= 0 or side not in {"BUY", "SELL"}:
            continue

        lot = lots.setdefault(symbol, LotState())
        trade_value = qty * price

        if side == "BUY":
            cash -= (trade_value + fees)
            total_qty = lot.quantity + qty
            lot.average_price = (
                ((lot.quantity * lot.average_price) + trade_value) / total_qty if total_qty > 0 else 0.0
            )
            lot.quantity = total_qty
            lot.stop_loss = tr["stop_loss"]
            lot.take_profit = tr["take_profit"]
            if lot.opened_at is None:
                lot.opened_at = tr["timestamp"]
        else:
            close_qty = min(qty, lot.quantity)
            if close_qty <= 0:
                continue
            cash += (close_qty * price) - fees
            realized = (price - lot.average_price) * close_qty - fees
            realized_total += realized
            lot.realized_pnl_open += realized
            lot.quantity -= close_qty
            if lot.quantity <= 0:
                lots.pop(symbol, None)
            else:
                lots[symbol] = lot

        invested_cost = sum(v.quantity * v.average_price for v in lots.values())
        snapshot_value = cash + invested_cost
        snapshots_to_insert.append(
            {
                "timestamp": tr["timestamp"],
                "total_value": snapshot_value,
                "cash_balance": cash,
                "invested_amount": invested_cost,
                "total_pnl": realized_total,
                "total_pnl_percentage": ((snapshot_value - initial_capital) / initial_capital) * 100.0,
            }
        )

    # Current portfolio valuation with last known prices.
    invested_current = 0.0
    unrealized_total = 0.0
    for symbol, lot in lots.items():
        current_price = current_price_hint.get(symbol, lot.average_price)
        if current_price <= 0:
            current_price = lot.average_price
        invested_current += lot.quantity * current_price
        unrealized_total += (current_price - lot.average_price) * lot.quantity
        current_price_hint[symbol] = current_price

    total_value = cash + invested_current
    total_pnl = realized_total
    total_pnl_percentage = ((total_value - initial_capital) / initial_capital) * 100.0 if initial_capital > 0 else 0.0

    # Apply DB updates atomically.
    conn.execute("BEGIN")
    try:
        if removed_ids:
            marks = ",".join("?" for _ in removed_ids)
            conn.execute(
                f"DELETE FROM trades WHERE portfolio_id = ? AND id IN ({marks})",
                [portfolio_id, *removed_ids],
            )

        conn.execute("DELETE FROM positions WHERE portfolio_id = ?", [portfolio_id])
        for symbol, lot in lots.items():
            conn.execute(
                """
                INSERT INTO positions (
                    symbol, quantity, average_price, current_price, unrealized_pnl, realized_pnl,
                    stop_loss, take_profit, opened_at, updated_at, portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    symbol,
                    lot.quantity,
                    lot.average_price,
                    current_price_hint[symbol],
                    (current_price_hint[symbol] - lot.average_price) * lot.quantity,
                    lot.realized_pnl_open,
                    lot.stop_loss,
                    lot.take_profit,
                    lot.opened_at,
                    datetime.utcnow().isoformat(sep=" "),
                    portfolio_id,
                ],
            )

        conn.execute("DELETE FROM portfolio_snapshots WHERE portfolio_id = ?", [portfolio_id])
        for snap in snapshots_to_insert:
            conn.execute(
                """
                INSERT INTO portfolio_snapshots (
                    portfolio_id, total_value, cash_balance, invested_amount, total_pnl,
                    total_pnl_percentage, timestamp, daily_return, weekly_return,
                    monthly_return, sharpe_ratio, max_drawdown
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                """,
                [
                    portfolio_id,
                    snap["total_value"],
                    snap["cash_balance"],
                    snap["invested_amount"],
                    snap["total_pnl"],
                    snap["total_pnl_percentage"],
                    snap["timestamp"],
                ],
            )

        # Insert a current snapshot with unrealized included.
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (
                portfolio_id, total_value, cash_balance, invested_amount, total_pnl,
                total_pnl_percentage, timestamp, daily_return, weekly_return,
                monthly_return, sharpe_ratio, max_drawdown
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
            """,
            [
                portfolio_id,
                total_value,
                cash,
                invested_current,
                realized_total + unrealized_total,
                total_pnl_percentage,
                datetime.utcnow().isoformat(sep=" "),
            ],
        )

        conn.execute(
            """
            UPDATE portfolios
            SET total_value = ?, cash_balance = ?, invested_amount = ?, total_pnl = ?,
                total_pnl_percentage = ?, updated_at = ?
            WHERE id = ?
            """,
            [
                total_value,
                cash,
                invested_current,
                total_pnl,
                total_pnl_percentage,
                datetime.utcnow().isoformat(sep=" "),
                portfolio_id,
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "initial_capital": initial_capital,
        "cash_balance": cash,
        "invested_amount": invested_current,
        "total_value": total_value,
        "realized_total": realized_total,
        "unrealized_total": unrealized_total,
        "open_positions": float(len(lots)),
        "removed_trades": float(len(removed_ids)),
    }


def main():
    parser = argparse.ArgumentParser(description="Repair corrupted portfolio ledger state")
    parser.add_argument("--db", default="trading_bot.db", help="Path to SQLite DB")
    parser.add_argument("--portfolio-id", type=int, default=1, help="Portfolio id")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    backup_path = db_path.with_suffix(db_path.suffix + f".bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    backup_path.write_bytes(db_path.read_bytes())
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, timestamp, symbol, side, quantity, price, fees FROM trades WHERE portfolio_id = ? ORDER BY timestamp ASC, id ASC",
            [args.portfolio_id],
        ).fetchall()
        remove_ids, events = detect_anomalous_trade_ids(rows)
        print(f"Anomalous events found: {len(events)}")
        for e in events:
            print(e)
        print(f"Trades marked for removal: {remove_ids}")

        summary = rebuild_state(conn, args.portfolio_id, remove_ids)
        print("Repair summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
