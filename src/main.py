import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.config import load_config
from src.monitor import HealthMonitor
from src.models import SystemOverview

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("OpsPulse.App")

# Load configuration and initialize monitor
config = load_config()
monitor = HealthMonitor(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start probe loop
    logger.info("Starting OpsPulse Sentinel Service...")
    monitor.start()
    yield
    # Shutdown: Stop probe loop
    logger.info("Stopping OpsPulse Sentinel Service...")
    monitor.stop()


app = FastAPI(
    title="OpsPulse Sentinel",
    description="Automated Microservice Health & Uptime Sentinel with Prometheus Metrics and Alerting",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz", summary="Liveness & Readiness probe for Kubernetes/Docker")
async def health_check():
    """Returns 200 OK if OpsPulse itself is alive and running."""
    return {"status": "ok", "service": "OpsPulse Sentinel", "version": "1.0.0"}


@app.get("/api/v1/overview", response_model=SystemOverview, summary="System health overview")
async def get_overview():
    """Returns aggregated status of all monitored services."""
    return monitor.get_overview()


@app.get("/api/v1/targets", summary="Detailed target statuses")
async def get_targets():
    """Returns list of all target statuses and SLA uptime percentages."""
    return list(monitor.statuses.values())


@app.post("/api/v1/probe", summary="Trigger manual probe cycle")
async def trigger_probe():
    """Force an immediate health check across all targets."""
    results = await monitor.run_probe_cycle()
    return {"message": "Probe cycle completed", "results_count": len(results)}


@app.get("/metrics", summary="Prometheus metrics endpoint")
async def metrics():
    """Exposes standard Prometheus scrape format metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", response_class=HTMLResponse, summary="DevOps Web Dashboard")
async def web_dashboard():
    """Simple, sleek visual dashboard for quick status inspection."""
    overview = monitor.get_overview()
    rows_html = ""
    for item in overview.targets:
        state_color = {
            "HEALTHY": "#10b981",
            "DEGRADED": "#f59e0b",
            "DOWN": "#ef4444",
            "UNKNOWN": "#6b7280"
        }.get(item.current_state.value, "#6b7280")

        latency_display = f"{item.last_latency_ms:.1f} ms" if item.last_latency_ms is not None else "N/A"
        checked_display = item.last_checked_at.strftime("%H:%M:%S UTC") if item.last_checked_at else "Pending"
        error_display = f"<br><small style='color:#ef4444'>{item.last_error}</small>" if item.last_error else ""

        badge_style = f"background:{state_color}; color:white; padding:4px 10px; border-radius:12px; font-weight:bold;"
        rows_html += f"""
        <tr>
            <td><strong>{item.target.name}</strong><br><small style="color:#9ca3af">{item.target.url}</small></td>
            <td><span style="{badge_style} font-size:12px;">{item.current_state.value}</span></td>
            <td>{item.uptime_percentage:.1f}%</td>
            <td>{latency_display}</td>
            <td>{checked_display}{error_display}</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="10">
        <title>OpsPulse - DevOps Uptime Sentinel</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #0f172a;
                color: #f8fafc;
                margin: 0;
                padding: 24px;
            }}
            .container {{ max-width: 900px; margin: 0 auto; }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid #334155;
                padding-bottom: 16px;
                margin-bottom: 24px;
            }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
            .card {{ background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }}
            .card-title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; margin-bottom: 8px; }}
            .card-value {{ font-size: 28px; font-weight: bold; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: #1e293b;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #334155;
            }}
            th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
            th {{ background: #111827; font-size: 13px; color: #94a3b8; text-transform: uppercase; }}
            .badge-healthy {{ color: #10b981; }}
            .badge-degraded {{ color: #f59e0b; }}
            .badge-down {{ color: #ef4444; }}
            .footer {{ margin-top: 24px; font-size: 12px; color: #64748b; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1 style="margin:0; font-size:24px;">⚡ OpsPulse Sentinel</h1>
                    <small style="color:#94a3b8">Continuous Microservice Health & SLA Monitor</small>
                </div>
                <div>
                    <a href="/metrics" style="color:#38bdf8; text-decoration:none; margin-right:12px;">
                        📊 Prometheus Metrics
                    </a>
                    <a href="/docs" style="color:#38bdf8; text-decoration:none;">📖 API Docs</a>
                </div>
            </div>

            <div class="stats-grid">
                <div class="card">
                    <div class="card-title">Total Targets</div>
                    <div class="card-value">{overview.monitored_targets_count}</div>
                </div>
                <div class="card">
                    <div class="card-title">Healthy</div>
                    <div class="card-value badge-healthy">{overview.healthy_count}</div>
                </div>
                <div class="card">
                    <div class="card-title">Degraded</div>
                    <div class="card-value badge-degraded">{overview.degraded_count}</div>
                </div>
                <div class="card">
                    <div class="card-title">Down</div>
                    <div class="card-value badge-down">{overview.down_count}</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Target Service</th>
                        <th>Status</th>
                        <th>Uptime SLA</th>
                        <th>Latency</th>
                        <th>Last Check</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="5" style="text-align:center;">No targets.</td></tr>'}
                </tbody>
            </table>

            <div class="footer">
                Auto-refreshes every 10 seconds &bull; OpsPulse v1.0.0 &bull; DevOps Microservice Health Engine
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
