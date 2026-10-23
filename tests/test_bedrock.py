import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('extra,accepted', [
    ({'reasoningContent': {'redactedContent': b'opaque-test-block'}}, True),
    ({'toolUse': {'name': 'unapproved'}}, False),
    ({'text': 'unexpected extra answer'}, False),
])
def test_final_text_with_reasoning_or_unexpected_blocks(extra, accepted):
    Adapter, Gate, Settings, Error = adapter_api()
    answer = '{"evidence_ids":["prediction"]}'
    class Client:
        def converse(self, **kwargs):
            return {'output': {'message': {'content': [extra, {'text': answer}]}}}
    adapter = Adapter(Settings(model_id='test', max_attempts=1), client=Client(),
                      gate=Gate(clock=lambda: 0, sleep=lambda _: None))
    if accepted:
        assert adapter.generate({}) == answer
    else:
        with pytest.raises(Error):
            adapter.generate({})


def adapter_api():
    assert Path('src/bedrock.py').exists(), 'Bedrock adapter is not implemented'
    from src.bedrock import BedrockExplainer, RequestGate, BedrockSettings, InferenceUnavailable
    return BedrockExplainer, RequestGate, BedrockSettings, InferenceUnavailable


def test_rate_limit_retry_and_cache():
    Adapter, Gate, Settings, _ = adapter_api()
    clock = [0.0]
    starts = []
    def sleep(seconds):
        clock[0] += seconds
    class Client:
        def converse(self, **kwargs):
            assert 'temperature' not in kwargs['inferenceConfig'], 'Profile rejects temperature'
            starts.append(clock[0])
            if len(starts) == 1:
                raise TimeoutError()
            return {'output': {'message': {'content': [{'text': '{"evidence_ids":["e1"]}'}]}}}
    adapter = Adapter(Settings(model_id='configured-by-test'), client=Client(),
                      gate=Gate(clock=lambda: clock[0], sleep=sleep))
    assert json.loads(adapter.generate({'evidence': []}))['evidence_ids'] == ['e1']
    adapter.generate({'evidence': []})
    assert starts == [0.0, 2.0]


def test_outage_is_bounded_and_sanitized():
    Adapter, Gate, Settings, Error = adapter_api()
    class Client:
        calls = 0
        def converse(self, **kwargs):
            self.calls += 1
            raise TimeoutError('secret provider text')
    client = Client()
    adapter = Adapter(Settings(model_id='configured-by-test'), client=client,
                      gate=Gate(clock=lambda: 10, sleep=lambda _: None))
    with pytest.raises(Error, match='unavailable') as error:
        adapter.generate({})
    assert client.calls == 2
    assert 'secret' not in str(error.value)


def test_live_requires_explicit_config_and_region():
    _, _, Settings, _ = adapter_api()
    with pytest.raises(ValueError):
        Settings(model_id='')
    with pytest.raises(ValueError):
        Settings(model_id='configured-by-test', region='us-west-2')
    with pytest.raises(ValueError):
        Settings(model_id='configured-by-test', interval_seconds=0.5)


def test_two_adapters_share_gate_and_throttling_retries():
    Adapter, Gate, Settings, _ = adapter_api()
    clock = [0.0]
    starts = []
    def sleep(seconds):
        clock[0] += seconds
    class Throttled(Exception):
        response = {'Error': {'Code': 'ThrottlingException'}}
    class Client:
        def converse(self, **kwargs):
            starts.append(clock[0])
            if len(starts) == 1:
                raise Throttled()
            return {'output': {'message': {'content': [{'text':'{"evidence_ids":["e1"]}'}]}}}
    gate = Gate(clock=lambda: clock[0], sleep=sleep)
    first = Adapter(Settings(model_id='test'), client=Client(), gate=gate)
    second = Adapter(Settings(model_id='test'), client=Client(), gate=gate)
    first.generate({'one':1})
    second.generate({'two':2})
    assert starts == [0, 2, 4]


def test_queue_wait_is_bounded():
    Adapter, Gate, Settings, Error = adapter_api()
    gate = Gate()
    gate.lock.acquire()
    try:
        adapter = Adapter(Settings(model_id='test', queue_timeout=0.01), client=object(), gate=gate)
        with pytest.raises(Error, match='queue busy'):
            adapter.generate({})
    finally:
        gate.lock.release()


def test_live_configuration_failure_reports_actual_category(tmp_path, monkeypatch):
    adapter_api()
    from src.orchestrator import configured_provider, run_scenario
    monkeypatch.delenv('BEDROCK_SINGLE_PROCESS_ACK', raising=False)
    result = run_scenario('degrading', tmp_path / 'config.sqlite', mode='bedrock',
                          explainer=configured_provider('bedrock'))
    assert result.explanation.mode == 'fallback'
    assert 'configuration' in result.explanation.fallback_reason.lower()
