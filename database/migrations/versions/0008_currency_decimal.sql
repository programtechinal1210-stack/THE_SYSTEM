-- Preserve the legacy REAL column; exact decimal text is authoritative from now on.
-- Legacy binary precision cannot be recovered; CAST retains SQLite's decimal representation.
ALTER TABLE core_exchange_rates ADD COLUMN rate_decimal TEXT;
UPDATE core_exchange_rates SET rate_decimal = CAST(rate AS TEXT);
