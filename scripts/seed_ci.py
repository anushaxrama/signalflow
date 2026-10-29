"""Deterministic warehouse fixture, used only in CI; never used by the dashboard."""
from signalflow.db import engine_for
from signalflow.pipeline import ingest

engine = engine_for()
ingest(engine, events=[
    ('intensity', {'from':'2026-01-01T00:00Z','to':'2026-01-01T00:30Z','intensity':{'forecast':100,'actual':110,'index':'moderate'}}),
    ('generation', {'from':'2026-01-01T00:00Z','to':'2026-01-01T00:30Z','generationmix':[{'fuel':'wind','perc':40},{'fuel':'gas','perc':60}]})
])
