"""Transport failure semantics without requiring a broker in unit tests."""
import json
from types import SimpleNamespace
import pytest
from signalflow import stream

class Future:
    def get(self, timeout):
        return None

class Producer:
    def __init__(self): self.messages=[]
    def send(self, *args, **kwargs):
        self.messages.append((args,kwargs)); return Future()
    def close(self): pass

class Consumer:
    def __init__(self, messages): self.messages=messages; self.commits=0
    def __iter__(self): return iter(self.messages)
    def commit(self): self.commits+=1
    def close(self): pass

def message(value):
    return SimpleNamespace(value=value,partition=0,offset=42)

def configure(monkeypatch, engine, messages):
    consumer=Consumer(messages); output=Producer()
    monkeypatch.setattr(stream,'engine_for',lambda:engine)
    monkeypatch.setattr(stream,'KafkaConsumer',lambda *a,**kw:consumer)
    monkeypatch.setattr(stream,'producer',lambda:output)
    return consumer,output

def test_commit_after_processing(engine, intensity, monkeypatch):
    consumer,output=configure(monkeypatch,engine,[message(json.dumps(dict(kind='intensity',payload=intensity)).encode())])
    stream.consume()
    assert consumer.commits==1 and not output.messages

def test_database_failure_does_not_commit(engine, intensity, monkeypatch):
    consumer,_=configure(monkeypatch,engine,[message(json.dumps(dict(kind='intensity',payload=intensity)).encode())])
    def fail(*_): raise RuntimeError('db down')
    monkeypatch.setattr(stream,'process_event',fail)
    with pytest.raises(RuntimeError,match='db down'): stream.consume()
    assert consumer.commits==0

@pytest.mark.parametrize('payload',[b'not-json',b'{"kind":"intensity","payload":{"actual":NaN}}',None])
def test_bad_envelope_deadletter_before_commit(engine, monkeypatch, payload):
    consumer,output=configure(monkeypatch,engine,[message(payload)])
    stream.consume()
    assert consumer.commits==1 and output.messages[0][0][0]==stream.DLQ

def test_invalid_domain_event_quarantined(engine, intensity, monkeypatch):
    intensity['intensity']['actual']=-1
    consumer,output=configure(monkeypatch,engine,[message(json.dumps(dict(kind='intensity',payload=intensity)).encode())])
    stream.consume()
    assert consumer.commits==1 and output.messages[0][0][0]==stream.DLQ
