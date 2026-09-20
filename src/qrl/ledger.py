"""SQLite ledger of every candidate tested during a search (Phase 2.3).

The ledger exists so a lucky winner can be told apart from a real one: every
variant tried, including failures, is recorded, and the total attempt count
feeds the deflated Sharpe check in a later milestone (see PLAN.md 2.3-2.5).

Storage is local and gitignored (`research/ledger.sqlite`); only the small,
deterministic `research/top_candidates.csv` export (see `scripts/export_ledger.py`)
is committed. Stdlib `sqlite3` only, foreign keys are turned on per connection,
and `PRAGMA user_version` records the schema version for future migrations.

Guardrails enforced here, not just documented:
- `record_test` refuses to log a test if the criteria hash differs from the
  hash the run started with (a run must judge every candidate by one fixed
  rulebook).
- `validation_events` has a UNIQUE constraint on `test_id`: a candidate may be
  honestly validated only once.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

DEFAULT_LEDGER_PATH = Path("research/ledger.sqlite")
SCHEMA_VERSION = 1

SEED_LANES = ("A", "B", "C")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    git_commit TEXT,
    criteria_hash TEXT NOT NULL,
    seed_lane TEXT NOT NULL CHECK (seed_lane IN ('A', 'B', 'C')),
    seed_description TEXT
);

CREATE TABLE IF NOT EXISTS tests (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    family TEXT NOT NULL,
    params_json TEXT NOT NULL,
    universe TEXT NOT NULL,
    period TEXT NOT NULL CHECK (period = 'research'),
    metrics_json TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    failure_reasons TEXT,
    candidate_key TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tests_run_id ON tests(run_id);
CREATE INDEX IF NOT EXISTS idx_tests_candidate_key ON tests(candidate_key);

CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    batch_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_events (
    test_id INTEGER PRIMARY KEY REFERENCES tests(test_id),
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS holdout_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    what_unsealed TEXT NOT NULL,
    git_commit TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Read queries exist in two complete, literal forms (all rows / filtered by a
# single run) rather than being assembled at runtime, so no SQL string is ever
# built from a variable (avoids bandit B608 and, more to the point, avoids
# hand-rolled SQL string-building altogether).
_SELECT_TESTS_ALL = "SELECT family, passed, failure_reasons FROM tests"
_SELECT_TESTS_BY_RUN = "SELECT family, passed, failure_reasons FROM tests WHERE run_id = ?"

_COUNT_VALIDATED_ALL = "SELECT COUNT(*) FROM validation_events v JOIN tests t USING (test_id)"
_COUNT_VALIDATED_BY_RUN = (
    "SELECT COUNT(*) FROM validation_events v JOIN tests t USING (test_id) WHERE t.run_id = ?"
)

_SELECT_CANDIDATES_ALL = (
    "SELECT test_id, run_id, family, params_json, universe, metrics_json, passed FROM tests"
)
_SELECT_CANDIDATES_BY_RUN = (
    "SELECT test_id, run_id, family, params_json, universe, metrics_json, passed "
    "FROM tests WHERE run_id = ?"
)


class LedgerError(RuntimeError):
    """Raised when a write would violate a ledger guardrail."""


def _dumps(payload: dict) -> str:
    """Serialize with sorted keys so identical candidates hash identically."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _require_rowid(cursor: sqlite3.Cursor) -> int:
    rowid = cursor.lastrowid
    if rowid is None:
        raise LedgerError("insert did not return a row id")
    return rowid


def candidate_key(family: str, params: dict, universe: str, period: str = "research") -> str:
    """Stable hash of a candidate's identity, used to detect repeats.

    Two calls with the same family/params/universe/period return the same key
    regardless of the params dict's key order.
    """
    payload = _dumps({"family": family, "params": params, "universe": universe, "period": period})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _read_packed_ref(git_dir: Path, ref: str) -> str | None:
    packed = git_dir / "packed-refs"
    if not packed.is_file():
        return None
    for line in packed.read_text().splitlines():
        if line.endswith(f" {ref}"):
            return line.split()[0]
    return None


def current_git_commit(repo_root: str | Path = ".") -> str | None:
    """Return the current commit hash by reading .git directly (no subprocess).

    Returns None if `repo_root` is not a git checkout or HEAD can't be read.
    """
    git_dir = Path(repo_root).resolve() / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        return None
    head = head_path.read_text().strip()
    if not head.startswith("ref:"):
        return head or None
    ref = head.split(":", 1)[1].strip()
    ref_path = git_dir / ref
    if ref_path.is_file():
        return ref_path.read_text().strip()
    return _read_packed_ref(git_dir, ref)


