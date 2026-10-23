"""Shared notification outbox: simulated default, idempotent, retryable, dedupe,
accepted-vs-delivered, redacted errors, no arbitrary recipients, review-only text."""
import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.notifications import (NotificationOutbox, SNSPublisher, build_review_message)

IDENTITY = {"order_id": "SIM-WO-abc123", "record_id": "2016", "model_id": "AI4I-HYB-deadbeef",
            "policy": "Hybrid balance", "decision": "Review flagged", "score": 0.38,
            "threshold": 0.2, "evidence": ["torque 66 Nm raises risk", "tool wear 180 min"]}


class FakeSNS:
    def __init__(self):
        self.calls = []

    def publish(self, TopicArn, Subject, Message):
        self.calls.append((TopicArn, Subject, Message))
        return {"MessageId": "fake-msg-1"}


class FailingPublisher:
    def __init__(self):
        self.attempts = 0

    def publish(self, subject, body):
        self.attempts += 1
        if self.attempts < 2:
            raise TimeoutError("secret endpoint detail must not leak")
        return "msg-after-retry"


def test_default_is_simulated_no_send(tmp_path):
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)
    res = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                  recipients_display=["ops@example.com"])
    assert res.status == "simulated" and res.mode == "simulated"
    assert res.delivered is False
    assert res.provider_message_id is None


def test_idempotent_same_content_does_not_duplicate_or_resend(tmp_path):
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)
    a = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body, recipients_display=["x@e.com"])
    b = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body, recipients_display=["x@e.com"])
    assert a.notification_id == b.notification_id
    with sqlite3.connect(tmp_path / "n.sqlite") as con:
        assert con.execute("SELECT count(*) FROM notifications").fetchone()[0] == 1
        assert con.execute("SELECT attempts FROM notifications").fetchone()[0] == 1


def test_failed_send_is_retryable_then_accepted_not_delivered(tmp_path):
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)
    pub = FailingPublisher()
    first = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                    recipients_display=["x@e.com"], allow_live=True, publisher=pub)
    assert first.status == "failed" and first.mode == "sns"
    assert first.error_category == "TimeoutError"          # redacted category only
    assert "secret" not in json.dumps(first.__dict__)
    # Retry: same id, now accepted (SNS accepted the publish) but NOT delivered.
    second = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                     recipients_display=["x@e.com"], allow_live=True, publisher=pub)
    assert second.notification_id == first.notification_id
    assert second.status == "accepted"
    assert second.provider_message_id == "msg-after-retry"
    assert second.delivered is False                       # acceptance != delivery
    assert second.attempts == 2


def test_accepted_is_terminal_no_resend(tmp_path):
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)

    class OnePub:
        n = 0
        def publish(self, s, b):
            OnePub.n += 1
            return "m1"
    pub = OnePub()
    ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
            recipients_display=["x@e.com"], allow_live=True, publisher=pub)
    # Second call must not publish again.
    again = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                    recipients_display=["x@e.com"], allow_live=True, publisher=pub)
    assert again.status == "accepted"
    assert OnePub.n == 1


def test_concurrent_sends_dedupe_to_one_row(tmp_path):
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)

    def do(_):
        return ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                       recipients_display=["x@e.com"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(do, range(16)))
    assert len({r.notification_id for r in results}) == 1
    with sqlite3.connect(tmp_path / "n.sqlite") as con:
        assert con.execute("SELECT count(*) FROM notifications").fetchone()[0] == 1


def test_restart_reuses_persisted_record(tmp_path):
    db = tmp_path / "n.sqlite"
    subject, body = build_review_message(IDENTITY)
    first = NotificationOutbox(db).send(order_id=IDENTITY["order_id"], subject=subject,
                                        body=body, recipients_display=["x@e.com"])
    # Simulate a process restart: a fresh outbox object on the same file.
    reopened = NotificationOutbox(db).get(first.notification_id)
    assert reopened is not None and reopened.status == "simulated"


def test_offline_default_makes_no_network_even_with_topic_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIFY_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:topic")

    def forbidden(*a, **k):
        raise AssertionError("no network allowed in simulated send")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    ob = NotificationOutbox(tmp_path / "n.sqlite")
    subject, body = build_review_message(IDENTITY)
    # No allow_live / publisher -> simulated, no network, even though a topic env is set.
    res = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                  recipients_display=["x@e.com"])
    assert res.status == "simulated"


def test_sns_publisher_uses_topic_not_arbitrary_recipients():
    fake = FakeSNS()
    pub = SNSPublisher("arn:aws:sns:us-east-1:000000000000:ops", client=fake)
    msg_id = pub.publish("subj", "body")
    assert msg_id == "fake-msg-1"
    topic, subject, message = fake.calls[0]
    assert topic == "arn:aws:sns:us-east-1:000000000000:ops"
    # The publish targets the topic ARN; no arbitrary to-list is passed as a recipient.
    assert "ops@example.com" not in message


def test_sns_publisher_requires_topic():
    with pytest.raises(ValueError):
        SNSPublisher("", client=FakeSNS())


