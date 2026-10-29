import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from .db import engine_for
from .analytics import snapshot, scenario

STATIC = Path(__file__).parent / 'static'

def create_app(engine=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine if engine is not None else engine_for()
        yield
        if engine is None:
            app.state.engine.dispose()
    app = FastAPI(title='SignalFlow API', version='1.0.0', description='Observed Great Britain grid signals and reproducible infrastructure scenarios.', lifespan=lifespan)
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.middleware('http')
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path in ('/docs', '/redoc', '/docs/oauth2-redirect'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; font-src https://fonts.gstatic.com; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
        return response

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/case-study', include_in_schema=False)
    def case_study():
        return FileResponse(STATIC / 'case-study.html')

    @app.get('/health')
    def health():
        try:
            with app.state.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return dict(status='ok', database='reachable')
        except Exception:
            return JSONResponse(status_code=503, content=dict(status='error', database='unreachable'))

    @app.get('/metrics', include_in_schema=False)
    def metrics():
        data = snapshot(app.state.engine)
        values = data['metrics']
        lines = [
            '# HELP signalflow_intervals Stored grid intervals',
            '# TYPE signalflow_intervals gauge',
            f"signalflow_intervals {values['total_intervals']}",
            '# HELP signalflow_rejected_events_total Quarantined unique source events',
            '# TYPE signalflow_rejected_events_total counter',
            f"signalflow_rejected_events_total {values['rejected_events']}",
            '# HELP signalflow_data_healthy Whether both datasets are current',
            '# TYPE signalflow_data_healthy gauge',
            f"signalflow_data_healthy {int(data['status'] == 'healthy')}",
        ]
        if values['freshness_seconds'] is not None:
            lines.extend(['# TYPE signalflow_interval_age_seconds gauge', f"signalflow_interval_age_seconds {values['freshness_seconds']}"])
        return Response('\n'.join(lines) + '\n', media_type='text/plain; version=0.0.4')

    @app.get('/api/overview')
    def overview(hours: int = Query(48, ge=6, le=720)):
        return snapshot(app.state.engine, hours)

    @app.get('/api/scenario')
    def estimate(power_kw: float = Query(100, ge=1, le=100000), duration_hours: float = Query(2, ge=0.5, le=24, multiple_of=0.5), pue: float = Query(1.2, ge=1, le=3)):
        return scenario(snapshot(app.state.engine, 168), power_kw, duration_hours, pue)

    @app.get('/api/export.csv')
    def export(hours: int = Query(48, ge=6, le=720)):
        stream = io.StringIO()
        columns = ['start', 'end', 'forecast', 'actual', 'index_label', 'ingested_at', 'event_id', 'anomaly']
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(snapshot(app.state.engine, hours)['series'])
        return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="signalflow-intervals.csv"'})
    return app

app = create_app()
