"""SQLite-only simulator: atomic reservation, unique replay key, no real actions."""
import hashlib
import sqlite3
from pathlib import Path
from .contracts import MaintenanceProposal, WorkOrder
from .maintenance import PART, REFERENCE, SLOT


class Ledger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute('CREATE TABLE IF NOT EXISTS inventory (part_id TEXT PRIMARY KEY, quantity INTEGER NOT NULL CHECK(quantity >= 0))')
            con.execute('CREATE TABLE IF NOT EXISTS slots (slot TEXT PRIMARY KEY, order_id TEXT UNIQUE)')
            con.execute('CREATE TABLE IF NOT EXISTS orders (idempotency_key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            con.execute('INSERT OR IGNORE INTO inventory VALUES (?, 2)', (PART,))
            con.execute('INSERT OR IGNORE INTO slots VALUES (?, NULL)', (SLOT,))

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def simulate(self, proposal: MaintenanceProposal) -> WorkOrder | None:
        proposal = MaintenanceProposal.model_validate(proposal.model_dump())
        if proposal.action == 'none':
            return None
        key = hashlib.sha256(f'{proposal.asset_id}|{proposal.assessment_id}|{proposal.action_version}'.encode()).hexdigest()
        order_id = f'SIM-WO-{key[:12]}'
        valid = (not proposal.review_required and proposal.action == 'inspect_bearing'
            and proposal.asset_id == 'SIM-PRESS-01' and proposal.part_id == PART
            and proposal.manual_reference == REFERENCE and proposal.duration_minutes == 60
            and proposal.candidate_slot == SLOT)
        if not valid and not (proposal.review_required and proposal.action == 'review'):
            # Malformed proposals must not consume resources or poison a valid replay key.
            return WorkOrder(order_id=order_id, idempotency_key=key, status='review_required',
                reason='Unsupported simulation proposal rejected; nothing reserved or persisted.', proposal=proposal)
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute('SELECT payload FROM orders WHERE idempotency_key=?', (key,)).fetchone()
            if existing:
                return WorkOrder.model_validate_json(existing[0])
            stock = con.execute('SELECT quantity FROM inventory WHERE part_id=?', (proposal.part_id,)).fetchone()
            slot = con.execute('SELECT order_id FROM slots WHERE slot=?', (proposal.candidate_slot,)).fetchone()
            available = valid and stock is not None and stock[0] > 0 and slot is not None and slot[0] is None
            status = 'reserved' if available else 'review_required'
            reason = proposal.reason if available or proposal.review_required else 'Simulation policy or resource conflict; nothing reserved.'
            if available:
                con.execute('UPDATE inventory SET quantity=quantity-1 WHERE part_id=?', (proposal.part_id,))
                con.execute('UPDATE slots SET order_id=? WHERE slot=?', (order_id, proposal.candidate_slot))
            order = WorkOrder(order_id=order_id, idempotency_key=key, status=status, reason=reason, proposal=proposal)
            con.execute('INSERT INTO orders VALUES (?, ?)', (key, order.model_dump_json()))
            return order
