import argparse
import json
import logging
import os
import signal
import time
from .db import engine_for
from .pipeline import ingest

log = logging.getLogger('signalflow')

def main():
    parser = argparse.ArgumentParser(description='SignalFlow pipeline operations')
    parser.add_argument('command', choices=['ingest', 'worker', 'serve', 'produce', 'consume', 'check'])
    parser.add_argument('--days', type=int, default=2)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.command == 'serve':
        import uvicorn
        uvicorn.run('signalflow.api:app', host=args.host, port=args.port)
        return
    if args.command in ('produce', 'consume'):
        from .stream import produce, consume
        return produce(args.days) if args.command == 'produce' else consume()
    engine = engine_for()
    if args.command == 'ingest':
        print(json.dumps(ingest(engine, args.days)))
    elif args.command == 'check':
        from .analytics import snapshot
        data = snapshot(engine)
        print(json.dumps(dict(status=data['status'], metrics=data['metrics']), indent=2))
        if data['status'] != 'healthy':
            raise SystemExit(1)
    else:
        interval = int(os.getenv('POLL_SECONDS', '300'))
        if interval < 60:
            parser.error('POLL_SECONDS must be at least 60')
        stopped = False
        def stop(*_):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while not stopped:
            try:
                log.info(json.dumps(ingest(engine, args.days)))
            except Exception:
                log.exception('ingestion failed; retrying next cycle')
            for _ in range(interval):
                if stopped:
                    break
                time.sleep(1)

if __name__ == '__main__':
    main()
