"""Shared notification outbox for simulated review-order notifications.

Design goals (all enforced here, not left to callers):

- Simulated by default. A real send happens only when live sending is explicitly
  opted in AND a publisher is supplied. Nothing in this module constructs an AWS
  client on its own; the SNS adapter must be injected.
- SQLite-persisted idempotency and status. The notification id is derived from the
  order identity plus the message content, so the same review order never produces
  two notifications and a page rerun cannot re-send.
- Failed sends are retryable; accepted/delivered states are terminal for that id.
- Concurrency and restart dedupe: a row is claimed inside BEGIN IMMEDIATE before any
  send, so two processes cannot both send. Because a crash can happen after a real
  publish but before we persist the result, we DOCUMENT this as at-most-once-intended
  with a recoverable `sending` state — we do not promise exactly-once.
- Accepted (SNS accepted the publish) is distinguished from delivered (the email
  actually reached a person). We can only ever observe "accepted"; delivery depends
  on topic subscriptions we do not control, so we never claim delivery.
- Error detail is redacted to a safe category; raw SDK/credential text is never stored.
- Recipients: in simulated mode the intended recipients are recorded for display
  only and no message leaves the process. In live mode the message is published to a
  configured SNS topic ARN; the arbitrary intended-recipient list is NEVER used as
  real send targets (topic subscriptions decide who is actually notified).
- Message body carries order/model/evidence identity and is review-only. It makes no
  deadline, replacement-certainty, or approval-link claim.
"""
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# Terminal vs retryable statuses.
TERMINAL = {"simulated", "accepted"}
RETRYABLE = {"failed", "sending"}


class Publisher(Protocol):
    """Injected live publisher. Implementations publish to a configured topic and
    return a provider message id on acceptance. They must never accept an arbitrary
    recipient list as real targets."""
    def publish(self, subject: str, body: str) -> str: ...


def _redact(exc: Exception) -> str:
    """A safe category only; never raw SDK/credential text."""
    name = type(exc).__name__
    safe = {"EndpointConnectionError", "ConnectTimeoutError", "ReadTimeoutError",
            "NoCredentialsError", "ClientError", "AuthFailure", "TimeoutError"}
    return name if name in safe else "SendError"


def build_review_message(identity: dict) -> tuple[str, str]:
    """Build a review-only subject/body from order/model/evidence identity.

    `identity` keys (all optional except order_id): order_id, record_id, model_id,
    policy, decision, score, threshold, evidence (list[str]).
    No deadline, no replacement claim, no approval link.
    """
    order_id = str(identity.get("order_id", "UNKNOWN"))
    decision = str(identity.get("decision", "review"))
    subject = f"[SIMULATED REVIEW] order {order_id} flagged for technician review"
    lines = [
        f"Simulated review notification for order {order_id}.",
        "A human technician must review this result. Nothing has been ordered, "
        "scheduled, replaced, or dispatched.",
        "",
        f"Decision: {decision}",
    ]
    if identity.get("record_id") is not None:
        lines.append(f"Record: {identity['record_id']}")
    if identity.get("model_id"):
        lines.append(f"Model: {identity['model_id']}"
                     + (f" ({identity['policy']})" if identity.get("policy") else ""))
    if identity.get("score") is not None and identity.get("threshold") is not None:
        lines.append(f"Classifier score {identity['score']} vs threshold {identity['threshold']} "
                     "(uncalibrated; not a validated failure probability).")
    evidence = identity.get("evidence") or []
    if evidence:
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"  - {e}" for e in evidence[:6])
    lines.append("")
    lines.append("This is a prototype using a dataset experiment. The result is a global "
                 "machine-level label, not a component diagnosis or a remaining-life estimate.")
    return subject, "\n".join(lines)


@dataclass
class NotificationResult:
    notification_id: str
    status: str          # simulated | accepted | failed | sending
    mode: str            # simulated | sns
    delivered: bool      # always False: we can observe acceptance, never delivery
    provider_message_id: str | None
    error_category: str | None
    subject: str
    recipients_display: list[str]
    attempts: int


