#!/usr/bin/env python3
"""Convert a Robinhood account activity CSV into Ghostfolio's CSV import format."""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Delisted tickers Yahoo no longer knows: import with prices taken as given.
MANUAL_SYMBOLS = {"APHA", "NKLA"}

def parse_date(s):
    return datetime.strptime(s, "%m/%d/%Y").date()


def parse_money(s):
    """'$1,234.56' -> 1234.56, '($12.00)' -> -12.00, '' -> 0."""
    s = s.strip()
    if not s:
        return Decimal(0)
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "")
    value = Decimal(s)
    return -value if negative else value


def parse_quantity(s):
    """Robinhood writes shares leaving the account (merger, symbol exchange)
    with a trailing S, e.g. '10S'. Return those as negative."""
    s = s.strip()
    if not s:
        return Decimal(0)
    if s.endswith("S"):
        return -Decimal(s[:-1])
    return Decimal(s)


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # Robinhood appends a blank line and a disclaimer: keep only real activity.
    rows = [r for r in rows if r.get("Activity Date")]
    # The export is newest-first. Reverse it, then sort by date: Python's sort is
    # stable, so rows on the same day keep their real (oldest-first) order.
    rows.reverse()
    rows.sort(key=lambda r: parse_date(r["Activity Date"]))
    return rows

def build_trades(rows):
    """Turn Robinhood rows into Ghostfolio-style trades, applying cancellations,
    splits and mergers in date order. Returns (trades, held)."""
    trades = []                  # each: date, symbol, action, qty, price, note
    held = defaultdict(Decimal)  # running share count per symbol
    merged = set()               # merger dates already handled

    for r in rows:
        code, sym = r["Trans Code"], r["Instrument"]
        date = parse_date(r["Activity Date"])
        qty = parse_quantity(r["Quantity"])

        if code in ("Buy", "Sell"):
            action = code.upper()
            trades.append({"date": date, "symbol": sym, "action": action, "qty": qty,
                           "price": parse_money(r["Price"]), "note": ""})
            held[sym] += qty if action == "BUY" else -qty

        elif code == "REC":  # free stock received: it cost nothing
            trades.append({"date": date, "symbol": sym, "action": "BUY", "qty": qty,
                           "price": Decimal(0), "note": "Free stock (REC)"})
            held[sym] += qty

        elif code in ("BCXL", "SCXL"):  # cancels an earlier buy/sell of the same size
            action = "BUY" if code == "BCXL" else "SELL"
            match = next((t for t in reversed(trades) if t["symbol"] == sym
                          and t["action"] == action and t["qty"] == qty), None)
            if match is None:
                raise ValueError(f"No earlier {action} of {qty} {sym} to cancel ({date})")
            trades.remove(match)
            held[sym] += -qty if action == "BUY" else qty
            print(f"  cancelled {action} {qty} {sym} from {match['date']}")

        elif code == "SPL":
            # Robinhood rounds the split quantity, so derive the ratio from the
            # holdings and round it to a whole number (e.g. 3.0003 -> 3).
            ratio = ((held[sym] + qty) / held[sym]).to_integral_value()
            for t in trades:
                if t["symbol"] == sym:  # restate earlier trades in post-split shares
                    t["qty"] *= ratio
                    t["price"] /= ratio
            held[sym] *= ratio
            print(f"  split {sym} {ratio}-for-1 on {date}")

        elif code == "MRGS" and date not in merged:
            # A merger is two MRGS rows on one day: old shares out (negative), new in.
            merged.add(date)
            pair = [m for m in rows if m["Trans Code"] == "MRGS"
                    and parse_date(m["Activity Date"]) == date]
            out_r = next(m for m in pair if parse_quantity(m["Quantity"]) < 0)
            in_r = next(m for m in pair if parse_quantity(m["Quantity"]) > 0)
            out_sym, out_qty = out_r["Instrument"], -parse_quantity(out_r["Quantity"])
            in_sym, in_qty = in_r["Instrument"], parse_quantity(in_r["Quantity"])
            # Cash paid for the leftover fraction of a share (the CIL row).
            cash = sum((parse_money(c["Amount"]) for c in rows
                        if c["Trans Code"] == "CIL" and c["Instrument"] == in_sym),
                       Decimal(0))
            # Carry the cost over: "sell" the old shares at their average cost
            # (no gain), "buy" the new ones for that value minus the cash received.
            buys = [t for t in trades if t["symbol"] == out_sym and t["action"] == "BUY"]
            avg = sum(t["qty"] * t["price"] for t in buys) / sum(t["qty"] for t in buys)
            value = out_qty * avg
            trades.append({"date": date, "symbol": out_sym, "action": "SELL", "qty": out_qty,
                           "price": avg, "note": f"Merger into {in_sym}"})
            trades.append({"date": date, "symbol": in_sym, "action": "BUY", "qty": in_qty,
                           "price": (value - cash) / in_qty,
                           "note": f"Merger from {out_sym} (cash in lieu {cash})"})
            held[out_sym] -= out_qty
            held[in_sym] += in_qty
            print(f"  merger {out_qty} {out_sym} -> {in_qty} {in_sym} "
                  f"+ ${cash} cash on {date}")

    return trades, held


