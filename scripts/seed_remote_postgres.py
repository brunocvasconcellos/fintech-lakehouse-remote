import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from faker import Faker

fake = Faker("pt_BR")
random.seed(int(os.getenv("SEED_RANDOM_SEED", "42")))

DB_CONFIG = dict(
    host=os.environ["SOURCE_POSTGRES_HOST"],
    port=int(os.getenv("SOURCE_POSTGRES_PORT", "5432")),
    dbname=os.environ["SOURCE_POSTGRES_DB"],
    user=os.environ["SOURCE_POSTGRES_USER"],
    password=os.environ["SOURCE_POSTGRES_PASSWORD"],
)

NUM_CUSTOMERS = int(os.getenv("SEED_CUSTOMERS", "10000"))
NUM_MERCHANTS = int(os.getenv("SEED_MERCHANTS", "2000"))
NUM_ACCOUNTS = int(os.getenv("SEED_ACCOUNTS", "15000"))
NUM_TRANSACTIONS = int(os.getenv("SEED_TRANSACTIONS", "100000"))
START_DATE = datetime.fromisoformat(os.getenv("SEED_START_DATE", "2025-01-01"))
END_DATE = datetime.fromisoformat(os.getenv("SEED_END_DATE", "2025-12-31"))

states = ["SP", "RJ", "MG", "PR", "SC", "RS", "BA", "PE", "CE", "GO"]
merchant_categories = [
    "groceries",
    "fuel",
    "rent",
    "salary",
    "utilities",
    "shopping",
    "transport",
    "health",
    "education",
    "restaurant",
]
transaction_types = [
    "PIX",
    "DEBIT_CARD",
    "CREDIT_CARD",
    "TRANSFER",
    "BILL_PAYMENT",
    "CASH_OUT",
    "SALARY",
]
channels = ["app", "web", "pos", "atm"]
account_types = ["checking", "savings"]


def random_ts() -> datetime:
    delta = END_DATE - START_DATE
    return START_DATE + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def main() -> None:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    with open("/opt/airflow/sql/postgres/source_schema.sql", encoding="utf-8") as f:
        cur.execute(f.read())
    conn.commit()

    customers = []
    for _ in range(NUM_CUSTOMERS):
        customers.append(
            (
                fake.cpf().replace(".", "").replace("-", ""),
                fake.name(),
                fake.date_of_birth(minimum_age=18, maximum_age=85),
                fake.city(),
                random.choice(states),
            )
        )
    cur.executemany(
        "INSERT INTO customers (document_number, full_name, birth_date, city, state) VALUES (%s,%s,%s,%s,%s)",
        customers,
    )
    conn.commit()

    merchants = []
    for _ in range(NUM_MERCHANTS):
        merchants.append(
            (
                fake.company(),
                random.choice(merchant_categories),
                fake.city(),
                random.choice(states),
            )
        )
    cur.executemany(
        "INSERT INTO merchants (merchant_name, merchant_category, city, state) VALUES (%s,%s,%s,%s)",
        merchants,
    )
    conn.commit()

    cur.execute("SELECT customer_id FROM customers")
    customer_ids = [row[0] for row in cur.fetchall()]

    accounts = []
    for _ in range(NUM_ACCOUNTS):
        cid = random.choice(customer_ids)
        opened_at = random_ts()
        balance = round(random.uniform(50, 30000), 2)
        accounts.append(
            (
                cid,
                fake.bban()[:12],
                random.choice(account_types),
                opened_at,
                "active",
                balance,
            )
        )
    cur.executemany(
        "INSERT INTO accounts (customer_id, account_number, account_type, opened_at, status, current_balance) VALUES (%s,%s,%s,%s,%s,%s)",
        accounts,
    )
    conn.commit()

    cur.execute("SELECT account_id, customer_id, current_balance FROM accounts")
    account_rows = cur.fetchall()

    cur.execute("SELECT merchant_id, merchant_category FROM merchants")
    merchant_rows = cur.fetchall()

    insert_sql = (
        "INSERT INTO transactions (account_id, customer_id, merchant_id, transaction_ts, "
        "transaction_type, amount, currency, channel, status, category, balance_before, "
        "balance_after, is_fraud) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )

    batch = []
    for i in range(NUM_TRANSACTIONS):
        account_id, customer_id, balance = random.choice(account_rows)
        merchant_id, category = random.choice(merchant_rows)
        tx_type = random.choice(transaction_types)
        ts = random_ts()
        amount = round(random.uniform(5, 5000), 2)

        if tx_type == "SALARY":
            amount = round(random.uniform(1500, 15000), 2)
            status = "approved"
            category = "salary"
            merchant_id = None
            balance_before = balance
            balance_after = balance + amount
        else:
            approved = balance >= amount or random.random() > 0.04
            status = "approved" if approved else "declined"
            balance_before = balance
            balance_after = balance - amount if approved else balance

        is_fraud = random.random() < 0.005

        batch.append(
            (
                account_id,
                customer_id,
                merchant_id,
                ts,
                tx_type,
                Decimal(str(amount)),
                "BRL",
                random.choice(channels),
                status,
                category,
                Decimal(str(round(balance_before, 2))),
                Decimal(str(round(balance_after, 2))),
                is_fraud,
            )
        )

        if (i + 1) % 10000 == 0:
            cur.executemany(insert_sql, batch)
            conn.commit()
            batch = []

    if batch:
        cur.executemany(insert_sql, batch)
        conn.commit()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