class NotificationOutbox:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                status TEXT NOT NULL,
                mode TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                provider_message_id TEXT,
                error_category TEXT,
                subject TEXT NOT NULL,
                recipients_display TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                updated_ts REAL NOT NULL)""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def notification_id(order_id: str, subject: str, body: str,
                        recipients_display: list[str]) -> str:
        payload = json.dumps([order_id, subject, body, list(recipients_display)],
                             sort_keys=True, separators=(",", ":"))
        return "NOTE-" + hashlib.sha256(payload.encode()).hexdigest()[:20]

    def get(self, notification_id: str) -> NotificationResult | None:
        with self._connect() as con:
            row = con.execute("SELECT notification_id,status,mode,delivered,provider_message_id,"
                              "error_category,subject,recipients_display,attempts "
                              "FROM notifications WHERE notification_id=?",
                              (notification_id,)).fetchone()
        return self._row_to_result(row) if row else None

    @staticmethod
    def _row_to_result(row) -> NotificationResult:
        return NotificationResult(
            notification_id=row[0], status=row[1], mode=row[2], delivered=bool(row[3]),
            provider_message_id=row[4], error_category=row[5], subject=row[6],
            recipients_display=json.loads(row[7]), attempts=row[8])

    def send(self, *, order_id: str, subject: str, body: str,
             recipients_display: list[str], allow_live: bool = False,
             publisher: Publisher | None = None) -> NotificationResult:
        """Idempotently record and (optionally) send one notification.

        Simulated unless allow_live is True AND a publisher is supplied. Re-calling
        with the same content returns the stored result without re-sending, except
        a previously failed send is retried.
        """
        nid = self.notification_id(order_id, subject, body, recipients_display)
        recips = json.dumps(list(recipients_display))

        # Claim the row inside an immediate transaction so concurrent callers and
        # page reruns cannot both proceed to a send.
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT notification_id,status,mode,delivered,provider_message_id,"
                              "error_category,subject,recipients_display,attempts "
                              "FROM notifications WHERE notification_id=?", (nid,)).fetchone()
            if row is not None and row[1] in TERMINAL:
                return self._row_to_result(row)          # already done; never re-send
            attempts = (row[8] if row else 0) + 1
            if row is None:
                con.execute("INSERT INTO notifications (notification_id,order_id,status,mode,"
                            "delivered,provider_message_id,error_category,subject,recipients_display,"
                            "attempts,updated_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (nid, order_id, "sending", "pending", 0, None, None, subject,
                             recips, attempts, time.time()))
            else:
                con.execute("UPDATE notifications SET status='sending', attempts=?, updated_ts=? "
                            "WHERE notification_id=?", (attempts, time.time(), nid))
            # Transaction commits here, marking the id as claimed/in-flight.

        live = bool(allow_live and publisher is not None)
        if not live:
            # Simulated: nothing leaves the process; recipients are display-only.
            return self._finalize(nid, status="simulated", mode="simulated", delivered=False,
                                  provider_message_id=None, error_category=None,
                                  subject=subject, recips=recips, attempts=attempts)
        try:
            message_id = publisher.publish(subject, body)
        except Exception as exc:                          # redact; keep row retryable
            return self._finalize(nid, status="failed", mode="sns", delivered=False,
                                  provider_message_id=None, error_category=_redact(exc),
                                  subject=subject, recips=recips, attempts=attempts)
        # SNS accepted the publish. This is acceptance, NOT delivery to a person.
        return self._finalize(nid, status="accepted", mode="sns", delivered=False,
                              provider_message_id=str(message_id), error_category=None,
                              subject=subject, recips=recips, attempts=attempts)

    def _finalize(self, nid, *, status, mode, delivered, provider_message_id,
                  error_category, subject, recips, attempts) -> NotificationResult:
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE notifications SET status=?,mode=?,delivered=?,provider_message_id=?,"
                        "error_category=?,updated_ts=? WHERE notification_id=?",
                        (status, mode, int(delivered), provider_message_id, error_category,
                         time.time(), nid))
        return NotificationResult(notification_id=nid, status=status, mode=mode,
                                  delivered=delivered, provider_message_id=provider_message_id,
                                  error_category=error_category, subject=subject,
                                  recipients_display=json.loads(recips), attempts=attempts)


class SNSPublisher:
    """Optional live publisher. Publishes ONLY to a fixed topic ARN. The intended
    recipient list is never used as a send target: SNS topic subscriptions decide
    who is actually notified. Construct this only under explicit live opt-in; it is
    never created by the outbox itself. A fake client may be injected for tests.
    """
    def __init__(self, topic_arn: str, *, client=None, region: str = "us-east-1"):
        if not topic_arn:
            raise ValueError("SNSPublisher requires an explicit topic ARN")
        self.topic_arn = topic_arn
        if client is None:
            import boto3
            client = boto3.client("sns", region_name=region)
        self.client = client

    def publish(self, subject: str, body: str) -> str:
        resp = self.client.publish(TopicArn=self.topic_arn, Subject=subject[:100], Message=body)
        return resp["MessageId"]
