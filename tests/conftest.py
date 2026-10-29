import os
import pytest
from signalflow.db import engine_for, metadata

@pytest.fixture
def engine(tmp_path):
    url = os.getenv('TEST_DATABASE_URL')
    if url and not url.endswith('/signalflow_test'):
        raise ValueError('Integration test database must be named signalflow_test')
    db = engine_for(url or ('sqlite:///' + str(tmp_path / 'test.db')))
    if url:
        metadata.drop_all(db)
        metadata.create_all(db)
    yield db
    db.dispose()

@pytest.fixture
def intensity():
    return {'from':'2026-10-01T00:00Z','to':'2026-10-01T00:30Z','intensity':{'forecast':100,'actual':110,'index':'moderate'}}

@pytest.fixture
def mix():
    return {'from':'2026-10-01T00:00Z','to':'2026-10-01T00:30Z','generationmix':[{'fuel':'wind','perc':40},{'fuel':'gas','perc':60}]}
