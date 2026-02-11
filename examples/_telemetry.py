# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""NDJSON telemetry for CKVD examples.

Machine-readable structured event logging for AI agent consumption.
Uses a custom lean NDJSON sink (not loguru serialize=True) to produce
compact records without bloat fields (module, name, process, thread).

Architecture:
    - Uses a resilient sink strategy to survive CKVD's logger.remove() calls.
    - CKVD's loguru_setup.py calls logger.remove() during CryptoKlineVisionData.create(),
      which destroys any previously added sinks. This module works around that by
      checking sink presence and re-adding before every emit.
    - Returns a ResilientLogger wrapper that auto-heals destroyed sinks on every call.
    - Uses opt(depth=1) for correct caller attribution (shows actual caller, not wrapper).
    - Binds provenance context (version, git_sha, trace_id) to every log event.
Usage:
    from _telemetry import init_telemetry, timed_span

    tlog = init_telemetry("example_name")
    tlog.bind(event_type="fetch_started", symbol="BTCUSDT").info("Fetching data")

    with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1h"):
        df = manager.get_data(...)

Schema contract: See examples/CLAUDE.md for the full NDJSON schema (v2).
"""

import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

from loguru import logger as _loguru_logger

# --- Output paths (anchored to script location, not cwd) ---
_EXAMPLES_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _EXAMPLES_DIR.parent  # used by _ndjson_sink for relative paths
NDJSON_DIR = _EXAMPLES_DIR / "logs"
NDJSON_FILE = NDJSON_DIR / "events.jsonl"
SERVICE_NAME = "ckvd-examples"

# Console format: minimal text for human watchers
_CONSOLE_FORMAT = "{time:HH:mm:ss} | {level: <8} | {message}"


# --- Provenance (resolved once at import time) ---
def _get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def _get_version() -> str:
    try:
        from ckvd import __version__

        return __version__
    except ImportError:
        return "unknown"


_GIT_SHA = _get_git_sha()
_VERSION = _get_version()
_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
_PLATFORM = f"{platform.system().lower()}-{platform.machine()}"

# --- Sink management ---
# CKVD's loguru_setup.py calls logger.remove() during CryptoKlineVisionData.create(),
# which destroys all sinks including ours. We track our sink IDs and re-add them
# whenever they go missing.
_ndjson_sink_id: int | None = None
_console_sink_id: int | None = None
_console_level: str = "INFO"


def _example_filter(record):
    """Filter: only pass records from example telemetry (not CKVD internal logs)."""
    return "service" in record["extra"]


# --- Custom lean NDJSON sink ---
def _ndjson_sink(message):
    """Custom lean NDJSON sink callable for loguru.

    Produces flat records with only useful fields:
    - ts, level, msg, file, function, line (from loguru record)
    - All extra fields merged at top level (service, trace_id, event_type, etc.)
    - exception info when present

    Strips bloat: module, name, process, thread, elapsed, level.icon, level.no.
    File paths are made relative to the project root for portability.
    """
    record = message.record
    entry = {
        "ts": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": record["level"].name,
        "msg": record["message"],
    }

    # Relative file path for portability (strip absolute prefix to project root)
    file_path = Path(record["file"].path)
    try:
        entry["file"] = str(file_path.relative_to(_PROJECT_ROOT))
    except ValueError:
        entry["file"] = record["file"].name

    entry["function"] = record["function"]
    entry["line"] = record["line"]

    # Merge all extra fields at top level (service, trace_id, event_type, etc.)
    entry.update(record["extra"])

    # Include exception info when present
    if record["exception"] is not None:
        exc = record["exception"]
        entry["exception"] = {
            "type": exc.type.__name__ if exc.type else None,
            "value": str(exc.value) if exc.value else None,
        }

    NDJSON_DIR.mkdir(parents=True, exist_ok=True)
    with open(NDJSON_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _ensure_sinks():
    """Re-add NDJSON and console sinks if CKVD's logger.remove() destroyed them.

    Loguru's internal _core.handlers dict tracks active sink IDs. If our IDs
    are no longer present, the sinks were removed and need to be re-added.
    """
    global _ndjson_sink_id, _console_sink_id

    handlers = _loguru_logger._core.handlers

    # Re-add NDJSON file sink if missing (custom lean sink, not serialize=True)
    if _ndjson_sink_id is None or _ndjson_sink_id not in handlers:
        _ndjson_sink_id = _loguru_logger.add(
            _ndjson_sink,
            level="DEBUG",
            filter=_example_filter,
        )

    # Re-add console text sink if missing
    if _console_sink_id is None or _console_sink_id not in handlers:
        _console_sink_id = _loguru_logger.add(
            sys.stderr,
            format=_CONSOLE_FORMAT,
            level=_console_level,
            colorize=True,
            filter=_example_filter,
        )


class ResilientLogger:
    """Logger wrapper that re-adds sinks before every emit.

    CKVD's loguru_setup.py calls logger.remove() which destroys our sinks.
    This wrapper ensures sinks are always present when logging.
    Uses opt(depth=1) for correct caller attribution.
    """

    def __init__(self, bound_logger):
        self._logger = bound_logger

    def bind(self, **kwargs):
        """Return a new ResilientLogger with additional bindings."""
        return ResilientLogger(self._logger.bind(**kwargs))

    def info(self, msg):
        _ensure_sinks()
        self._logger.opt(depth=1).info(msg)

    def warning(self, msg):
        _ensure_sinks()
        self._logger.opt(depth=1).warning(msg)

    def error(self, msg):
        _ensure_sinks()
        self._logger.opt(depth=1).error(msg)

    def debug(self, msg):
        _ensure_sinks()
        self._logger.opt(depth=1).debug(msg)


def generate_trace_id() -> str:
    """Generate 16-char hex correlation ID for trace grouping."""
    return uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate 8-char hex span ID."""
    return uuid.uuid4().hex[:8]


