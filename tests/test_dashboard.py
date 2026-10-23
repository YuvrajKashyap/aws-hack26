from pathlib import Path


def test_dashboard_replay_and_missing_sensor(tmp_path, monkeypatch):
    assert Path('app.py').exists(), 'Dashboard is not implemented'
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('DEMO_LEDGER_PATH', str(tmp_path / 'ui.sqlite'))
    app = AppTest.from_file('src/replay_page.py', default_timeout=20).run()
    assert not app.exception
    app.selectbox[0].select('degrading').run()
    app.button[0].click().run()
    assert not app.exception
    assert any('reserved' in x.value for x in app.success)
    app.button[0].click().run()
    assert not app.exception
    app.selectbox[0].select('missing-sensor').run()
    app.button[0].click().run()
    assert not app.exception
    assert any('review_required' in x.value for x in app.warning)


def test_chart_uses_utc_scale(tmp_path, monkeypatch):
    import json
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('DEMO_LEDGER_PATH', str(tmp_path / 'chart.sqlite'))
    app = AppTest.from_file('src/replay_page.py', default_timeout=20).run()
    app.button[0].click().run()
    chart = app.get('arrow_vega_lite_chart')[0]
    spec = json.loads(chart.proto.spec)
    assert spec['spec']['encoding']['x']['scale']['type'] == 'utc'
