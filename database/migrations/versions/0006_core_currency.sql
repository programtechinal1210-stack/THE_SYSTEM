-- 0006 Currency service: core_currencies + core_exchange_rates.
-- Additive only; no existing data is altered.
CREATE TABLE core_currencies (
    id CHAR(32) NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10) NOT NULL DEFAULT '',
    is_anchor INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (code)
);
CREATE INDEX ix_core_currencies_code ON core_currencies (code);

CREATE TABLE core_exchange_rates (
    id CHAR(32) NOT NULL,
    from_currency CHAR(32) NOT NULL,
    to_currency CHAR(32) NOT NULL,
    rate REAL NOT NULL,
    effective_date TEXT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (from_currency) REFERENCES core_currencies (id),
    FOREIGN KEY (to_currency) REFERENCES core_currencies (id)
);
CREATE INDEX ix_core_exchange_rates_pair ON core_exchange_rates (from_currency, to_currency, effective_date);

INSERT INTO core_currencies (id, code, name, symbol, is_anchor) VALUES
 (lower(hex(randomblob(16))), 'YER', 'ريال يمني', '﷼', 1),
 (lower(hex(randomblob(16))), 'USD', 'دولار أمريكي', '$', 0);
