#!/usr/bin/env python3
"""Convert a Copilot Money transaction export into per-account CSVs for Actual Budget.

Account balances and names live in a private JSON config next to the data (never in
this public repo). Each account's history is checked against a known balance: the
script stops if the numbers don't add up.

Config example (accounts.json):
{
  "balance_date": "2026-10-31",
  "accounts": {
    "TOTAL CHECKING": {"out": "chase-checking", "balance": "1234.56",
                       "import_through": "2026-10-31"},
    "Qapital Spend Account": {"out": "qapital", "balance": "100.00", "opening": "0"}
  }
}
- balance: the account's real balance at the end of balance_date (from a statement)
- import_through: last date to import (default: everything); use it when Actual
  already has the later transactions
- opening: force the opening balance (e.g. 0 for an account opened inside the
  history); any difference is added as one "Copilot history gap" adjustment
"""
import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Copilot category -> Actual category (anything not listed keeps its name).
CATEGORY_MAP = {
    "Subscriptions": "Online Subscriptions",
    "Candy Crush": "Online Subscriptions",
}

# Qapital savings rules: money moved from the Spend account into Qapital goals.
QAPITAL_RULES = {"Youtube", "Set & Forget", "Apple Healthkit Workouts", "Payday", "52 Week"}

# Categories that must already exist in Actual (import matches by exact name).
ACTUAL_CATEGORIES = {
    "Rent", "Bills", "Groceries", "Student Loans", "Pets", "Home",
    "Amazon", "Online Subscriptions", "Restaurants", "Shopping", "Tree Fund",
    "Savings", "Other", "Transfer (history)", "Income", "Starting Balances",
}

FIELDS = ["Date", "Payee", "Notes", "Category", "Amount"]


def clean(s):
    """Copilot uses non-breaking spaces in some names ('Apple\\xa0Card')."""
    return " ".join(s.replace("\xa0", " ").split())


def actual_category(r):
    """Pick the Actual category for one Copilot row."""
    kind, excluded, cat = r["type"], r["excluded"] == "true", r["category"]
    if kind == "internal transfer":
        return CATEGORY_MAP.get(cat, cat) if (cat and not excluded) else "Transfer (history)"
    if kind == "income":
        return "Income"
    if excluded:  # excluded spending in Copilot has no category
        return "Savings" if r["name"] in QAPITAL_RULES else "Other"
    return CATEGORY_MAP.get(cat, cat) if cat else "Other"


def convert_account(rows, name, cfg, balance_date):
    """Return (output rows, summary dict) for one account, or raise if it doesn't add up."""
    txns = [r for r in rows if clean(r["account"]) == name and r["status"] == "posted"]
    if not txns:
        raise ValueError(f"No posted transactions for account {name!r}")
    for r in txns:
        r["_date"] = date.fromisoformat(r["date"])
        r["_amount"] = -Decimal(r["amount"])  # Copilot: spending positive. Actual: negative.

    balance = Decimal(cfg["balance"])
    history = sum(r["_amount"] for r in txns if r["_date"] <= balance_date)
    implied_opening = balance - history
    opening = Decimal(cfg["opening"]) if "opening" in cfg else implied_opening
    gap = implied_opening - opening

    through = date.fromisoformat(cfg["import_through"]) if "import_through" in cfg else None
    keep = sorted((r for r in txns if through is None or r["_date"] <= through),
                  key=lambda r: r["_date"])
    first = keep[0]["_date"]

    out = [{"Date": (first - timedelta(days=1)).isoformat(), "Payee": "Starting Balance",
            "Notes": "Opening balance derived from Copilot history", "Category": "Starting Balances",
            "Amount": opening}]
    for r in keep:
        out.append({"Date": r["date"], "Payee": clean(r["name"]), "Notes": clean(r["note"]),
                    "Category": actual_category(r), "Amount": r["_amount"]})
    if gap:
        out.append({"Date": balance_date.isoformat(), "Payee": "Balance adjustment",
                    "Notes": "Copilot history gap: transactions missing from the export",
                    "Category": "Other", "Amount": gap})

    unknown = {o["Category"] for o in out} - ACTUAL_CATEGORIES
    if unknown:
        raise ValueError(f"{name}: categories not in Actual: {sorted(unknown)}")

    # The check: everything up to balance_date must land exactly on the real balance.
    at_balance_date = sum(o["Amount"] for o in out if date.fromisoformat(o["Date"]) <= balance_date)
    if at_balance_date != balance:
        raise ValueError(f"{name}: history ends at {at_balance_date}, statement says {balance}")

    summary = {"rows": len(keep), "from": first, "to": keep[-1]["_date"],
               "opening": opening, "gap": gap, "end": sum(o["Amount"] for o in out),
               "categories": Counter(o["Category"] for o in out[1:])}
    return out, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path, help="Copilot transactions export")
    parser.add_argument("config", type=Path, help="private accounts.json (see above)")
    parser.add_argument("--write", action="store_true",
                        help="write actual-<out>.csv files (default: dry run, summary only)")
    parser.add_argument("--out-dir", type=Path,
                        help="where to write (default: next to the export)")
    parser.add_argument("--only", metavar="ACCOUNT", action="append",
                        help="process just this Copilot account (repeatable)")
    args = parser.parse_args()

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    config = json.loads(args.config.read_text())
    balance_date = date.fromisoformat(config["balance_date"])
    out_dir = args.out_dir or args.csv.parent

    print(f"{len(rows)} Copilot rows; accounts: {', '.join(sorted({clean(r['account']) for r in rows}))}")
    for name, cfg in config["accounts"].items():
        if args.only and name not in args.only:
            continue
        out, s = convert_account(rows, name, cfg, balance_date)
        print(f"\n{name} -> actual-{cfg['out']}.csv")
        print(f"  {s['rows']} transactions, {s['from']} -> {s['to']}")
        print(f"  opening balance {s['opening']}"
              + (f", gap adjustment {s['gap']} on {balance_date}" if s["gap"] else ""))
        print(f"  balance on {balance_date} matches statement; balance after last row {s['end']}")
        for cat, n in s["categories"].most_common():
            print(f"    {n:5}  {cat}")
        if args.write:
            path = out_dir / f"actual-{cfg['out']}.csv"
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(out)
            print(f"  wrote {path}")
    if not args.write:
        print(f"\nDry run: add --write to create the files in {out_dir}")


if __name__ == "__main__":
    main()