CASH_CODES = {"ACH", "RTP", "FUTSWP"}  # bank/cash moves: set as the account's cash balance
TRADE_CODES = {"Buy", "Sell", "REC", "BCXL", "SCXL", "SPL", "MRGS", "CIL", "SXCH"}


def build_income_and_fees(rows):
    """Dividends, stock lending income and ADR fees as Ghostfolio activities.
    Returns (activities, totals per Robinhood code)."""
    activities = []
    totals = Counter()
    for r in rows:
        code, sym = r["Trans Code"], r["Instrument"]
        date = parse_date(r["Activity Date"])
        amount = parse_money(r["Amount"])
        if code == "CDIV":
            activities.append({"date": date, "symbol": sym, "source": "YAHOO",
                               "action": "dividend", "qty": Decimal(1), "price": amount,
                               "fee": Decimal(0), "note": ""})
        elif code == "SLIP":
            activities.append({"date": date, "symbol": "Stock Lending Income",
                               "source": "MANUAL", "action": "interest",
                               "qty": Decimal(1), "price": amount,
                               "fee": Decimal(0), "note": f"Lent {sym}"})
        elif code in ("DFEE", "AFEE"):
            activities.append({"date": date, "symbol": "ADR Fees", "source": "MANUAL",
                               "action": "fee", "qty": Decimal(0), "price": Decimal(0),
                               "fee": -amount, "note": f"{code} {sym}"})
        elif code in CASH_CODES:
            totals["cash moves (skipped)"] += amount
            continue
        elif code in TRADE_CODES:
            continue
        else:
            raise ValueError(f"Unknown Trans Code {code!r} on {date}: add a rule for it")
        totals[code] += amount
    return activities, totals


FIELDS = ["Date", "Code", "DataSource", "Currency", "Price", "Quantity",
          "Action", "Fee", "Note", "Account"]


def fmt(d):
    """Decimal -> plain string with at most 8 decimals and no trailing zeros."""
    s = f"{d.quantize(Decimal('0.00000001')):f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def write_import(path, activities, account):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for a in sorted(activities, key=lambda a: a["date"]):
            w.writerow([a["date"].isoformat(), a["symbol"], a["source"], "USD",
                        fmt(a["price"]), fmt(a["qty"]), a["action"], fmt(a["fee"]),
                        a["note"], account])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Robinhood activity export")
    parser.add_argument("--account", default="Brokerage",
                        help="Ghostfolio account name (default: Brokerage)")
    parser.add_argument("--write", action="store_true",
                        help="write the import file (default: dry run, summary only)")
    args = parser.parse_args()

    rows = read_rows(args.csv)
    print(f"{len(rows)} activity rows, "
        f"{rows[0]['Activity Date']} -> {rows[-1]['Activity Date']}")
    for code, n in Counter(r["Trans Code"] for r in rows).most_common():
        print(f"  {code or '(blank)':8} {n}")
    print("\nAdjustments:")
    trades, held = build_trades(rows)
    print(f"\n{len(trades)} trades")
    print("\nHoldings after all adjustments:")
    for sym, qty in sorted(held.items()):
        if qty != 0:
            print(f"  {sym:6} {qty}")

    activities = [dict(t, source="MANUAL" if t["symbol"] in MANUAL_SYMBOLS else "YAHOO", 
                       action=t["action"].lower(), fee=Decimal(0))
                  for t in trades]
    income, totals = build_income_and_fees(rows)
    activities += income

    print("\nIncome, fees and skipped cash:")
    for code, total in totals.items():
        print(f"  {code:22} {total:>12}")
    print(f"\n{len(activities)} activities: "
          + ", ".join(f"{n} {a}" for a, n in Counter(a["action"] for a in activities).items()))

    out = args.csv.with_name("ghostfolio-import.csv")
    if args.write:
        write_import(out, activities, args.account)
        print(f"\nWrote {out}")
    else:
        print(f"\nDry run: add --write to create {out}")


if __name__ == "__main__":
    main()
