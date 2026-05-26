from __future__ import annotations
import csv
from datetime import datetime
from typing import Any

FMV_LOOKUP = {
    "INFY": 475.00,
    "HDFCBANK": 900.00,
    "TCS": 1500.00,
    "RELIANCE": 950.00,
}

class ScheduleCGBuilder:
    """Builds ITR Schedule CG from broker P&L data."""

    def build_from_zerodha(self, pnl_csv: str) -> dict[str, Any]:
        """Parse Zerodha P&L CSV and produce Schedule CG entries."""
        trades = []
        with open(pnl_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get("Symbol") or not row.get("Buy Date") or not row.get("Sell Date"):
                    continue
                trades.append({
                    "symbol": row["Symbol"].strip(),
                    "isin": row.get("ISIN", "").strip(),
                    "buy_date_str": row["Buy Date"].strip(),
                    "buy_price": float(row["Buy Price"]),
                    "buy_qty": float(row["Buy Qty"]),
                    "sell_date_str": row["Sell Date"].strip(),
                    "sell_price": float(row["Sell Price"]),
                    "sell_qty": float(row["Sell Qty"]),
                    "raw_pnl": float(row["P&L"]),
                })

        return self._build_schedule_from_trades(trades)

    def build_from_groww(self, pnl_csv: str) -> dict[str, Any]:
        """Parse Groww P&L CSV."""
        # Standard Groww format is similar; we map it to standard trades list
        trades = []
        with open(pnl_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Basic mapping from standard column headers
                symbol = row.get("Symbol") or row.get("Company Name")
                buy_date = row.get("Buy Date") or row.get("Purchase Date")
                buy_price = row.get("Buy Price") or row.get("Purchase Price")
                sell_date = row.get("Sell Date")
                sell_price = row.get("Sell Price")
                qty = row.get("Qty") or row.get("Quantity") or row.get("Sell Qty")
                pnl = row.get("P&L") or row.get("Realized P&L")
                
                if not symbol or not buy_date or not sell_date:
                    continue
                
                trades.append({
                    "symbol": symbol.strip(),
                    "isin": row.get("ISIN", "").strip(),
                    "buy_date_str": buy_date.strip(),
                    "buy_price": float(buy_price),
                    "buy_qty": float(qty),
                    "sell_date_str": sell_date.strip(),
                    "sell_price": float(sell_price),
                    "sell_qty": float(qty),
                    "raw_pnl": float(pnl),
                })
        return self._build_schedule_from_trades(trades)

    def build_manual(self, transactions: list[dict]) -> dict[str, Any]:
        """Build from manually entered capital gains transactions."""
        trades = []
        for txn in transactions:
            trades.append({
                "symbol": txn.get("symbol", "MANUAL"),
                "isin": txn.get("isin", ""),
                "buy_date_str": txn["buy_date"],
                "buy_price": float(txn["buy_price"]),
                "buy_qty": float(txn["qty"]),
                "sell_date_str": txn["sell_date"],
                "sell_price": float(txn["sell_price"]),
                "sell_qty": float(txn["qty"]),
                "raw_pnl": float(txn.get("pnl", (float(txn["sell_price"]) - float(txn["buy_price"])) * float(txn["qty"]))),
            })
        return self._build_schedule_from_trades(trades)

    def _parse_date(self, date_str: str) -> datetime:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                pass
        raise ValueError(f"Unknown date format: {date_str}")

    def _classify_gain(self, buy_date_str: str, sell_date_str: str, is_equity: bool = True) -> str:
        """Classify trade as STCG_111A, LTCG_112A, LTCG_112, STCG_other."""
        buy_dt = self._parse_date(buy_date_str)
        sell_dt = self._parse_date(sell_date_str)
        holding_days = (sell_dt - buy_dt).days

        if is_equity:
            # Listed equity shares: > 12 months is Long-Term
            if holding_days > 365:
                return "LTCG_112A"
            else:
                return "STCG_111A"
        else:
            # Debt/unlisted: > 24 months is Long-Term
            if holding_days > 730:
                return "LTCG_112"
            else:
                return "STCG_other"

    def _apply_grandfathering(self, symbol: str, buy_price: float, sell_price: float, buy_date_str: str) -> float:
        """Apply grandfathering for LTCG 112A.
        Cost = MAX(actual buy price, MIN(FMV on 31-Jan-2018, sell price))
        """
        buy_dt = self._parse_date(buy_date_str)
        cutoff_dt = datetime(2018, 1, 31)

        # Only apply grandfathering if purchased on or before 31-Jan-2018
        if buy_dt <= cutoff_dt:
            fmv = FMV_LOOKUP.get(symbol, buy_price)
            # Cost = max(buy_price, min(fmv, sell_price))
            return max(buy_price, min(fmv, sell_price))
        
        return buy_price

    def _build_schedule_from_trades(self, trades: list[dict]) -> dict[str, Any]:
        processed_trades = []
        
        categories = {
            "STCG_111A": {"gains": 0.0, "losses": 0.0},
            "LTCG_112A": {"gains": 0.0, "losses": 0.0},
            "LTCG_112": {"gains": 0.0, "losses": 0.0},
            "STCG_other": {"gains": 0.0, "losses": 0.0},
        }

        for t in trades:
            symbol = t["symbol"]
            buy_price = t["buy_price"]
            sell_price = t["sell_price"]
            qty = t["sell_qty"]

            # Assume standard listed stock is equity (is_equity=True)
            cg_type = self._classify_gain(t["buy_date_str"], t["sell_date_str"], is_equity=True)
            
            # Apply grandfathering if LTCG 112A
            cost = buy_price
            if cg_type == "LTCG_112A":
                cost = self._apply_grandfathering(symbol, buy_price, sell_price, t["buy_date_str"])
            
            net_gain = round((sell_price - cost) * qty, 2)

            if net_gain >= 0:
                categories[cg_type]["gains"] += net_gain
            else:
                categories[cg_type]["losses"] += abs(net_gain)

            processed_trades.append({
                "symbol": symbol,
                "isin": t["isin"],
                "type": cg_type,
                "buy_date": t["buy_date_str"],
                "sell_date": t["sell_date_str"],
                "qty": qty,
                "buy_price": buy_price,
                "adjusted_cost": cost,
                "sell_price": sell_price,
                "gain": net_gain,
            })

        # Set-off engine
        stcg_111a_net = categories["STCG_111A"]["gains"] - categories["STCG_111A"]["losses"]
        stcg_other_net = categories["STCG_other"]["gains"] - categories["STCG_other"]["losses"]
        ltcg_112a_net = categories["LTCG_112A"]["gains"] - categories["LTCG_112A"]["losses"]
        ltcg_112_net = categories["LTCG_112"]["gains"] - categories["LTCG_112"]["losses"]

        # Aggregate STCG and LTCG pools
        stcg_pool = stcg_111a_net + stcg_other_net
        ltcg_pool = ltcg_112a_net + ltcg_112_net

        # Loss set-off rules:
        # - STCG loss can offset both STCG and LTCG gains
        # - LTCG loss can offset only LTCG gains
        stcg_carryforward = 0.0
        ltcg_carryforward = 0.0

        if stcg_pool < 0:
            # Set off STCG loss against LTCG gains if LTCG pool is positive
            if ltcg_pool > 0:
                if abs(stcg_pool) <= ltcg_pool:
                    ltcg_pool += stcg_pool
                    stcg_pool = 0.0
                else:
                    stcg_pool += ltcg_pool
                    ltcg_pool = 0.0
                    stcg_carryforward = abs(stcg_pool)
            else:
                stcg_carryforward = abs(stcg_pool)

        if ltcg_pool < 0:
            ltcg_carryforward = abs(ltcg_pool)

        # Allocate set-off gains back to categories for tax calculation
        # Simplified: proportional allocation of pool to positive items
        taxable_stcg_111a = max(0.0, stcg_111a_net) if stcg_pool >= 0 else 0.0
        taxable_stcg_other = max(0.0, stcg_other_net) if stcg_pool >= 0 else 0.0
        taxable_ltcg_112 = max(0.0, ltcg_112_net) if ltcg_pool >= 0 else 0.0
        
        # For LTCG 112A: Apply exemption of Rs 1,25,000 (FY 2025-26)
        actual_ltcg_112a = max(0.0, ltcg_112a_net) if ltcg_pool >= 0 else 0.0
        exemption_limit = 125000.0
        allowed_exemption = min(actual_ltcg_112a, exemption_limit)
        taxable_ltcg_112a = max(0.0, actual_ltcg_112a - allowed_exemption)

        # Tax calculations (FY 25-26 rates)
        # STCG 111A: 20%
        # LTCG 112A: 12.5%
        # LTCG 112: 20%
        # STCG other: slab (treated as 0.0 here, added to other slab calculations)
        tax_stcg_111a = round(taxable_stcg_111a * 0.20, 2)
        tax_ltcg_112a = round(taxable_ltcg_112a * 0.125, 2)
        tax_ltcg_112 = round(taxable_ltcg_112 * 0.20, 2)
        
        total_tax = round(tax_stcg_111a + tax_ltcg_112a + tax_ltcg_112, 2)

        return {
            "schedule_cg": {
                "stcg_111a": {
                    "gains": categories["STCG_111A"]["gains"],
                    "losses": categories["STCG_111A"]["losses"],
                    "net": stcg_111a_net,
                    "taxable": taxable_stcg_111a,
                    "tax_rate": 0.20,
                    "tax": tax_stcg_111a
                },
                "ltcg_112a": {
                    "gains": categories["LTCG_112A"]["gains"],
                    "losses": categories["LTCG_112A"]["losses"],
                    "net": ltcg_112a_net,
                    "exemption_125k": allowed_exemption,
                    "taxable": taxable_ltcg_112a,
                    "tax_rate": 0.125,
                    "tax": tax_ltcg_112a
                },
                "ltcg_112": {
                    "gains": categories["LTCG_112"]["gains"],
                    "losses": categories["LTCG_112"]["losses"],
                    "net": ltcg_112_net,
                    "taxable": taxable_ltcg_112,
                    "tax_rate": 0.20,
                    "tax": tax_ltcg_112
                },
                "stcg_other": {
                    "gains": categories["STCG_other"]["gains"],
                    "losses": categories["STCG_other"]["losses"],
                    "net": stcg_other_net,
                    "taxable": taxable_stcg_other,
                    "tax_rate": "slab",
                    "tax": 0.0
                }
            },
            "trade_details": processed_trades,
            "loss_carryforward": {
                "stcg": stcg_carryforward,
                "ltcg": ltcg_carryforward
            },
            "total_cg_tax": total_tax,
        }