def test_review_message_is_review_only_no_deadline_or_approval_link():
    subject, body = build_review_message(IDENTITY)
    low = (subject + " " + body).lower()
    assert "simulated" in low and "review" in low
    for banned in ("deadline", "due by", "within 24", "approval_url", "{approval", "replace the",
                   "http://", "https://"):
        assert banned not in low
    # Identity is present.
    assert "SIM-WO-abc123" in body and "AI4I-HYB-deadbeef" in body


def test_blocked_publisher_concurrency_exactly_one_publish(tmp_path):
    """Two separate outbox instances on the same DB, two threads. The first claims
    the row and blocks inside publish; the second must see the in-flight `sending`
    row as terminal and NOT publish. Exactly one publish, not merely one DB row."""
    import threading
    db = tmp_path / "n.sqlite"
    NotificationOutbox(db)                     # create schema up front
    subject, body = build_review_message(IDENTITY)

    inside_publish = threading.Event()
    release = threading.Event()
    publish_count = {"n": 0}
    lock = threading.Lock()

    class BlockingPublisher:
        def publish(self, subj, bdy):
            with lock:
                publish_count["n"] += 1
            inside_publish.set()
            assert release.wait(timeout=5), "release not signalled"
            return "msg-1"

    pub = BlockingPublisher()
    results = {}

    def caller(name):
        ob = NotificationOutbox(db)            # distinct instance per 'process'
        results[name] = ob.send(order_id=IDENTITY["order_id"], subject=subject, body=body,
                                recipients_display=["ops (simulated)"], dedupe_key="unit|ALT-1|high",
                                allow_live=True, publisher=pub)

    a = threading.Thread(target=caller, args=("a",))
    a.start()
    assert inside_publish.wait(timeout=5), "first caller never entered publish"
    # First caller is now blocked inside publish with a committed 'sending' row.
    # Run the second caller to completion; it must not publish.
    caller("b")
    assert results["b"].status in ("sending", "simulated", "accepted")
    assert publish_count["n"] == 1             # second caller did NOT publish
    release.set()
    a.join(timeout=5)
    assert results["a"].status == "accepted"
    assert publish_count["n"] == 1             # still exactly one publish after release
    # Both callers reference the same notification identity.
    assert results["a"].notification_id == results["b"].notification_id


def test_semantic_dedupe_survives_changed_content_and_reopen(tmp_path):
    """A stable dedupe key dedupes two 'high' ticks whose subject/body/timestamp and
    score differ, even across a reopened outbox (restart). One notification, and with
    a counting publisher, exactly one publish."""
    db = tmp_path / "n.sqlite"
    key = "CRAC-3|ALT-CRAC-3-001|high"

    class CountingPub:
        n = 0
        def publish(self, s, b):
            CountingPub.n += 1
            return f"m{CountingPub.n}"
    pub = CountingPub()

    first = NotificationOutbox(db).send(
        order_id="SIM-WO-1", subject="[SIMULATED HIGH] tick 1",
        body="risk 0.70 at 14:00", recipients_display=["ops"], dedupe_key=key,
        allow_live=True, publisher=pub)
    assert first.status == "accepted"
    # Second tick: different order id, subject, body and score; reopened outbox.
    second = NotificationOutbox(db).send(
        order_id="SIM-WO-2", subject="[SIMULATED HIGH] tick 2",
        body="risk 0.83 at 14:10", recipients_display=["ops"], dedupe_key=key,
        allow_live=True, publisher=pub)
    assert second.notification_id == first.notification_id     # same stored notification
    assert second.subject == first.subject                     # first payload persisted
    assert CountingPub.n == 1                                   # exactly one publish
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT count(*) FROM notifications").fetchone()[0] == 1


def test_crash_sending_row_only_reclaimed_with_explicit_recover(tmp_path):
    """A 'sending' row (crash ambiguity) is terminal for automatic calls, and is only
    retried under explicit recover=True."""
    db = tmp_path / "n.sqlite"
    ob = NotificationOutbox(db)
    subj, body, recips = "s", "b", ["ops"]
    nid = NotificationOutbox.notification_id("SIM-WO-9", subj, body, recips)
    # Simulate a crash mid-send: this exact notification stuck in 'sending'.
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO notifications (notification_id,order_id,dedupe_key,status,mode,"
                    "delivered,provider_message_id,error_category,subject,recipients_display,"
                    "attempts,updated_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (nid, "SIM-WO-9", None, "sending", "pending", 0, None, None,
                     subj, json.dumps(recips), 1, 0.0))

    class Pub:
        n = 0
        def publish(self, s, b):
            Pub.n += 1
            return "m1"
    pub = Pub()
    # Automatic call must NOT reclaim the 'sending' row (returns it in-flight terminal).
    auto = ob.send(order_id="SIM-WO-9", subject=subj, body=body, recipients_display=recips,
                   allow_live=True, publisher=pub)
    assert auto.status == "sending" and Pub.n == 0
    # Explicit recovery is allowed and may publish (documented duplicate risk).
    recovered = ob.send(order_id="SIM-WO-9", subject=subj, body=body, recipients_display=recips,
                        allow_live=True, publisher=pub, recover=True)
    assert recovered.status == "accepted"
    assert Pub.n == 1
