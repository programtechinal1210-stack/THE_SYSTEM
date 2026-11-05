"""Internal fixed-table SQL helpers, always using the caller's Core transaction."""
from sqlalchemy import text

TABLES = {'inv_documents','inv_document_lines','inv_stock_ledger','inv_stock_balances',
          'inv_valuation_state','inv_outbox_events','inv_financial_controls','inv_warehouse_access',
          'inv_material_requests','inv_request_lines','inv_reservations','inv_custody_accounts',
          'inv_stocktakes','inv_stocktake_lines','inv_stocktake_scope_items'}


class PostingRepository:
    def __init__(self, session):
        self.session = session

    async def one(self, sql, **params):
        row = (await self.session.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None

    async def many(self, sql, **params):
        return [dict(r) for r in (await self.session.execute(text(sql), params)).mappings()]

    async def insert(self, table, values):
        if table not in TABLES:
            raise ValueError('Unsupported posting table')
        await self.session.execute(text(f'INSERT INTO {table} ({",".join(values)}) VALUES ({",".join(":"+k for k in values)})'), values)

    async def update(self, table, identifier, values):
        if table not in TABLES:
            raise ValueError('Unsupported posting table')
        await self.session.execute(text(f'UPDATE {table} SET {",".join(k+"=:"+k for k in values)} WHERE id=:identifier'),
                                   {**values, 'identifier': identifier})