class Ledger:
    """A SQLite-backed record of every test run during a search.

    Usable as a context manager:

        with Ledger(path) as ledger:
            run_id = ledger.start_run(criteria_hash, "A", "trend_pullback variants")
            ...
    """

    def __init__(self, path: str | Path = DEFAULT_LEDGER_PATH) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        self._conn.executescript(_SCHEMA_SQL)
        if version == 0:
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # -- writers ---------------------------------------------------------

    def start_run(
        self,
        criteria_hash: str,
        seed_lane: str,
        seed_description: str | None = None,
        git_commit: str | None = None,
    ) -> int:
        commit = git_commit if git_commit is not None else current_git_commit()
        try:
            cur = self._conn.execute(
                "INSERT INTO runs (started_at, git_commit, criteria_hash, seed_lane, "
                "seed_description) VALUES (?, ?, ?, ?, ?)",
                (_utcnow(), commit, criteria_hash, seed_lane, seed_description),
            )
        except sqlite3.IntegrityError as err:
            raise LedgerError(str(err)) from err
        self._conn.commit()
        return _require_rowid(cur)

    def end_run(self, run_id: int) -> None:
        self._conn.execute("UPDATE runs SET ended_at = ? WHERE run_id = ?", (_utcnow(), run_id))
        self._conn.commit()

    def record_test(
        self,
        run_id: int,
        criteria_hash: str,
        family: str,
        params: dict,
        universe: str,
        metrics: dict,
        passed: bool,
        failure_reasons: str | None = None,
        period: str = "research",
    ) -> int:
        run_row = self._conn.execute(
            "SELECT criteria_hash FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if run_row is None:
            raise LedgerError(f"unknown run_id {run_id}")
        if run_row["criteria_hash"] != criteria_hash:
            raise LedgerError(
                f"criteria hash mismatch for run {run_id}: run started with "
                f"{run_row['criteria_hash']!r}, got {criteria_hash!r}"
            )
        key = candidate_key(family, params, universe, period)
        try:
            cur = self._conn.execute(
                "INSERT INTO tests (run_id, family, params_json, universe, period, "
                "metrics_json, passed, failure_reasons, candidate_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    family,
                    _dumps(params),
                    universe,
                    period,
                    _dumps(metrics),
                    int(bool(passed)),
                    failure_reasons,
                    key,
                    _utcnow(),
                ),
            )
        except sqlite3.IntegrityError as err:
            raise LedgerError(str(err)) from err
        self._conn.commit()
        return _require_rowid(cur)

    def record_note(self, run_id: int, batch_no: int, text: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO notes (run_id, batch_no, text, created_at) VALUES (?, ?, ?, ?)",
            (run_id, batch_no, text, _utcnow()),
        )
        self._conn.commit()
        return _require_rowid(cur)

    def record_validation(self, test_id: int, metrics: dict) -> int:
        try:
            self._conn.execute(
                "INSERT INTO validation_events (test_id, metrics_json, created_at) "
                "VALUES (?, ?, ?)",
                (test_id, _dumps(metrics), _utcnow()),
            )
        except sqlite3.IntegrityError as err:
            raise LedgerError(f"test {test_id} already has a validation event") from err
        self._conn.commit()
        return test_id

    def record_holdout_event(
        self, what_unsealed: str, reason: str, git_commit: str | None = None
    ) -> int:
        commit = git_commit if git_commit is not None else current_git_commit()
        cur = self._conn.execute(
            "INSERT INTO holdout_events (what_unsealed, git_commit, reason, created_at) "
            "VALUES (?, ?, ?, ?)",
            (what_unsealed, commit, reason, _utcnow()),
        )
        self._conn.commit()
        return _require_rowid(cur)

    # -- readers -----------------------------------------------------------

    def summary(self, run_id: int | None = None) -> dict:
        """Funnel counts for the search loop: tested, passed, validated,
        per-family pass counts, and near-misses grouped by failure reason.
        """
        if run_id is None:
            rows = self._conn.execute(_SELECT_TESTS_ALL).fetchall()
            validated = self._conn.execute(_COUNT_VALIDATED_ALL).fetchone()[0]
        else:
            rows = self._conn.execute(_SELECT_TESTS_BY_RUN, (run_id,)).fetchall()
            validated = self._conn.execute(_COUNT_VALIDATED_BY_RUN, (run_id,)).fetchone()[0]

        by_family: dict[str, dict[str, int]] = {}
        near_misses: dict[str, int] = {}
        for row in rows:
            fam = by_family.setdefault(row["family"], {"tested": 0, "passed": 0})
            fam["tested"] += 1
            if row["passed"]:
                fam["passed"] += 1
            elif row["failure_reasons"]:
                near_misses[row["failure_reasons"]] = near_misses.get(row["failure_reasons"], 0) + 1

        return {
            "run_id": run_id,
            "tested": len(rows),
            "passed": sum(1 for row in rows if row["passed"]),
            "validated": validated,
            "by_family": by_family,
            "near_misses": near_misses,
        }

    def top_candidates(
        self, run_id: int | None = None, n: int = 20, order_by: str = "sharpe"
    ) -> list[dict]:
        """The n candidates with the highest `order_by` metric.

        Sorting happens in Python (not `json_extract`) so this does not
        depend on the SQLite build having the JSON1 extension compiled in.
        """
        if run_id is None:
            rows = self._conn.execute(_SELECT_CANDIDATES_ALL).fetchall()
        else:
            rows = self._conn.execute(_SELECT_CANDIDATES_BY_RUN, (run_id,)).fetchall()
        validated_ids = {
            row[0] for row in self._conn.execute("SELECT test_id FROM validation_events").fetchall()
        }

        candidates = []
        for row in rows:
            metrics = json.loads(row["metrics_json"])
            if order_by not in metrics:
                continue
            candidates.append(
                {
                    "test_id": row["test_id"],
                    "run_id": row["run_id"],
                    "family": row["family"],
                    "params": json.loads(row["params_json"]),
                    "universe": row["universe"],
                    "metrics": metrics,
                    "passed": bool(row["passed"]),
                    "validated": row["test_id"] in validated_ids,
                }
            )
        candidates.sort(key=lambda c: c["metrics"][order_by], reverse=True)
        return candidates[:n]

    def list_runs(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT run_id, started_at, ended_at, git_commit, criteria_hash, seed_lane, "
            "seed_description FROM runs ORDER BY run_id"
        ).fetchall()
        return [dict(row) for row in rows]
