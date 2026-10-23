"""Local offline acceptance check. Requires playwright + Chromium (development only)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

Path('artifacts').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.goto('http://127.0.0.1:8502/AI4I_Baseline')
    page.get_by_role('button', name='Assess record', exact=True).wait_for(timeout=120000)
    page.get_by_role('button', name='Assess record', exact=True).click()
    frame = page.frame_locator('iframe').first
    frame.get_by_text('MODEL READY', exact=True).wait_for(timeout=60000)
    frame.get_by_role('button', name='Tool head').click()
    frame.get_by_text('Tool wear', exact=False).wait_for()
    page.wait_for_timeout(1000)
    page.locator('iframe').first.screenshot(path='artifacts/assembly.png')
    page.screenshot(path='artifacts/console-desktop.png', full_page=True)
    frame.get_by_role('button', name='Explode view').click()
    assert frame.get_by_role('button', name='Assemble').get_attribute('aria-pressed') == 'true'
    frame.get_by_role('button', name='Reset view').click()
    frame.get_by_role('heading', name='Machine overview').wait_for()
    drive = frame.get_by_role('button', name='Drive / spindle')
    drive.focus()
    drive.press('Enter')
    assert drive.get_attribute('aria-pressed') == 'true'
    page.emulate_media(reduced_motion='reduce')
    page.set_viewport_size({'width': 390, 'height': 844})
    frame.get_by_role('button', name='Process chamber').click()
    frame.get_by_text('Air temperature', exact=False).wait_for()
    page.screenshot(path='artifacts/console-mobile.png', full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    record = page.get_by_role('combobox').nth(1)
    record.fill('2016')
    page.get_by_role('option', name='2016', exact=True).click()
    page.get_by_role('button', name='Assess record', exact=True).click()
    page.get_by_role('heading', name='Technician review · simulated').wait_for(timeout=60000)
    page.get_by_role('textbox', name='Inspection note (simulation)').fill('Synthetic inspection recorded during browser verification.')
    page.get_by_role('button', name='Save simulated review', exact=True).click()
    page.get_by_text('Simulated review saved. No external action was performed.', exact=True).wait_for()
    assert not errors, errors
    print('PASS: loaded GLB, readings, explode, reset, reduced motion, mobile, flagged order, persisted review, no page errors')
    browser.close()
