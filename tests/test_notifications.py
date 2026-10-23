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
