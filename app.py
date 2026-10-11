
import json
import re
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# --------------------------------------------------
# 1. Application and configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")

app = FastAPI(title="Acme Appliances Ledger Agent")

class Question(BaseModel):
    question: str


# --------------------------------------------------
# 2. Load ledger and exchange rates
# --------------------------------------------------

with open(BASE_DIR / "all_orders.json", encoding="utf-8") as f:
    RAW_ORDERS = json.load(f)

with open(BASE_DIR / "rates.json", encoding="utf-8") as f:
    RATE_DATA = json.load(f)

USD_PER_UNIT = {
    currency: Decimal(str(rate))
    for currency, rate in RATE_DATA["usd_per_unit"].items()
}


# --------------------------------------------------
# 3. Utility functions
# --------------------------------------------------

def parse_ts(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(IST)


def money_usd(row):
    currency = row["currency"]
    if currency not in USD_PER_UNIT:
        raise ValueError(f"Unknown currency: {currency}")

    return Decimal(str(row["amount"])) * USD_PER_UNIT[currency]


def usd_result(value):
    return float(
        value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def sum_usd(rows):
    return sum((money_usd(r) for r in rows), Decimal("0"))


# --------------------------------------------------
# 4. Deduplicate orders: latest updated_at wins
# --------------------------------------------------

_current = {}

for row in RAW_ORDERS:
    order_id = row["id"]

    if (
        order_id not in _current
        or parse_ts(row["updated_at"])
        > parse_ts(_current[order_id]["updated_at"])
    ):
        _current[order_id] = row

ORDERS = list(_current.values())


# --------------------------------------------------
# 5. Known dimensions
# --------------------------------------------------

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

PRODUCTS = sorted(
    {r["product"] for r in ORDERS},
    key=len,
    reverse=True,
)

REGIONS = sorted(
    {r["region"] for r in ORDERS},
    key=len,
    reverse=True,
)


# --------------------------------------------------
# 6. Filter by region, product, customer and date
# --------------------------------------------------

def filter_orders(question):
    q = question.lower()
    rows = ORDERS[:]

    # Region
    for region in REGIONS:
        if re.search(r"\b" + re.escape(region.lower()) + r"\b", q):
            rows = [
                r for r in rows
                if r["region"].lower() == region.lower()
            ]
            break

    # Product
    for product in PRODUCTS:
        if product.lower() in q:
            rows = [
                r for r in rows
                if r["product"].lower() == product.lower()
            ]
            break

    # Customer ID, e.g. C1124
    cm = re.search(r"\bC\d{4}\b", question, re.I)
    if cm:
        customer = cm.group().upper()
        rows = [
            r for r in rows
            if r["customer"].upper() == customer
        ]

    # Explicit date range: YYYY-MM-DD to YYYY-MM-DD
    dm = re.search(
        r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\s*"
        r"(?:to|through|-)\s*"
        r"(20\d{2})-(\d{1,2})-(\d{1,2})\b",
        q,
    )

    if dm:
        start = date(*map(int, dm.groups()[:3]))
        end = date(*map(int, dm.groups()[3:]))

        if end < start:
            raise ValueError("End date precedes start date")

        return [
            r for r in rows
            if start <= parse_ts(r["created_at"]).date() <= end
        ]

    # Month and year: March 2026
    mm = re.search(
        r"\b(january|february|march|april|may|june|july|"
        r"august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\s+(20\d{2})\b",
        q,
    )

    if mm:
        year = int(mm.group(2))
        month = MONTHS[mm.group(1)]
        rows = [
            r for r in rows
            if parse_ts(r["created_at"]).year == year
            and parse_ts(r["created_at"]).month == month
        ]
    else:
        # YYYY-MM
        ym = re.search(r"\b(20\d{2})-(0?[1-9]|1[0-2])\b", q)
        if ym:
            year, month = int(ym.group(1)), int(ym.group(2))
            rows = [
                r for r in rows
                if parse_ts(r["created_at"]).year == year
                and parse_ts(r["created_at"]).month == month
            ]

    return rows


# --------------------------------------------------
# 7. Interpret and answer questions
# --------------------------------------------------

def answer_question(question):
    q = question.strip()
    ql = q.lower()

    if not q:
        raise ValueError("Question cannot be empty")

    rows = filter_orders(q)

    if not rows:
        return 0

    paid = [r for r in rows if r["status"] == "paid"]
    refunded = [r for r in rows if r["status"] == "refunded"]
    voided = [r for r in rows if r["status"] == "void"]

    # Net revenue: paid minus refunded.
    if "net revenue" in ql or "net sales" in ql:
        return usd_result(sum_usd(paid) - sum_usd(refunded))

    # Refund amount or refund count.
    if "refund" in ql:
        if re.search(r"\b(how many|count|number of)\b", ql):
            return len(refunded)
        return usd_result(sum_usd(refunded))

    # Void count.
    if "void" in ql:
        if re.search(r"\b(how many|count|number of)\b", ql):
            return len(voided)
        return usd_result(sum_usd(voided))

    # Rankings: top/highest/best/most.
    if re.search(r"\b(top|highest|most|best)\b", ql):
        if "customer" in ql:
            key_fn = lambda r: r["customer"]
        elif "region" in ql:
            key_fn = lambda r: r["region"]
        else:
            key_fn = lambda r: r["product"]

        quantity_metric = any(
            word in ql
            for word in ("units", "quantity", "items sold")
        )

        groups = {}

        for r in paid:
            key = key_fn(r)
            value = (
                Decimal(str(r["qty"]))
                if quantity_metric
                else money_usd(r)
            )
            groups[key] = groups.get(key, Decimal("0")) + value

        if not groups:
            return 0

        return max(groups, key=groups.get)

    # Unique/distinct customers.
    if "customer" in ql and any(
        word in ql for word in ("unique", "distinct", "different")
    ):
        return len({r["customer"] for r in rows})

    # Average.
    if "average" in ql or re.search(r"\bavg\b", ql):
        if "unit" in ql or "quantity" in ql:
            return (
                round(sum(r["qty"] for r in paid) / len(paid), 2)
                if paid else 0
            )

        return (
            usd_result(sum_usd(paid) / Decimal(len(paid)))
            if paid else 0
        )

    # Quantity sold.
    if any(
        word in ql
        for word in ("quantity", "units", "items sold")
    ):
        return sum(r["qty"] for r in paid)

    # Counts.
    if re.search(r"\b(how many|number of|count)\b", ql):
        if "customer" in ql:
            return len({r["customer"] for r in rows})
        if "paid order" in ql:
            return len(paid)
        if "refunded order" in ql:
            return len(refunded)
        if "order" in ql:
            return len(rows)
        return len(rows)

    # Revenue and sales: only paid orders count as revenue.
    if any(
        word in ql
        for word in (
            "revenue", "sales", "turnover", "income",
            "earned", "earnings", "paid", "money made",
        )
    ):
        return usd_result(sum_usd(paid))

    # Generic total / amount / value.
    if any(word in ql for word in ("total", "amount", "value", "money")):
        return usd_result(sum_usd(paid))

    # Default interpretation: paid-order count.
    return len(paid)


# --------------------------------------------------
# 8. HTTP endpoints
# --------------------------------------------------

@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "Acme Appliances Ledger Agent",
        "unique_orders_loaded": len(ORDERS),
    }


@app.post("/")
@app.post("/answer")
async def ask(payload: Question):
    if not payload.question.strip():
        raise HTTPException(
            status_code=400,
            detail="question is required",
        )

    try:
        result = answer_question(payload.question)
        return {"answer": result}
    except Exception:
        # Avoid returning internal details to the caller.
        raise HTTPException(
            status_code=500,
            detail="Unable to process the question",
        )
