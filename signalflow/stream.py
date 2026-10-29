"""Optional Kafka transport. Commit offsets only after durable database processing."""
import json
import logging
import os
import time
from kafka import KafkaProducer, KafkaConsumer
from .db import engine_for
from .pipeline import collect, process_event, event_id

TOPIC = 'signalflow.grid.v1'
DLQ = 'signalflow.deadletter.v1'

def producer():
    return KafkaProducer(bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        acks='all', retries=5, max_in_flight_requests_per_connection=1,
        value_serializer=lambda v: json.dumps(v, allow_nan=False).encode(), key_serializer=lambda v: v.encode())

def produce(days=2):
    output = producer()
    try:
        for kind, payload in collect(days):
            output.send(TOPIC, key=kind + ':' + payload['from'], value=dict(kind=kind, payload=payload)).get(timeout=30)
    finally:
        output.flush(timeout=30)
        output.close()

def consume():
    engine = engine_for()
    stream = KafkaConsumer(TOPIC, bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        group_id='signalflow-materializer-v1', enable_auto_commit=False, auto_offset_reset='earliest',
        max_poll_records=1)
    dead = producer()
    try:
        for message in stream:
            try:
                def reject_constant(value):
                    raise ValueError('nonfinite JSON value: ' + value)
                event = json.loads(message.value, parse_constant=reject_constant)
                if not isinstance(event, dict) or 'kind' not in event or 'payload' not in event:
                    raise ValueError('invalid envelope')
                event_id(event['kind'], event['payload'])
            except (ValueError, TypeError, KeyError) as exc:
                dead.send(DLQ, key=str(message.offset), value=dict(error=str(exc), original=message.value.decode(errors='replace') if isinstance(message.value, bytes) else repr(message.value))).get(timeout=30)
                stream.commit()
                continue
            # Any database exception escapes without a commit; container restarts replay safely.
            result = process_event(engine, event['kind'], event['payload'])
            if result == 'rejected':
                dead.send(DLQ, key=event_id(event['kind'], event['payload']), value=event).get(timeout=30)
            stream.commit()
            logging.info('partition=%s offset=%s status=%s', message.partition, message.offset, result)
    finally:
        stream.close()
        dead.close()
        engine.dispose()
