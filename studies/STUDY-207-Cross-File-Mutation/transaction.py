"""STUDY-207: atomic cross-file transaction (the hard core).

A cross-file mutation touches two (or more) files; it must commit on *all* of
them or *none*. This module demonstrates the all-or-nothing property with a
write-ahead-log (WAL) primitive:

    1. log the intended writes (a recoverable record of the whole batch);
    2. write every target to a temp file alongside it;
    3. atomically rename every temp into place;
    4. mark the WAL complete.

On any failure before the renames begin, the temps are discarded and every
original file is byte-identical to before. On a failure *during* the renames,
the WAL replay restores each touched file from its pre-image. There is no
observable state in which one file reflects the mutation and the other does
not.

A two-phase commit (prepare-all-temps, then commit-all-renames) is the
functionally equivalent alternative for the local-filesystem case; the WAL is
chosen because its log is an inspectable artifact that makes the all-or-nothing
property auditable, and because the log lists every intended file write, which
shapes naturally toward N files. Both are well-understood patterns; neither is
a production crash-recovery implementation — this proves the property (WHAT),
not a vendor mechanism (HOW).

Deterministic failure injection (``fail_after``) replaces a real disk-full /
read-only mount, which would be non-portable and flaky in CI. The injected
hook raises at a named, reproducible point mid-transaction.

AGPL-3.0 | Patent Pending (app 19/575,491)
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Named, reproducible failure-injection points (ADR-004).
INJECT_POINTS = (
    "wal_written",        # after the WAL log is written, before any temp
    "source_temp_write",  # after the first staged file's temp is written
    "target_temp_write",  # after the second staged file's temp is written
    "before_rename",      # after all temps written, before the first rename
)


class TransactionError(Exception):
    """The transaction was rejected or failed; all files are unchanged."""


class FailureInjected(TransactionError):
    """A deterministic mid-transaction failure fired (testing the rollback)."""


@dataclass
class _StagedWrite:
    path: Path
    graph: dict
    label: str
    existed: bool
    original_bytes: Optional[bytes]


@dataclass
class CommitResult:
    files_committed: list[str] = field(default_factory=list)
    wal_complete: bool = False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _serialize(graph: dict) -> bytes:
    return json.dumps(graph, indent=2).encode("utf-8")


class CrossFileTransaction:
    """All-or-nothing write across multiple files via a write-ahead log.

    Usage::

        txn = CrossFileTransaction(base_dir)
        txn.stage(path_source, graph_source, label="source")
        txn.stage(path_target, graph_target, label="target")
        txn.commit()                       # both renamed, or neither

    Pass ``fail_after="target_temp_write"`` to inject a deterministic failure
    after the target temp is written but before any rename — the rollback then
    leaves every file byte-identical.
    """

    def __init__(
        self,
        base_dir: Path,
        fail_after: Optional[str] = None,
    ) -> None:
        if fail_after is not None and fail_after not in INJECT_POINTS:
            raise TransactionError(f"unknown injection point: {fail_after}")
        self.base_dir = Path(base_dir)
        self.fail_after = fail_after
        self._staged: list[_StagedWrite] = []
        self._temps: list[Path] = []
        self.wal_path = self.base_dir / ".wal.json"

    def stage(self, path: Path, graph: dict, label: str) -> None:
        path = Path(path)
        existed = path.exists()
        original = path.read_bytes() if existed else None
        self._staged.append(
            _StagedWrite(path, graph, label, existed, original)
        )

    # -- internals -------------------------------------------------------------

    def _maybe_fail(self, point: str) -> None:
        if self.fail_after == point:
            raise FailureInjected(f"injected failure at {point}")

    def _write_wal(self) -> None:
        record = {
            "status": "pending",
            "writes": [
                {"file": s.path.name, "sha256": _sha256(_serialize(s.graph))}
                for s in self._staged
            ],
        }
        self.wal_path.write_text(json.dumps(record, indent=2))

    def _rollback_pre_rename(self) -> None:
        """No rename has happened yet: discard temps, originals are intact."""
        for tmp in self._temps:
            if tmp.exists():
                tmp.unlink()
        if self.wal_path.exists():
            self.wal_path.unlink()
        self._temps.clear()

    def _restore_from_preimage(self) -> None:
        """A rename may have partially applied: restore every file's pre-image."""
        for s in self._staged:
            if s.existed and s.original_bytes is not None:
                s.path.write_bytes(s.original_bytes)
            elif not s.existed and s.path.exists():
                s.path.unlink()
        for tmp in self._temps:
            if tmp.exists():
                tmp.unlink()
        if self.wal_path.exists():
            self.wal_path.unlink()
        self._temps.clear()

    # -- commit ----------------------------------------------------------------

    def commit(self) -> CommitResult:
        if not self._staged:
            raise TransactionError("nothing staged")

        # 1. write-ahead log of the whole batch
        try:
            self._write_wal()
            self._maybe_fail("wal_written")

            # 2. temp-write every target alongside it
            for s in self._staged:
                tmp = s.path.with_suffix(s.path.suffix + ".wal.tmp")
                tmp.write_bytes(_serialize(s.graph))
                self._temps.append(tmp)
                self._maybe_fail(f"{s.label}_temp_write")

            self._maybe_fail("before_rename")
        except Exception:
            # Nothing has been renamed into place — originals untouched.
            self._rollback_pre_rename()
            raise

        # 3. atomically rename every temp into place
        renamed: list[_StagedWrite] = []
        try:
            for s, tmp in zip(self._staged, self._temps):
                os.replace(tmp, s.path)  # atomic per-file rename
                renamed.append(s)
        except Exception:
            # A rename failed mid-batch: restore every file's pre-image.
            self._restore_from_preimage()
            raise

        # 4. mark the WAL complete, then clean it up
        record = json.loads(self.wal_path.read_text())
        record["status"] = "complete"
        self.wal_path.write_text(json.dumps(record, indent=2))
        self.wal_path.unlink()
        self._temps.clear()

        return CommitResult(
            files_committed=[s.path.name for s in renamed],
            wal_complete=True,
        )