def init_telemetry(example_name: str, *, console_level: str = "INFO"):
    """Initialize NDJSON telemetry for an example.

    Adds an NDJSON file sink and a console text sink to loguru. Sinks are
    automatically re-added if CKVD's logger.remove() destroys them.

    Returns a ResilientLogger that ensures sinks survive CKVD initialization.

    Args:
        example_name: Short identifier for this example (e.g., "quick_start").
        console_level: Minimum level for console output. Default "INFO".

    Returns:
        A ResilientLogger with provenance fields bound to every message.
    """
    global _console_level
    _console_level = console_level

    # Add sinks (or re-add if destroyed)
    _ensure_sinks()

    # Generate trace_id for this run
    trace_id = generate_trace_id()

    # Bind provenance context to all subsequent log calls
    bound = _loguru_logger.bind(
        service=SERVICE_NAME,
        version=_VERSION,
        git_sha=_GIT_SHA,
        python=_PYTHON,
        platform=_PLATFORM,
        trace_id=trace_id,
        example=example_name,
    )

    tlog = ResilientLogger(bound)

    # Emit session_started event
    tlog.bind(event_type="session_started").info(f"Session started: {example_name}")

    # py-spy profiling hint (feature-flagged, no hard dependency)
    if os.environ.get("CKVD_PYSPY_PROFILE", "").lower() in ("true", "1", "yes"):
        pid = os.getpid()
        tlog.bind(
            event_type="profiling_hint",
            pid=pid,
            pyspy_command=f"py-spy record -o profile.svg --pid {pid}",
        ).info(f"py-spy profiling enabled, PID={pid}")

    return tlog


class timed_span:
    """Context manager that emits start/completed/failed events with timing.

    Usage:
        with timed_span(tlog, "fetch", symbol="BTCUSDT"):
            df = manager.get_data(...)

    Emits:
        - fetch_started  (on __enter__)
        - fetch_completed with latency_ms (on success)
        - fetch_failed with error, error_type, latency_ms (on exception)
    """

    def __init__(self, tlog, event_type: str, **extra):
        self.tlog = tlog
        self.event_type = event_type
        self.extra = extra
        self.span_id = generate_span_id()
        self.start: float = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        self.tlog.bind(
            event_type=f"{self.event_type}_started",
            span_id=self.span_id,
            **self.extra,
        ).info(f"{self.event_type} started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self.start) * 1000
        if exc_type is None:
            self.tlog.bind(
                event_type=f"{self.event_type}_completed",
                span_id=self.span_id,
                latency_ms=round(elapsed_ms, 2),
                **self.extra,
            ).info(f"{self.event_type} completed in {elapsed_ms:.1f}ms")
        else:
            self.tlog.bind(
                event_type=f"{self.event_type}_failed",
                span_id=self.span_id,
                latency_ms=round(elapsed_ms, 2),
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.extra,
            ).error(f"{self.event_type} failed: {exc_val}")
        return False  # Don't suppress exceptions
