"""NOTHING BLOCKS THE BRUSH: paint stays off the event loop, the queue
carries UI epilogues, and the spend meter counts every image."""
import asyncio
import json
import os
from types import SimpleNamespace

import pytest


def test_imaging_tools_stay_registered_and_threaded():
    """The async wrappers kept their tool schemas; every heavy tool has a
    sync twin that runs in a worker thread."""
    from agentic.tools import imaging as im
    for name in ['generate_panel_image', 'generate_cover_image',
                 'generate_setting_background',
                 'create_styled_image_for_character_variant',
                 'split_layer', 'generate_insert_art',
                 'generate_character_exemplar', 'export_issue_pdf',
                 'export_issue_cbz', 'stitch_issue_pages']:
        tool = getattr(im, name)
        assert hasattr(tool, 'params_json_schema'), f'{name} lost its tool schema'
        assert getattr(im, f'_{name}_sync', None) is not None, f'{name} has no sync twin'
    props = im.generate_panel_image.params_json_schema.get('properties', {})
    assert 'panel_id' in props and 'takes' in props, 'panel tool schema kept its params'


@pytest.mark.asyncio
async def test_render_queue_epilogue_runs_on_the_loop(tmp_path, monkeypatch):
    import helpers.render_queue as rq
    monkeypatch.setattr(rq, 'QUEUE_DIR', str(tmp_path / '.queue'))
    state = SimpleNamespace(refresh_details=lambda: None)
    got, loop_ok = [], []
    main_loop = asyncio.get_running_loop()

    def after(result):
        got.append(result)
        loop_ok.append(asyncio.get_running_loop() is main_loop)
    task = rq.enqueue_renders(state, [("a paint job", lambda: "ok note", after)])
    await task
    assert got == ["ok note"]
    assert loop_ok == [True], "the epilogue must run back on the event loop"
    assert not any(f.endswith('.json') for f in os.listdir(str(tmp_path / '.queue'))), \
        "the slip is burned when the job lands"


def test_spend_counts_every_image(tmp_path, monkeypatch):
    import helpers.generator as g
    monkeypatch.setattr(g, 'SPEND_LEDGER', str(tmp_path / '.spend.json'))
    g.record_spend('high', images=4)
    g.record_spend('high')
    n, cost = g.spend_today()
    assert n == 5, "a four-take heal counts four images, not one call"
    assert abs(cost - 5 * g.EST_COST['high']) < 1e-9
