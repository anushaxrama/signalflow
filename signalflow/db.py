import os
from pathlib import Path
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Float,
                        Integer, Text, Index, event, text)

metadata = MetaData()
observations = Table('observations', metadata,
    Column('start', String, primary_key=True), Column('end', String, nullable=False),
    Column('forecast', Float, nullable=False), Column('actual', Float),
    Column('index_label', String, nullable=False), Column('ingested_at', String, nullable=False),
    Column('event_id', String, nullable=False))
generation = Table('generation', metadata,
    Column('start', String, primary_key=True), Column('fuel', String, primary_key=True),
    Column('end', String, nullable=False), Column('percentage', Float, nullable=False),
    Column('ingested_at', String, nullable=False), Column('event_id', String, nullable=False))
raw_events = Table('raw_events', metadata,
    Column('id', String, primary_key=True), Column('kind', String, nullable=False),
    Column('payload', Text, nullable=False), Column('received_at', String, nullable=False),
    Column('status', String, nullable=False), Column('error', Text))
runs = Table('pipeline_runs', metadata,
    Column('id', String, primary_key=True), Column('started_at', String, nullable=False),
    Column('finished_at', String), Column('status', String, nullable=False),
    Column('fetched', Integer, nullable=False), Column('inserted', Integer, nullable=False),
    Column('rejected', Integer, nullable=False), Column('error', Text))
Index('generation_start_idx', generation.c.start)

def engine_for(url=None):
    url = url or os.getenv('DATABASE_URL', 'sqlite:///data/signalflow.db')
    if url.startswith('sqlite:///') and ':memory:' not in url:
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {}, pool_pre_ping=True)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def pragmas(connection, _):
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA foreign_keys=ON')
    if engine.dialect.name == 'postgresql':
        # API and workers may bootstrap together; serialize the v1 DDL transaction.
        with engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_xact_lock(73846201)'))
            metadata.create_all(conn)
    else:
        metadata.create_all(engine)
    return engine

def upsert(conn, table, values, keys):
    # Both supported stores provide atomic conflict handling; no select-then-insert race.
    if conn.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(table).values(**values)
    changes = {k: getattr(stmt.excluded, k) for k in values if k not in keys}
    conn.execute(stmt.on_conflict_do_update(index_elements=keys, set_=changes))
