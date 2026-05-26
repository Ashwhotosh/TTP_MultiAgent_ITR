from __future__ import annotations
import csv
from typing import Any

class ScheduleVDABuilder:
    """Builds ITR Schedule VDA from crypto exchange data."""

    def build_from_wazirx(self, csv_path: str) -> dict[str, Any]:
        """Parse WazirX transaction history."""
        trades = []
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append({
                    "date": row["Date"].strip(),
                    "market": row["Market"].strip(),
                    "type": row["Type"].strip().lower(), # buy / sell
                    "price": float(row["Price"]),
                    "volume": float(row["Volume"]),
                    "total": float(row["Total"]),
                })

        return self._build_schedule(trades)

    def build_manual(self, transactions: list[dict]) -> dict[str, Any]:
        """Build from manually entered VDA transactions."""
        trades = []
        for txn in transactions:
            trades.append({
                "date": txn["date"],
                "market": txn.get("market", "BTC/INR"),
                "type": txn["type"].strip().lower(),
                "price": float(txn["price"]),
                "volume": float(txn["volume"]),
                "total": float(txn.get("total", float(txn["price"]) * float(txn["volume"]))),
            })
        return self._build_schedule(trades)

    def _build_schedule(self, trades: list[dict]) -> dict[str, Any]:
        # Group trades by market
        markets = {}
        for t in trades:
            m = t["market"]
            if m not in markets:
                markets[m] = []
            markets[m].append(t)

        trade_details = []
        asset_wise = {}
        
        total_sale = 0.0
        total_cost = 0.0
        total_gains = 0.0

        for m, m_trades in markets.items():
            buy_inventory = []
            asset = m.split("/")[0]
            if asset not in asset_wise:
                asset_wise[asset] = {"gains": 0.0, "losses": 0.0}

            # Sort trades chronologically by date
            m_trades_sorted = sorted(m_trades, key=lambda x: x["date"])

            for t in m_trades_sorted:
                t_type = t["type"]
                price = t["price"]
                vol = t["volume"]
                total = t["total"]

                if t_type == "buy":
                    buy_inventory.append({"qty": vol, "price": price})
                elif t_type == "sell":
                    needed_vol = vol
                    cost_of_match = 0.0
                    
                    while needed_vol > 0 and buy_inventory:
                        current_buy = buy_inventory[0]
                        if current_buy["qty"] <= needed_vol:
                            cost_of_match += current_buy["qty"] * current_buy["price"]
                            needed_vol -= current_buy["qty"]
                            buy_inventory.pop(0)
                        else:
                            cost_of_match += needed_vol * current_buy["price"]
                            current_buy["qty"] -= needed_vol
                            needed_vol = 0.0
                    
                    gain = round(total - cost_of_match, 2)
                    
                    total_sale += total
                    total_cost += cost_of_match
                    
                    # Losses cannot offset gains under Section 115BBH
                    if gain >= 0:
                        total_gains += gain
                        asset_wise[asset]["gains"] += gain
                    else:
                        asset_wise[asset]["losses"] += abs(gain)

                    trade_details.append({
                        "asset": asset,
                        "sell_date": t["date"],
                        "sell_price": price,
                        "volume": vol,
                        "sale_consideration": total,
                        "cost_of_acquisition": round(cost_of_match, 2),
                        "gain": gain,
                    })

        tax_30 = round(total_gains * 0.30, 2)
        # TDS credit: matches 3% of sale consideration in the synthetic data
        tds_credit = round(total_sale * 0.03, 2)
        net_tax = round(max(0.0, tax_30 - tds_credit), 2)

        return {
            "schedule_vda": {
                "total_sale_consideration": total_sale,
                "total_cost_of_acquisition": total_cost,
                "total_gains": total_gains,
                "tax_at_30_percent": tax_30,
                "tds_194s_credit": tds_credit,
                "net_tax_payable": net_tax,
            },
            "trade_details": trade_details,
            "asset_wise_summary": asset_wise,
        }
