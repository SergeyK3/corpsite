from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, replace
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

import scripts.provision_hr_user_accounts as provisioner
from app.auth import verify_password
from app.db.engine import engine
from scripts.provision_hr_user_accounts import (
    ALREADY_EXISTS,
    AMBIGUOUS,
    APPROVED_ACCOUNTS,
    HR_UNIT_CODE,
    LINK_CONFLICT,
    LOGIN_CONFLICT,
    NOT_FOUND,
    ORDINARY_HR_ALLOWED_ROLE_GRANTS,
    ORDINARY_HR_ROLE_CODE,
    READY,
    AccountSpec,
    EffectivePlacement,
    EmployeeRecord,
    OrgUnitRecord,
    PlanRow,
    PlacementRecord,
    ProvisioningError,
    ProvisioningSnapshot,
    RoleRecord,
    UserRecord,
    build_plan_from_snapshot,
    load_snapshot,
    normalize_identity,
    provision_ready_rows,
    render_plan,
    run_apply,
    run_dry_run,
)


@dataclass
class _BackendOwner:
    connection: object | None = None
    raw_connection: object | None = None
    pid: int | None = None
    owns_connection: bool = False


class _BackendOwnership:
    def __init__(self, pid_getter) -> None:
        self._pid_getter = pid_getter
        self._lock = threading.RLock()
        self._owners: dict[str, _BackendOwner] = {}

    def publish(self, label: str, conn) -> int:
        if conn.closed:
            raise RuntimeError(f"cannot publish closed {label} connection")
        raw = conn.connection.driver_connection
        pid = int(self._pid_getter(conn))
        if pid <= 0:
            raise RuntimeError(f"invalid PostgreSQL backend PID for {label}: {pid}")
        with self._lock:
            self._owners[label] = _BackendOwner(conn, raw, pid, True)
        return pid

    def on_checkin(self, dbapi_connection, _connection_record) -> None:
        # SQLAlchemy invokes pool checkin synchronously before the DBAPI connection
        # can be handed to another consumer. The same lock serializes termination.
        with self._lock:
            for owner in self._owners.values():
                if owner.owns_connection and owner.raw_connection is dbapi_connection:
                    owner.connection = None
                    owner.raw_connection = None
                    owner.pid = None
                    owner.owns_connection = False

    def snapshot(self, label: str) -> _BackendOwner:
        with self._lock:
            owner = self._owners.get(label, _BackendOwner())
            return replace(owner)

    def release(self, label: str, conn) -> None:
        with self._lock:
            owner = self._owners.get(label)
            if owner is None or not owner.owns_connection:
                return
            if owner.connection is not conn:
                return
            owner.connection = None
            owner.raw_connection = None
            owner.pid = None
            owner.owns_connection = False

    def terminate_if_owned(self, label: str, thread, terminate) -> int | None:
        if not thread.is_alive():
            return None
        with self._lock:
            if not thread.is_alive():
                return None
            owner = self._owners.get(label)
            if owner is None or not owner.owns_connection:
                return None
            conn = owner.connection
            raw = owner.raw_connection
            pid = owner.pid
            if conn is None or raw is None or pid is None or pid <= 0 or conn.closed:
                return None
            if conn.connection.driver_connection is not raw:
                return None
            if int(self._pid_getter(conn)) != pid:
                return None
            # Keep the ownership lock through termination. A concurrent conn.close()
            # cannot complete pool checkin/reuse until this call returns.
            terminate(pid)
            return pid


@dataclass
class _TerminationChannel:
    connection: object
    cursor: object
    backend_pid: int

    def terminate(self, target_pid: int) -> None:
        if target_pid <= 0:
            raise RuntimeError(f"refusing invalid PostgreSQL backend PID: {target_pid}")
        if target_pid == self.backend_pid:
            raise RuntimeError("refusing to terminate the termination backend")
        self.cursor.execute("SELECT pg_terminate_backend(%s)", (target_pid,))
        row = self.cursor.fetchone()
        if row is None or row[0] is not True:
            raise RuntimeError(f"PostgreSQL did not terminate backend PID {target_pid}")

    def close(self) -> None:
        try:
            self.cursor.close()
        finally:
            self.connection.close()


def _open_direct_termination_channel(db_engine) -> _TerminationChannel:
    # Create a physical DBAPI connection directly through the dialect. It is not
    # checked out from db_engine.pool, so pool exhaustion cannot deadlock checkin.
    args, kwargs = db_engine.dialect.create_connect_args(db_engine.url)
    raw_connection = db_engine.dialect.connect(*args, **kwargs)
    cursor = None
    try:
        raw_connection.autocommit = True
        cursor = raw_connection.cursor()
        cursor.execute("SELECT pg_backend_pid()")
        backend_pid = int(cursor.fetchone()[0])
        if backend_pid <= 0:
            raise RuntimeError(f"invalid termination backend PID: {backend_pid}")
        return _TerminationChannel(raw_connection, cursor, backend_pid)
    except BaseException as primary:
        cleanup_errors: list[BaseException] = []
        try:
            if cursor is not None:
                try:
                    cursor.close()
                except BaseException as exc:
                    cleanup_errors.append(exc)
        finally:
            try:
                raw_connection.close()
            except BaseException as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_group = BaseExceptionGroup(
                "termination channel preparation cleanup failed",
                cleanup_errors,
            )
            primary.add_note(f"termination channel cleanup also failed: {cleanup_group!r}")
            raise primary from cleanup_group
        raise


@dataclass(frozen=True)
class _StopResult:
    stuck_label: str | None = None
    terminated_pid: int | None = None


def _stop_background_thread(
    thread: threading.Thread | None,
    *,
    owner_label: str,
    display_label: str,
    ownership: _BackendOwnership,
    termination_channel_factory,
    errors: list[BaseException],
    join_timeout: float,
) -> _StopResult:
    if thread is None:
        return _StopResult()
    thread.join(timeout=join_timeout)
    terminated_pid: int | None = None
    if thread.is_alive():
        channel = None
        try:
            # The direct connection and its cursor are fully prepared before the
            # ownership lock is acquired by terminate_if_owned().
            channel = termination_channel_factory()
            terminated_pid = ownership.terminate_if_owned(
                owner_label,
                thread,
                channel.terminate,
            )
        except BaseException as exc:
            exc.add_note(f"failed to terminate {display_label} backend")
            errors.append(exc)
        finally:
            if channel is not None:
                try:
                    channel.close()
                except BaseException as exc:
                    exc.add_note(f"failed to close {display_label} termination channel")
                    errors.append(exc)
        thread.join(timeout=join_timeout)
    return _StopResult(
        stuck_label=display_label if thread.is_alive() else None,
        terminated_pid=terminated_pid,
    )


def _cleanup_then_raise(primary: BaseException | None, cleanup) -> None:
    cleanup_error: BaseException | None = None
    try:
        cleanup()
    except BaseException as exc:
        cleanup_error = exc

    if primary is not None:
        if cleanup_error is not None:
            primary.add_note(f"cleanup also failed: {cleanup_error!r}")
            raise primary from cleanup_error
        raise primary
    if cleanup_error is not None:
        raise cleanup_error


def _background_apply_exception(
    writer_errors: list[BaseException],
    final_result: dict[str, object],
    *,
    final_started: bool,
) -> BaseException | None:
    if writer_errors:
        return writer_errors[0]
    if not final_started:
        return None
    final_exception = final_result.get("exception")
    if "return_code" in final_result:
        return AssertionError(f"final apply unexpectedly returned: {final_result}")
    if not isinstance(final_exception, ProvisioningError):
        return (
            final_exception
            if isinstance(final_exception, BaseException)
            else AssertionError(f"final apply produced no result: {final_result}")
        )
    if "final plan" not in str(final_exception):
        return AssertionError(f"unexpected final ProvisioningError: {final_exception}")
    return None


def _run_all_cleanup_steps(cleanup_conflict, cleanup_employees, cleanup_catalog) -> None:
    errors: list[BaseException] = []
    try:
        try:
            cleanup_conflict()
        except BaseException as exc:
            errors.append(exc)
    finally:
        try:
            try:
                cleanup_employees()
            except BaseException as exc:
                errors.append(exc)
        finally:
            try:
                cleanup_catalog()
            except BaseException as exc:
                errors.append(exc)

    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("multiple cleanup steps failed", errors)


def _finish_concurrency_orchestration(
    *,
    release_writer: threading.Event,
    writer_thread: threading.Thread | None,
    final_thread: threading.Thread | None,
    ownership: _BackendOwnership,
    termination_channel_factory,
    writer_errors: list[BaseException],
    final_result: dict[str, object],
    primary_exception: BaseException | None,
    remove_listener,
    cleanup_conflict,
    cleanup_employees,
    cleanup_catalog,
    join_timeout: float,
) -> dict[str, int]:
    release_writer.set()
    writer_stop = _stop_background_thread(
        writer_thread,
        owner_label="writer",
        display_label="writer",
        ownership=ownership,
        termination_channel_factory=termination_channel_factory,
        errors=writer_errors,
        join_timeout=join_timeout,
    )
    final_stop = _stop_background_thread(
        final_thread,
        owner_label="final",
        display_label="final",
        ownership=ownership,
        termination_channel_factory=termination_channel_factory,
        errors=writer_errors,
        join_timeout=join_timeout,
    )

    listener_exception: BaseException | None = None
    try:
        remove_listener()
    except BaseException as exc:
        listener_exception = exc

    stuck_threads = [
        result.stuck_label
        for result in (writer_stop, final_stop)
        if result.stuck_label is not None
    ]
    if stuck_threads:
        raise AssertionError(
            f"background thread(s) still alive after termination: {stuck_threads}"
        )

    background_exception = _background_apply_exception(
        writer_errors,
        final_result,
        final_started=final_thread is not None,
    )
    pending_exception = primary_exception
    if pending_exception is None:
        pending_exception = background_exception
    elif background_exception is not None and background_exception is not pending_exception:
        pending_exception.add_note(f"background thread also failed: {background_exception!r}")
    if pending_exception is None:
        pending_exception = listener_exception
    elif listener_exception is not None:
        pending_exception.add_note(
            f"pool listener removal also failed: {listener_exception!r}"
        )

    def cleanup() -> None:
        assert writer_thread is None or not writer_thread.is_alive()
        assert final_thread is None or not final_thread.is_alive()
        _run_all_cleanup_steps(cleanup_conflict, cleanup_employees, cleanup_catalog)

    _cleanup_then_raise(pending_exception, cleanup)
    return {
        result.stuck_label or label: result.terminated_pid
        for label, result in (("writer", writer_stop), ("final", final_stop))
        if result.terminated_pid is not None
    }


def _close_then_remove_listener(close_connection, remove_listener) -> None:
    try:
        close_connection()
    finally:
        remove_listener()


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backend_ownership_uses_live_pid_and_rejects_checked_in_connection() -> None:
    def pid_getter(conn) -> int:
        return int(conn.connection.driver_connection.get_backend_pid())

    class AliveThread:
        @staticmethod
        def is_alive() -> bool:
            return True

    ownership = _BackendOwnership(pid_getter)
    event.listen(engine.pool, "checkin", ownership.on_checkin)
    conn = engine.connect()
    terminated: list[int] = []
    try:
        pid = ownership.publish("worker", conn)
        published = ownership.snapshot("worker")
        assert published.owns_connection
        assert published.connection is conn
        assert published.raw_connection is conn.connection.driver_connection
        assert published.pid == pid
        assert not conn.closed

        selected_pid = ownership.terminate_if_owned(
            "worker",
            AliveThread(),
            terminated.append,
        )
        assert selected_pid == pid
        assert terminated == [pid]

        conn.close()
        checked_in = ownership.snapshot("worker")
        assert not checked_in.owns_connection
        assert checked_in.connection is None
        assert checked_in.raw_connection is None
        assert checked_in.pid is None

        assert (
            ownership.terminate_if_owned(
                "worker",
                AliveThread(),
                terminated.append,
            )
            is None
        )
        assert terminated == [pid]
        with pytest.raises(RuntimeError, match="closed"):
            ownership.publish("closed", conn)
    finally:
        _close_then_remove_listener(
            lambda: None if conn.closed else conn.close(),
            lambda: event.remove(engine.pool, "checkin", ownership.on_checkin),
        )
    assert not event.contains(engine.pool, "checkin", ownership.on_checkin)


def test_listener_removal_runs_even_when_connection_close_fails() -> None:
    calls: list[str] = []

    def failing_close() -> None:
        calls.append("close")
        raise RuntimeError("close failed")

    def remove_listener() -> None:
        calls.append("remove_listener")

    with pytest.raises(RuntimeError, match="close failed"):
        _close_then_remove_listener(failing_close, remove_listener)

    assert calls == ["close", "remove_listener"]


def test_partial_termination_channel_cleanup_preserves_preparation_error() -> None:
    preparation_error = RuntimeError("PID preparation failed")
    cursor_close_error = RuntimeError("cursor close failed")
    connection_close_error = RuntimeError("connection close failed")
    calls: list[str] = []

    class FailingCursor:
        def execute(self, _sql) -> None:
            calls.append("execute")
            raise preparation_error

        def close(self) -> None:
            calls.append("cursor.close")
            raise cursor_close_error

    class FailingRawConnection:
        autocommit = False

        def cursor(self):
            calls.append("cursor")
            return FailingCursor()

        def close(self) -> None:
            calls.append("connection.close")
            raise connection_close_error

    class DirectDialect:
        @staticmethod
        def create_connect_args(_url):
            return (), {}

        @staticmethod
        def connect(*_args, **_kwargs):
            calls.append("connect")
            return FailingRawConnection()

    class DirectEngine:
        dialect = DirectDialect()
        url = object()

    with pytest.raises(RuntimeError, match="PID preparation failed") as caught:
        _open_direct_termination_channel(DirectEngine())

    assert caught.value is preparation_error
    assert calls == ["connect", "cursor", "execute", "cursor.close", "connection.close"]
    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    assert caught.value.__cause__.exceptions == (
        cursor_close_error,
        connection_close_error,
    )
    assert any("termination channel cleanup also failed" in note for note in caught.value.__notes__)


def _start_release_thread(release: threading.Event, label: str) -> threading.Thread:
    started = threading.Event()

    def worker() -> None:
        started.set()
        if not release.wait(timeout=10):
            raise RuntimeError(f"{label} test thread was not released")

    thread = threading.Thread(target=worker, name=label, daemon=False)
    thread.start()
    assert started.wait(timeout=2)
    return thread


@pytest.mark.parametrize(
    ("source", "expected_type", "expected_message"),
    (
        ("writer", RuntimeError, "writer error"),
        ("final_exception", RuntimeError, "unexpected final exception"),
        ("return_code", AssertionError, "unexpectedly returned"),
        ("primary", AssertionError, "polling assertion"),
    ),
)
def test_full_orchestration_cleans_before_raising_pending_exception(
    source: str,
    expected_type: type[BaseException],
    expected_message: str,
) -> None:
    release = threading.Event()
    writer_thread = _start_release_thread(release, "orchestration-writer")
    final_thread = _start_release_thread(release, "orchestration-final")
    writer_error = RuntimeError("writer error")
    final_error = RuntimeError("unexpected final exception")
    primary_error = AssertionError("polling assertion")
    writer_errors = [writer_error] if source == "writer" else []
    if source == "final_exception":
        final_result: dict[str, object] = {"exception": final_error}
    elif source == "return_code":
        final_result = {"return_code": 0}
    else:
        final_result = {"exception": ProvisioningError("final plan changed")}
    primary = primary_error if source == "primary" else None
    cleanup_order: list[str] = []
    ownership = _BackendOwnership(lambda _conn: 1)

    def cleanup_step(label: str) -> None:
        assert not writer_thread.is_alive()
        assert not final_thread.is_alive()
        cleanup_order.append(label)

    try:
        with pytest.raises(expected_type, match=expected_message) as caught:
            _finish_concurrency_orchestration(
                release_writer=release,
                writer_thread=writer_thread,
                final_thread=final_thread,
                ownership=ownership,
                termination_channel_factory=lambda: pytest.fail(
                    "termination channel must not be opened for stopped threads"
                ),
                writer_errors=writer_errors,
                final_result=final_result,
                primary_exception=primary,
                remove_listener=lambda: None,
                cleanup_conflict=lambda: cleanup_step("conflict"),
                cleanup_employees=lambda: cleanup_step("employees"),
                cleanup_catalog=lambda: cleanup_step("catalog"),
                join_timeout=2,
            )
        expected_exception = {
            "writer": writer_error,
            "final_exception": final_error,
            "primary": primary_error,
        }.get(source)
        if expected_exception is not None:
            assert caught.value is expected_exception
        assert cleanup_order == ["conflict", "employees", "catalog"]
    finally:
        release.set()
        writer_thread.join(timeout=2)
        final_thread.join(timeout=2)
        assert not writer_thread.is_alive()
        assert not final_thread.is_alive()


@pytest.mark.parametrize("failing_step", ("conflict", "employees", "catalog"))
def test_full_orchestration_attempts_every_cleanup_step_after_failure(
    failing_step: str,
) -> None:
    release = threading.Event()
    writer_thread = _start_release_thread(release, "cleanup-writer")
    final_thread = _start_release_thread(release, "cleanup-final")
    primary = RuntimeError("primary failure")
    cleanup_failure = ValueError(f"{failing_step} cleanup failed")
    cleanup_order: list[str] = []

    def cleanup_step(label: str) -> None:
        assert not writer_thread.is_alive()
        assert not final_thread.is_alive()
        cleanup_order.append(label)
        if label == failing_step:
            raise cleanup_failure

    try:
        with pytest.raises(RuntimeError, match="primary failure") as caught:
            _finish_concurrency_orchestration(
                release_writer=release,
                writer_thread=writer_thread,
                final_thread=final_thread,
                ownership=_BackendOwnership(lambda _conn: 1),
                termination_channel_factory=lambda: pytest.fail(
                    "termination channel must not be opened for stopped threads"
                ),
                writer_errors=[],
                final_result={"exception": ProvisioningError("final plan changed")},
                primary_exception=primary,
                remove_listener=lambda: None,
                cleanup_conflict=lambda: cleanup_step("conflict"),
                cleanup_employees=lambda: cleanup_step("employees"),
                cleanup_catalog=lambda: cleanup_step("catalog"),
                join_timeout=2,
            )
        assert caught.value is primary
        assert caught.value.__cause__ is cleanup_failure
        assert any("cleanup also failed" in note for note in caught.value.__notes__)
        assert cleanup_order == ["conflict", "employees", "catalog"]
    finally:
        release.set()
        writer_thread.join(timeout=2)
        final_thread.join(timeout=2)
        assert not writer_thread.is_alive()
        assert not final_thread.is_alive()


def test_full_orchestration_raises_cleanup_failure_without_primary() -> None:
    cleanup_order: list[str] = []
    cleanup_failure = ValueError("employees cleanup failed")

    def cleanup_step(label: str) -> None:
        cleanup_order.append(label)
        if label == "employees":
            raise cleanup_failure

    with pytest.raises(ValueError, match="employees cleanup failed") as caught:
        _finish_concurrency_orchestration(
            release_writer=threading.Event(),
            writer_thread=None,
            final_thread=None,
            ownership=_BackendOwnership(lambda _conn: 1),
            termination_channel_factory=lambda: pytest.fail("unexpected termination"),
            writer_errors=[],
            final_result={},
            primary_exception=None,
            remove_listener=lambda: None,
            cleanup_conflict=lambda: cleanup_step("conflict"),
            cleanup_employees=lambda: cleanup_step("employees"),
            cleanup_catalog=lambda: cleanup_step("catalog"),
            join_timeout=0.1,
        )

    assert caught.value is cleanup_failure
    assert cleanup_order == ["conflict", "employees", "catalog"]


def test_multiple_cleanup_failures_remain_diagnostic() -> None:
    cleanup_order: list[str] = []
    primary = RuntimeError("primary failure")

    def failing_step(label: str) -> None:
        cleanup_order.append(label)
        raise ValueError(f"{label} cleanup failed")

    with pytest.raises(RuntimeError, match="primary failure") as caught:
        _finish_concurrency_orchestration(
            release_writer=threading.Event(),
            writer_thread=None,
            final_thread=None,
            ownership=_BackendOwnership(lambda _conn: 1),
            termination_channel_factory=lambda: pytest.fail("unexpected termination"),
            writer_errors=[],
            final_result={},
            primary_exception=primary,
            remove_listener=lambda: None,
            cleanup_conflict=lambda: failing_step("conflict"),
            cleanup_employees=lambda: failing_step("employees"),
            cleanup_catalog=lambda: failing_step("catalog"),
            join_timeout=0.1,
        )

    assert caught.value is primary
    assert isinstance(caught.value.__cause__, ExceptionGroup)
    assert len(caught.value.__cause__.exceptions) == 3
    assert cleanup_order == ["conflict", "employees", "catalog"]


def test_multiple_base_cleanup_failures_without_primary_raise_group() -> None:
    class CleanupSignal(BaseException):
        pass

    conflict_failure = CleanupSignal("conflict cleanup failed")
    catalog_failure = CleanupSignal("catalog cleanup failed")
    cleanup_order: list[str] = []

    def cleanup_step(label: str) -> None:
        cleanup_order.append(label)
        if label == "conflict":
            raise conflict_failure
        if label == "catalog":
            raise catalog_failure

    with pytest.raises(BaseExceptionGroup) as caught:
        _finish_concurrency_orchestration(
            release_writer=threading.Event(),
            writer_thread=None,
            final_thread=None,
            ownership=_BackendOwnership(lambda _conn: 1),
            termination_channel_factory=lambda: pytest.fail("unexpected termination"),
            writer_errors=[],
            final_result={},
            primary_exception=None,
            remove_listener=lambda: None,
            cleanup_conflict=lambda: cleanup_step("conflict"),
            cleanup_employees=lambda: cleanup_step("employees"),
            cleanup_catalog=lambda: cleanup_step("catalog"),
            join_timeout=0.1,
        )

    assert type(caught.value) is BaseExceptionGroup
    assert caught.value.exceptions == (conflict_failure, catalog_failure)
    assert cleanup_order == ["conflict", "employees", "catalog"]


def _exercise_exhausted_pool_stop(
    termination_channel_factory,
    observations: dict[str, object],
    *,
    expect_termination: bool,
) -> None:
    isolated_engine = create_engine(
        engine.url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
        pool_pre_ping=True,
    )
    ownership = _BackendOwnership(
        lambda conn: int(conn.connection.driver_connection.get_backend_pid())
    )
    ready = threading.Event()
    worker_errors: list[BaseException] = []
    worker_pid: dict[str, int] = {}
    thread: threading.Thread | None = None
    primary_exception: BaseException | None = None
    listener_registered = False

    def worker() -> None:
        conn = None
        try:
            conn = isolated_engine.connect()
            worker_pid["pid"] = ownership.publish("writer", conn)
            ready.set()
            # The operation is intentionally finite so cleanup can wait for a
            # natural exit even when every termination attempt is unavailable.
            conn.execute(text("SELECT pg_sleep(3)"))
        except BaseException as exc:
            worker_errors.append(exc)
            ready.set()
        finally:
            if conn is not None:
                ownership.release("writer", conn)
                conn.close()

    try:
        event.listen(isolated_engine.pool, "checkin", ownership.on_checkin)
        listener_registered = True
        thread = threading.Thread(
            target=worker,
            name="pool-exhaustion-writer",
            daemon=False,
        )
        thread.start()
        assert ready.wait(timeout=5), "worker did not acquire the sole pooled connection"
        assert ownership.snapshot("writer").owns_connection
        assert isolated_engine.pool.checkedout() == 1
        with pytest.raises(SQLAlchemyTimeoutError):
            isolated_engine.connect()

        stop_errors: list[BaseException] = []
        started_at = time.monotonic()
        result = _stop_background_thread(
            thread,
            owner_label="writer",
            display_label="writer",
            ownership=ownership,
            termination_channel_factory=lambda: termination_channel_factory(isolated_engine),
            errors=stop_errors,
            join_timeout=1,
        )
        elapsed = time.monotonic() - started_at

        observations["result"] = result
        observations["elapsed"] = elapsed
        observations["worker_pid"] = worker_pid.get("pid")
        if stop_errors:
            raise stop_errors[0]
        if expect_termination:
            assert result.stuck_label is None
            assert result.terminated_pid == worker_pid["pid"]
            assert not thread.is_alive()
            assert elapsed < 5
            assert worker_errors, "terminated PostgreSQL query must exit through an exception"
            assert not ownership.snapshot("writer").owns_connection
            assert isolated_engine.pool.checkedout() == 0
    except BaseException as exc:
        primary_exception = exc

    def cleanup_worker() -> None:
        cleanup_errors: list[BaseException] = []
        if thread is not None:
            try:
                # pg_sleep(3) makes this a bounded natural-completion fallback.
                thread.join(timeout=5)
            except BaseException as exc:
                cleanup_errors.append(exc)
            if thread.is_alive() and "pid" in worker_pid:
                channel = None
                try:
                    channel = _open_direct_termination_channel(isolated_engine)
                    channel.terminate(worker_pid["pid"])
                except BaseException as exc:
                    cleanup_errors.append(exc)
                finally:
                    if channel is not None:
                        try:
                            channel.close()
                        except BaseException as exc:
                            cleanup_errors.append(exc)
                try:
                    thread.join(timeout=5)
                except BaseException as exc:
                    cleanup_errors.append(exc)
            if thread.is_alive():
                cleanup_errors.append(
                    AssertionError("exhausted-pool worker remained alive after bounded cleanup")
                )
        observations["worker_alive_after_cleanup"] = bool(thread and thread.is_alive())
        observations["pool_checkedout_after_cleanup"] = isolated_engine.pool.checkedout()
        if len(cleanup_errors) == 1:
            raise cleanup_errors[0]
        if cleanup_errors:
            raise BaseExceptionGroup("exhausted-pool worker cleanup failed", cleanup_errors)

    def remove_listener() -> None:
        try:
            if listener_registered:
                event.remove(isolated_engine.pool, "checkin", ownership.on_checkin)
        finally:
            observations["listener_removed"] = not event.contains(
                isolated_engine.pool,
                "checkin",
                ownership.on_checkin,
            )

    def dispose_engine() -> None:
        try:
            isolated_engine.dispose()
        finally:
            observations["engine_disposed"] = True

    _cleanup_then_raise(
        primary_exception,
        lambda: _run_all_cleanup_steps(
            cleanup_worker,
            remove_listener,
            dispose_engine,
        ),
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stop_thread_terminates_real_backend_with_exhausted_pool() -> None:
    observations: dict[str, object] = {}

    _exercise_exhausted_pool_stop(
        _open_direct_termination_channel,
        observations,
        expect_termination=True,
    )

    assert observations["worker_alive_after_cleanup"] is False
    assert observations["pool_checkedout_after_cleanup"] == 0
    assert observations["listener_removed"] is True
    assert observations["engine_disposed"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_exhausted_pool_channel_open_failure_still_cleans_everything() -> None:
    channel_error = RuntimeError("termination channel unavailable")
    observations: dict[str, object] = {}

    def fail_channel_open(_isolated_engine):
        raise channel_error

    started_at = time.monotonic()
    with pytest.raises(RuntimeError, match="termination channel unavailable") as caught:
        _exercise_exhausted_pool_stop(
            fail_channel_open,
            observations,
            expect_termination=False,
        )
    elapsed = time.monotonic() - started_at

    assert caught.value is channel_error
    assert elapsed < 10
    assert observations["worker_alive_after_cleanup"] is False
    assert observations["pool_checkedout_after_cleanup"] == 0
    assert observations["listener_removed"] is True
    assert observations["engine_disposed"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stop_thread_does_not_terminate_checked_in_pooled_pid() -> None:
    ownership = _BackendOwnership(
        lambda conn: int(conn.connection.driver_connection.get_backend_pid())
    )
    event.listen(engine.pool, "checkin", ownership.on_checkin)
    checked_in = threading.Event()
    allow_finish = threading.Event()
    stale_pid: dict[str, int] = {}

    def worker() -> None:
        conn = engine.connect()
        try:
            stale_pid["pid"] = ownership.publish("writer", conn)
        finally:
            conn.close()
            checked_in.set()
        allow_finish.wait(timeout=5)

    thread = threading.Thread(target=worker, name="checked-in-writer", daemon=False)
    thread.start()
    opened_channels: list[_TerminationChannel] = []

    def open_channel_and_release_worker() -> _TerminationChannel:
        channel = _open_direct_termination_channel(engine)
        opened_channels.append(channel)
        allow_finish.set()
        return channel

    try:
        assert checked_in.wait(timeout=5)
        assert not ownership.snapshot("writer").owns_connection
        result = _stop_background_thread(
            thread,
            owner_label="writer",
            display_label="writer",
            ownership=ownership,
            termination_channel_factory=open_channel_and_release_worker,
            errors=[],
            join_timeout=0.1,
        )
        assert opened_channels, "full stop path did not prepare a termination channel"
        assert result.stuck_label is None
        assert result.terminated_pid is None
        assert not thread.is_alive()
        assert stale_pid["pid"] > 0
    finally:
        allow_finish.set()
        thread.join(timeout=5)
        try:
            event.remove(engine.pool, "checkin", ownership.on_checkin)
        finally:
            assert not thread.is_alive()
            assert not event.contains(engine.pool, "checkin", ownership.on_checkin)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stuck_thread_fails_before_cleanup_after_real_backend_termination() -> None:
    ownership = _BackendOwnership(
        lambda conn: int(conn.connection.driver_connection.get_backend_pid())
    )
    event.listen(engine.pool, "checkin", ownership.on_checkin)
    query_started = threading.Event()
    remain_stuck = threading.Event()
    release_writer = threading.Event()
    cleanup_order: list[str] = []
    worker_pid: dict[str, int] = {}

    def worker() -> None:
        conn = None
        try:
            conn = engine.connect()
            worker_pid["pid"] = ownership.publish("writer", conn)
            query_started.set()
            conn.execute(text("SELECT pg_sleep(30)"))
        except BaseException:
            query_started.set()
            remain_stuck.wait(timeout=10)
        finally:
            if conn is not None:
                ownership.release("writer", conn)
                conn.close()

    thread = threading.Thread(target=worker, name="stuck-writer", daemon=False)
    thread.start()
    listener_removed = False
    try:
        assert query_started.wait(timeout=5)
        with pytest.raises(AssertionError, match="still alive after termination"):
            _finish_concurrency_orchestration(
                release_writer=release_writer,
                writer_thread=thread,
                final_thread=None,
                ownership=ownership,
                termination_channel_factory=lambda: _open_direct_termination_channel(engine),
                writer_errors=[],
                final_result={},
                primary_exception=None,
                remove_listener=lambda: (
                    event.remove(engine.pool, "checkin", ownership.on_checkin),
                    cleanup_order.append("listener_removed"),
                ),
                cleanup_conflict=lambda: cleanup_order.append("conflict"),
                cleanup_employees=lambda: cleanup_order.append("employees"),
                cleanup_catalog=lambda: cleanup_order.append("catalog"),
                join_timeout=0.2,
            )
        listener_removed = True
        assert thread.is_alive()
        assert cleanup_order == ["listener_removed"]
        assert worker_pid["pid"] > 0
    finally:
        remain_stuck.set()
        thread.join(timeout=5)
        if event.contains(engine.pool, "checkin", ownership.on_checkin):
            event.remove(engine.pool, "checkin", ownership.on_checkin)
        assert not thread.is_alive()
        assert listener_removed


@pytest.mark.parametrize(
    ("writer_errors", "final_result", "expected_type", "expected_message"),
    (
        ([RuntimeError("writer error")], {}, RuntimeError, "writer error"),
        (
            [],
            {"exception": RuntimeError("unexpected final exception")},
            RuntimeError,
            "unexpected final exception",
        ),
        ([], {"return_code": 0}, AssertionError, "unexpectedly returned"),
    ),
)
def test_pending_exception_is_raised_only_after_cleanup(
    writer_errors: list[BaseException],
    final_result: dict[str, object],
    expected_type: type[BaseException],
    expected_message: str,
) -> None:
    order: list[str] = []
    pending = _background_apply_exception(
        writer_errors,
        final_result,
        final_started=True,
    )
    assert pending is not None

    def cleanup() -> None:
        order.append("cleanup")

    with pytest.raises(expected_type, match=expected_message) as caught:
        _cleanup_then_raise(pending, cleanup)

    assert caught.value is pending
    assert order == ["cleanup"]


def test_primary_exception_survives_cleanup_failure() -> None:
    primary = RuntimeError("primary failure")
    cleanup_error = ValueError("cleanup failure")

    def failing_cleanup() -> None:
        raise cleanup_error

    with pytest.raises(RuntimeError, match="primary failure") as caught:
        _cleanup_then_raise(primary, failing_cleanup)

    assert caught.value is primary
    assert caught.value.__cause__ is cleanup_error
    assert any("cleanup also failed" in note for note in caught.value.__notes__)


def test_cleanup_failure_is_raised_without_primary_exception() -> None:
    cleanup_error = ValueError("cleanup failure")

    def failing_cleanup() -> None:
        raise cleanup_error

    with pytest.raises(ValueError, match="cleanup failure") as caught:
        _cleanup_then_raise(None, failing_cleanup)

    assert caught.value is cleanup_error


def _role(*, grants: tuple[str, ...] = ()) -> RoleRecord:
    return RoleRecord(44, ORDINARY_HR_ROLE_CODE, "сотрудник1 ОК", True, grants)


def _unit() -> OrgUnitRecord:
    return OrgUnitRecord(73, HR_UNIT_CODE, "Отдел кадров", True)


def _employee(index: int, full_name: str) -> EmployeeRecord:
    return EmployeeRecord(
        employee_id=10_000 + index,
        full_name=full_name,
        person_id=None,
        is_active=True,
        operational_status="active",
        org_unit_id=73,
        org_unit_code=HR_UNIT_CODE,
        org_unit_name="Отдел кадров",
        position_id=20_000 + index,
        position_name="Менеджер",
        date_from=date(2025, 1, 1),
        date_to=None,
    )


def _snapshot(
    *,
    specs: tuple[AccountSpec, ...] = APPROVED_ACCOUNTS,
    employees: tuple[EmployeeRecord, ...] | None = None,
    users: tuple[UserRecord, ...] = (),
    placements: tuple[PlacementRecord, ...] = (),
    role: RoleRecord | None = None,
) -> ProvisioningSnapshot:
    employee_rows = employees or tuple(
        _employee(index, spec.source_full_name) for index, spec in enumerate(specs, start=1)
    )
    return ProvisioningSnapshot(
        roles=(role or _role(),),
        org_units=(_unit(),),
        employees=employee_rows,
        placements=placements,
        users=users,
    )


def test_successful_dry_run_plan_and_render(capsys) -> None:
    plan = build_plan_from_snapshot(_snapshot(), today=date(2026, 8, 5))

    assert len(plan) == 12
    assert {row.status for row in plan} == {READY}
    assert {row.proposed_role.code for row in plan} == {ORDINARY_HR_ROLE_CODE}
    assert all(row.placement and row.placement.source == "employee_snapshot" for row in plan)

    render_plan(plan)
    output = capsys.readouterr().out
    assert "READY=12" in output
    assert "must_change_password=false" in output
    assert APPROVED_ACCOUNTS[0].source_full_name in output


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dry_run_does_not_change_database(capsys, monkeypatch) -> None:
    with engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM public.users")).scalar_one()

    safe_plan = build_plan_from_snapshot(_snapshot(), today=date(2026, 8, 5))
    monkeypatch.setattr(provisioner, "build_plan", lambda _conn: safe_plan)
    result = run_dry_run(engine)

    with engine.connect() as conn:
        after = conn.execute(text("SELECT COUNT(*) FROM public.users")).scalar_one()
    assert result in {0, 2}
    assert after == before
    assert "HR user provisioning plan" in capsys.readouterr().out


def test_exact_unicode_matching_for_kazakh_cyrillic() -> None:
    spec = APPROVED_ACCOUNTS[-1]
    employee = _employee(1, "  ӨСЕРОВА\tАйсара   Асанқызы ")
    snapshot = _snapshot(specs=(spec,), employees=(employee,))

    plan = build_plan_from_snapshot(snapshot, (spec,), today=date(2026, 8, 5))

    assert plan[0].status == READY
    assert plan[0].employee and plan[0].employee.employee_id == employee.employee_id
    assert normalize_identity("Өсерова Айсара Асанқызы") == normalize_identity(
        employee.full_name
    )


def test_double_space_normalization_is_exact_not_fuzzy() -> None:
    spec = AccountSpec("Абзалқызы Толғанай", "abzalkyzy.t")
    exact = _employee(1, "Абзалқызы  Толғанай")
    near_but_not_exact = _employee(2, "Абзалқызы Толганай")
    snapshot = _snapshot(specs=(spec,), employees=(exact, near_but_not_exact))

    plan = build_plan_from_snapshot(snapshot, (spec,), today=date(2026, 8, 5))

    assert plan[0].status == READY
    assert plan[0].employee and plan[0].employee.employee_id == exact.employee_id


def test_not_found_and_ambiguous_are_fail_closed() -> None:
    missing = AccountSpec("Нет Такого Сотрудника", "missing.user")
    duplicate = AccountSpec("Дубликат Сотрудник", "duplicate.user")
    employees = (_employee(1, duplicate.source_full_name), _employee(2, duplicate.source_full_name))
    snapshot = _snapshot(specs=(missing, duplicate), employees=employees)

    plan = build_plan_from_snapshot(snapshot, (missing, duplicate), today=date(2026, 8, 5))

    assert [row.status for row in plan] == [NOT_FOUND, AMBIGUOUS]


def test_login_conflict_and_link_conflict_are_distinct() -> None:
    login_spec = AccountSpec("Первый Сотрудник", "occupied.login")
    link_spec = AccountSpec("Второй Сотрудник", "wanted.login")
    employees = (
        _employee(1, login_spec.source_full_name),
        _employee(2, link_spec.source_full_name),
    )
    users = (
        UserRecord(
            501,
            99_999,
            "Другой Пользователь",
            "occupied.login",
            44,
            "HR_reg",
            True,
        ),
        UserRecord(
            502,
            employees[1].employee_id,
            link_spec.source_full_name,
            "old.login",
            44,
            "HR_reg",
            True,
        ),
    )
    snapshot = _snapshot(specs=(login_spec, link_spec), employees=employees, users=users)

    plan = build_plan_from_snapshot(snapshot, (login_spec, link_spec), today=date(2026, 8, 5))

    assert [row.status for row in plan] == [LOGIN_CONFLICT, LINK_CONFLICT]


def test_unlinked_same_fio_is_link_conflict() -> None:
    spec = APPROVED_ACCOUNTS[-1]
    employee = _employee(1, spec.source_full_name)
    existing_unlinked = UserRecord(
        8,
        None,
        spec.source_full_name,
        "hr_head@corp.local",
        14,
        "HR_HEAD",
        True,
    )
    snapshot = _snapshot(specs=(spec,), employees=(employee,), users=(existing_unlinked,))

    plan = build_plan_from_snapshot(snapshot, (spec,), today=date(2026, 8, 5))

    assert plan[0].status == LINK_CONFLICT
    assert "user(s): 8" in plan[0].detail


def test_existing_account_is_already_exists_and_not_rewritten() -> None:
    spec = APPROVED_ACCOUNTS[0]
    employee = _employee(1, spec.source_full_name)
    existing = UserRecord(
        700,
        employee.employee_id,
        "Stored Existing Name",
        spec.login,
        14,
        "HR_HEAD",
        False,
    )
    snapshot = _snapshot(specs=(spec,), employees=(employee,), users=(existing,))

    plan = build_plan_from_snapshot(snapshot, (spec,), today=date(2026, 8, 5))

    assert plan[0].status == ALREADY_EXISTS
    assert plan[0].existing_user == existing
    assert plan[0].existing_user.login == spec.login
    assert plan[0].existing_user.role_code == "HR_HEAD"


def test_duplicate_login_owner_prevents_already_exists() -> None:
    spec = APPROVED_ACCOUNTS[0]
    employee = _employee(1, spec.source_full_name)
    linked = UserRecord(
        700,
        employee.employee_id,
        spec.source_full_name,
        spec.login,
        44,
        "HR_reg",
        True,
    )
    duplicate_owner = UserRecord(
        701,
        None,
        "Another User",
        f"  {spec.login.upper()}  ",
        44,
        "HR_reg",
        True,
    )
    snapshot = _snapshot(
        specs=(spec,),
        employees=(employee,),
        users=(linked, duplicate_owner),
    )

    plan = build_plan_from_snapshot(snapshot, (spec,), today=date(2026, 8, 5))

    assert plan[0].status == LOGIN_CONFLICT
    assert plan[0].existing_user == linked


def test_ordinary_role_is_not_hr_head_and_has_no_implicit_grants() -> None:
    plan = build_plan_from_snapshot(_snapshot(), today=date(2026, 8, 5))
    assert all(row.proposed_role.code == ORDINARY_HR_ROLE_CODE for row in plan)
    assert all(row.proposed_role.code != "HR_HEAD" for row in plan)

    baseline_plan = build_plan_from_snapshot(
        _snapshot(role=_role(grants=("ACCESS_OBSERVER",))),
        today=date(2026, 8, 5),
    )
    assert {row.status for row in baseline_plan} == {READY}
    assert ORDINARY_HR_ALLOWED_ROLE_GRANTS == frozenset({"ACCESS_OBSERVER"})

    with pytest.raises(ProvisioningError, match="non-baseline effective access grants"):
        build_plan_from_snapshot(
            _snapshot(role=_role(grants=("INCOMING_INFO_REGISTER",))),
            today=date(2026, 8, 5),
        )


@pytest.mark.parametrize(
    "grant_code",
    (
        "INCOMING_INFO_REGISTER",
        "INCOMING_INFO_READ",
        "INCOMING_INFO_RESOLVE",
        "INCOMING_INFO_EXECUTE",
        "INCOMING_INFO_CONTROL",
        "INCOMING_INFO_ADMIN",
        "INCOMING_INFO_RESTRICTED_BYPASS",
        "UNKNOWN_SPECIAL_PERMISSION",
    ),
)
def test_special_or_unknown_role_grant_is_fail_closed(grant_code: str) -> None:
    with pytest.raises(ProvisioningError, match=grant_code):
        build_plan_from_snapshot(
            _snapshot(role=_role(grants=(grant_code,))),
            today=date(2026, 8, 5),
        )


def _load_integration_role_and_unit(
    conn,
) -> tuple[RoleRecord, OrgUnitRecord, int, bool, bool, bool]:
    roles_have_is_active = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='roles' AND column_name='is_active'
            """
        )
    ).first() is not None
    role_active_sql = "is_active" if roles_have_is_active else "TRUE"
    role_row = conn.execute(
        text(
            f"SELECT role_id,code,name,{role_active_sql} AS is_active FROM public.roles "
            f"WHERE code=:code AND {role_active_sql}=TRUE"
        ),
        {"code": ORDINARY_HR_ROLE_CODE},
    ).mappings().first()
    created_role = False
    if not role_row:
        role_columns = {
            str(row[0])
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='roles'"
                )
            )
        }
        role_values = {"code": ORDINARY_HR_ROLE_CODE, "name": "pytest ordinary HR"}
        columns = ["code", "name"]
        if "is_active" in role_columns:
            role_values["is_active"] = True
            columns.append("is_active")
        role_id = conn.execute(
            text(
                f"INSERT INTO public.roles ({','.join(columns)}) "
                f"VALUES ({','.join(':' + column for column in columns)}) RETURNING role_id"
            ),
            role_values,
        ).scalar_one()
        role_row = {
            "role_id": int(role_id),
            "code": ORDINARY_HR_ROLE_CODE,
            "name": "pytest ordinary HR",
            "is_active": True,
        }
        created_role = True
    unit_row = conn.execute(
        text(
            "SELECT unit_id,code,name,is_active FROM public.org_units "
            "WHERE lower(trim(code))=lower(:code) AND is_active=TRUE"
        ),
        {"code": HR_UNIT_CODE},
    ).mappings().first()
    created_unit = False
    if not unit_row:
        unit_id = conn.execute(
            text(
                """
                INSERT INTO public.org_units (name,code,is_active)
                VALUES ('pytest HR unit',:code,TRUE)
                RETURNING unit_id
                """
            ),
            {"code": HR_UNIT_CODE},
        ).scalar_one()
        unit_row = {
            "unit_id": int(unit_id),
            "code": HR_UNIT_CODE,
            "name": "pytest HR unit",
            "is_active": True,
        }
        created_unit = True
    position_id = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
    ).scalar_one_or_none()
    created_position = False
    if position_id is None:
        position_id = conn.execute(
            text(
                "INSERT INTO public.positions (name) "
                "VALUES ('pytest HR position') RETURNING position_id"
            )
        ).scalar_one()
        created_position = True
    grants = tuple(
        conn.execute(
            text(
                """
                SELECT ar.code FROM public.access_grants g
                JOIN public.access_roles ar ON ar.access_role_id=g.access_role_id
                WHERE g.target_type='ROLE' AND g.target_id=:role_id AND g.active_flag=TRUE
                  AND g.revoked_at IS NULL
                  AND g.starts_at <= statement_timestamp()
                  AND (g.ends_at IS NULL OR g.ends_at > statement_timestamp())
                  AND ar.is_active=TRUE
                ORDER BY ar.code
                """
            ),
            {"role_id": int(role_row["role_id"])},
        ).scalars()
    )
    unexpected_grants = sorted(set(grants) - ORDINARY_HR_ALLOWED_ROLE_GRANTS)
    if unexpected_grants:
        pytest.skip(f"HR_reg has non-baseline role grants: {unexpected_grants}")
    return (
        RoleRecord(
            int(role_row["role_id"]),
            str(role_row["code"]),
            str(role_row["name"]),
            bool(role_row["is_active"]),
            grants,
        ),
        OrgUnitRecord(
            int(unit_row["unit_id"]),
            str(unit_row["code"]),
            str(unit_row["name"]),
            bool(unit_row["is_active"]),
        ),
        int(position_id),
        created_role,
        created_unit,
        created_position,
    )


def _create_integration_employees(conn, *, unit_id: int, position_id: int, token: str):
    employees: list[EmployeeRecord] = []
    specs: list[AccountSpec] = []
    for index in range(12):
        full_name = f"Pytest HR Provision {token} {index:02d}"
        login = f"pytest.hr.{token}.{index:02d}"
        employee_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name,org_unit_id,position_id,date_from,is_active,operational_status
                    ) VALUES (
                        :full_name,:unit_id,:position_id,CURRENT_DATE,TRUE,'active'
                    ) RETURNING employee_id
                    """
                ),
                {"full_name": full_name, "unit_id": unit_id, "position_id": position_id},
            ).scalar_one()
        )
        specs.append(AccountSpec(full_name, login))
        employees.append(
            EmployeeRecord(
                employee_id,
                full_name,
                None,
                True,
                "active",
                unit_id,
                HR_UNIT_CODE,
                "Отдел кадров",
                position_id,
                "Test Position",
                date.today(),
                None,
            )
        )
    return tuple(specs), tuple(employees)


def _ready_integration_plan(
    specs: tuple[AccountSpec, ...],
    employees: tuple[EmployeeRecord, ...],
    role: RoleRecord,
    unit: OrgUnitRecord,
) -> list[PlanRow]:
    return [
        PlanRow(
            spec=spec,
            status=READY,
            detail="integration ready",
            employee=employee,
            placement=EffectivePlacement(
                unit.unit_id,
                unit.code,
                unit.name,
                int(employee.position_id or 0),
                employee.position_name,
                "employee_snapshot",
            ),
            existing_user=None,
            login_owner=None,
            proposed_role=role,
        )
        for spec, employee in zip(specs, employees, strict=True)
    ]


def _cleanup_integration_rows(employee_ids: list[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.users WHERE employee_id=ANY(:ids)"), {"ids": employee_ids}
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id=ANY(:ids)"),
            {"ids": employee_ids},
        )


def _cleanup_integration_catalog(
    *,
    role: RoleRecord | None,
    unit: OrgUnitRecord | None,
    position_id: int | None,
    created_role: bool,
    created_unit: bool,
    created_position: bool,
) -> None:
    if not any((created_role, created_unit, created_position)):
        return
    with engine.begin() as conn:
        if created_role and role is not None:
            conn.execute(text("DELETE FROM public.roles WHERE role_id=:id"), {"id": role.role_id})
        if created_unit and unit is not None:
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id=:id"),
                {"id": unit.unit_id},
            )
        if created_position and position_id is not None:
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id=:id"), {"id": position_id}
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_hashes_password_is_idempotent_and_grants_no_permissions(capsys) -> None:
    token = uuid4().hex[:10]
    password = secrets.token_urlsafe(18)
    employee_ids: list[int] = []
    role = None
    unit = None
    position_id = None
    created_role = created_unit = created_position = False
    try:
        with engine.begin() as conn:
            (
                role,
                unit,
                position_id,
                created_role,
                created_unit,
                created_position,
            ) = _load_integration_role_and_unit(conn)
            specs, employees = _create_integration_employees(
                conn, unit_id=unit.unit_id, position_id=position_id, token=token
            )
            employee_ids = [employee.employee_id for employee in employees]
        plan = _ready_integration_plan(specs, employees, role, unit)

        render_plan(plan)
        with engine.begin() as conn:
            created_ids = provision_ready_rows(conn, plan, password)
        assert len(created_ids) == 12

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT user_id,employee_id,login,role_id,password_hash,must_change_password,
                           locked_at,locked_until,locked_reason
                    FROM public.users WHERE user_id=ANY(:ids) ORDER BY user_id
                    """
                ),
                {"ids": created_ids},
            ).mappings().all()
            user_grants = conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.access_grants "
                    "WHERE target_type='USER' AND target_id=ANY(:ids)"
                ),
                {"ids": created_ids},
            ).scalar_one()
            snapshot = load_snapshot(conn)

        assert len(rows) == 12
        assert verify_password(password, str(rows[0]["password_hash"]))
        assert str(rows[0]["password_hash"]) != password
        assert all(int(row["role_id"]) == role.role_id for row in rows)
        assert all(row["must_change_password"] is False for row in rows)
        assert all(row["locked_at"] is None for row in rows)
        assert all(row["locked_until"] is None for row in rows)
        assert all(row["locked_reason"] is None for row in rows)
        assert int(user_grants) == 0
        assert password not in capsys.readouterr().out

        rerun_plan = build_plan_from_snapshot(snapshot, specs, today=date.today())
        assert {row.status for row in rerun_plan} == {ALREADY_EXISTS}
        before = [
            (row["user_id"], row["login"], row["role_id"], row["password_hash"])
            for row in rows
        ]
        with engine.begin() as conn:
            assert provision_ready_rows(conn, rerun_plan, password) == []
        with engine.connect() as conn:
            after_rows = conn.execute(
                text(
                    "SELECT user_id,login,role_id,password_hash FROM public.users "
                    "WHERE user_id=ANY(:ids) ORDER BY user_id"
                ),
                {"ids": created_ids},
            ).mappings().all()
        after = [
            (row["user_id"], row["login"], row["role_id"], row["password_hash"])
            for row in after_rows
        ]
        assert after == before
    finally:
        _cleanup_integration_rows(employee_ids)
        _cleanup_integration_catalog(
            role=role,
            unit=unit,
            position_id=position_id,
            created_role=created_role,
            created_unit=created_unit,
            created_position=created_position,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_transaction_rolls_back_all_rows_on_conflict() -> None:
    token = uuid4().hex[:10]
    password = secrets.token_urlsafe(18)
    employee_ids: list[int] = []
    role = None
    unit = None
    position_id = None
    created_role = created_unit = created_position = False
    try:
        with engine.begin() as conn:
            (
                role,
                unit,
                position_id,
                created_role,
                created_unit,
                created_position,
            ) = _load_integration_role_and_unit(conn)
            specs, employees = _create_integration_employees(
                conn, unit_id=unit.unit_id, position_id=position_id, token=token
            )
            employee_ids = [employee.employee_id for employee in employees]
        plan = _ready_integration_plan(specs, employees, role, unit)
        hash_calls = 0

        def fail_after_first_hash(value: str) -> str:
            nonlocal hash_calls
            hash_calls += 1
            if hash_calls == 2:
                raise RuntimeError("injected hashing failure")
            return provisioner.hash_password(value)

        with pytest.raises(RuntimeError, match="injected hashing failure"):
            with engine.begin() as conn:
                provision_ready_rows(conn, plan, password, hash_fn=fail_after_first_hash)

        with engine.connect() as conn:
            created = conn.execute(
                text("SELECT COUNT(*) FROM public.users WHERE employee_id=ANY(:ids)"),
                {"ids": employee_ids},
            ).scalar_one()
        assert int(created) == 0
    finally:
        _cleanup_integration_rows(employee_ids)
        _cleanup_integration_catalog(
            role=role,
            unit=unit,
            position_id=position_id,
            created_role=created_role,
            created_unit=created_unit,
            created_position=created_position,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_run_apply_orders_diagnostic_prompts_lock_and_final_plan(
    capsys,
    monkeypatch,
) -> None:
    safe_plan = build_plan_from_snapshot(_snapshot(), today=date(2026, 8, 5))
    events: list[str] = []
    plan_connections: list[object] = []

    def fake_build_plan(conn):
        phase = "initial_build" if not plan_connections else "final_build"
        events.append(phase)
        plan_connections.append(conn)
        if phase == "final_build":
            assert conn.get_execution_options()["isolation_level"] == "SERIALIZABLE"
        return safe_plan

    def fake_read_password() -> str:
        events.append("password")
        return "orchestration-secret"

    def fake_render(_plan) -> None:
        events.append("render")

    def fake_input(_prompt: str) -> str:
        events.append("confirm")
        return "APPLY 12 HR USER ACCOUNTS"

    original_lock = provisioner._lock_users_for_apply

    def tracked_lock(conn) -> None:
        events.append("lock")
        original_lock(conn)

    def fake_provision(conn, plan, password, *, lock_users=True, **_kwargs):
        events.append("provision")
        assert conn is plan_connections[1]
        assert plan is safe_plan
        assert password == "orchestration-secret"
        assert lock_users is False
        return [123]

    monkeypatch.setattr(provisioner, "_assert_safe_apply_runtime", lambda: None)
    monkeypatch.setattr(provisioner, "build_plan", fake_build_plan)
    monkeypatch.setattr(provisioner, "_read_password", fake_read_password)
    monkeypatch.setattr(provisioner, "render_plan", fake_render)
    monkeypatch.setattr(provisioner, "_lock_users_for_apply", tracked_lock)
    monkeypatch.setattr(provisioner, "provision_ready_rows", fake_provision)
    monkeypatch.setattr("builtins.input", fake_input)

    assert run_apply(engine) == 0

    assert events == [
        "initial_build",
        "password",
        "render",
        "confirm",
        "lock",
        "final_build",
        "provision",
    ]
    assert plan_connections[0] is not plan_connections[1]
    assert "orchestration-secret" not in capsys.readouterr().out


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_run_apply_changed_or_failed_final_plan_rolls_back(
    monkeypatch,
) -> None:
    safe_plan = build_plan_from_snapshot(_snapshot(), today=date(2026, 8, 5))
    changed_plan = [replace(row, detail="changed after diagnostic") for row in safe_plan]
    provision_called = False
    call_count = 0

    def changed_build_plan(_conn):
        nonlocal call_count
        call_count += 1
        return safe_plan if call_count == 1 else changed_plan

    def forbidden_provision(*_args, **_kwargs):
        nonlocal provision_called
        provision_called = True
        return []

    monkeypatch.setattr(provisioner, "_assert_safe_apply_runtime", lambda: None)
    monkeypatch.setattr(provisioner, "build_plan", changed_build_plan)
    monkeypatch.setattr(provisioner, "_read_password", lambda: "changed-plan-secret")
    monkeypatch.setattr(provisioner, "render_plan", lambda _plan: None)
    monkeypatch.setattr(provisioner, "provision_ready_rows", forbidden_provision)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: "APPLY 12 HR USER ACCOUNTS",
    )

    with pytest.raises(ProvisioningError, match="plan changed"):
        run_apply(engine)

    assert not provision_called
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1 FROM public.users LIMIT 1")).first() is not None

    call_count = 0
    marker_login = f"pytest.final.plan.rollback.{uuid4().hex[:10]}"

    def failing_final_build(conn):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            conn.execute(
                text(
                    """
                    INSERT INTO public.users (full_name,role_id,is_active,login)
                    SELECT 'pytest final planning rollback',role_id,TRUE,:login
                    FROM public.roles
                    ORDER BY role_id
                    LIMIT 1
                    """
                ),
                {"login": marker_login},
            )
            raise RuntimeError("final planning failed")
        return safe_plan

    monkeypatch.setattr(provisioner, "build_plan", failing_final_build)
    try:
        with pytest.raises(RuntimeError, match="final planning failed"):
            run_apply(engine)
        with engine.connect() as conn:
            marker_count = conn.execute(
                text("SELECT COUNT(*) FROM public.users WHERE login=:login"),
                {"login": marker_login},
            ).scalar_one()
        assert int(marker_count) == 0
        assert not provision_called
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.users WHERE login=:login"),
                {"login": marker_login},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_run_apply_final_snapshot_sees_concurrent_login_owner(
    capsys,
    monkeypatch,
) -> None:
    token = uuid4().hex[:10]
    password = "concurrent-snapshot-secret"
    employee_ids: list[int] = []
    conflict_user_id: int | None = None
    role = None
    unit = None
    position_id = None
    created_role = created_unit = created_position = False
    inserted = threading.Event()
    release_writer = threading.Event()
    writer_finished = threading.Event()
    final_pid_ready = threading.Event()
    final_finished = threading.Event()
    provision_called = threading.Event()
    writer_errors: list[BaseException] = []
    writer_result: dict[str, int] = {}
    final_result: dict[str, object] = {}
    writer_thread: threading.Thread | None = None
    final_thread: threading.Thread | None = None
    primary_exception: BaseException | None = None

    def backend_pid(conn) -> int:
        raw = conn.connection.driver_connection
        getter = getattr(raw, "get_backend_pid", None)
        if callable(getter):
            return int(getter())
        info = getattr(raw, "info", None)
        pid = getattr(info, "backend_pid", None)
        if pid is None:
            raise RuntimeError("PostgreSQL driver does not expose backend PID")
        return int(pid)

    ownership = _BackendOwnership(backend_pid)
    event.listen(engine.pool, "checkin", ownership.on_checkin)

    try:
        with engine.begin() as conn:
            (
                role,
                unit,
                position_id,
                created_role,
                created_unit,
                created_position,
            ) = _load_integration_role_and_unit(conn)
            specs, employees = _create_integration_employees(
                conn,
                unit_id=unit.unit_id,
                position_id=position_id,
                token=token,
            )
            employee_ids = [employee.employee_id for employee in employees]

        def real_roster_plan(conn):
            return build_plan_from_snapshot(
                load_snapshot(conn),
                specs,
                today=date.today(),
            )

        def concurrent_writer() -> None:
            conn = None
            transaction = None
            try:
                conn = engine.connect()
                ownership.publish("writer", conn)
                transaction = conn.begin()
                writer_result["user_id"] = int(
                    conn.execute(
                        text(
                            """
                            INSERT INTO public.users (
                                full_name, role_id, unit_id, is_active, login
                            )
                            VALUES (
                                :full_name, :role_id, :unit_id, TRUE, :login
                            )
                            RETURNING user_id
                            """
                        ),
                        {
                            "full_name": f"Concurrent Owner {token}",
                            "role_id": role.role_id,
                            "unit_id": unit.unit_id,
                            "login": specs[0].login,
                        },
                    ).scalar_one()
                )
                inserted.set()
                if not release_writer.wait(timeout=30):
                    raise RuntimeError("concurrent writer was not released")
                transaction.commit()
            except BaseException as exc:
                if transaction is not None and transaction.is_active:
                    transaction.rollback()
                writer_errors.append(exc)
                inserted.set()
            finally:
                if conn is not None:
                    ownership.release("writer", conn)
                    conn.close()
                writer_finished.set()

        def read_password() -> str:
            return password

        original_lock = provisioner._lock_users_for_apply

        def identify_then_lock(conn) -> None:
            ownership.publish("final", conn)
            final_pid_ready.set()
            original_lock(conn)

        original_provision = provisioner.provision_ready_rows

        def tracked_provision(*args, **kwargs):
            provision_called.set()
            return original_provision(*args, **kwargs)

        def run_final_apply() -> None:
            try:
                final_result["return_code"] = run_apply(engine)
            except BaseException as exc:
                final_result["exception"] = exc
            finally:
                final_finished.set()

        monkeypatch.setattr(provisioner, "_assert_safe_apply_runtime", lambda: None)
        monkeypatch.setattr(provisioner, "build_plan", real_roster_plan)
        monkeypatch.setattr(provisioner, "_read_password", read_password)
        monkeypatch.setattr(provisioner, "_lock_users_for_apply", identify_then_lock)
        monkeypatch.setattr(provisioner, "provision_ready_rows", tracked_provision)
        monkeypatch.setattr(
            "builtins.input",
            lambda _prompt: "APPLY 12 HR USER ACCOUNTS",
        )

        writer_thread = threading.Thread(target=concurrent_writer, daemon=False)
        writer_thread.start()
        assert inserted.wait(timeout=10), "writer INSERT did not complete"
        if writer_errors:
            raise writer_errors[0]
        writer_owner = ownership.snapshot("writer")
        assert writer_owner.owns_connection
        assert writer_owner.connection is not None
        assert not writer_owner.connection.closed
        assert writer_owner.pid == backend_pid(writer_owner.connection)

        final_thread = threading.Thread(target=run_final_apply, daemon=False)
        final_thread.start()
        assert final_pid_ready.wait(timeout=10), "final backend PID was not published"
        final_owner = ownership.snapshot("final")
        assert final_owner.owns_connection
        assert final_owner.connection is not None
        assert not final_owner.connection.closed
        final_pid = int(final_owner.pid or 0)
        assert final_pid == backend_pid(final_owner.connection)

        deadline = time.monotonic() + 10
        waiting_lock_observed = False
        last_locks: list[dict[str, object]] = []
        with engine.connect() as observer:
            while time.monotonic() < deadline:
                waiting_lock_observed = (
                    observer.execute(
                        text(
                            """
                            SELECT 1
                            FROM pg_locks
                            WHERE pid = :pid
                              AND locktype = 'relation'
                              AND relation = 'public.users'::regclass
                              AND mode = 'AccessExclusiveLock'
                              AND granted = FALSE
                            LIMIT 1
                            """
                        ),
                        {"pid": final_pid},
                    ).first()
                    is not None
                )
                if waiting_lock_observed:
                    break
                last_locks = [
                    dict(row)
                    for row in observer.execute(
                        text(
                            """
                            SELECT locktype, mode, granted, relation::regclass::text AS relation
                            FROM pg_locks
                            WHERE pid = :pid
                            ORDER BY locktype, mode, granted
                            """
                        ),
                        {"pid": final_pid},
                    ).mappings()
                ]
                if final_finished.wait(timeout=0.05):
                    break

        assert waiting_lock_observed, (
            "final backend did not wait for AccessExclusiveLock on public.users; "
            f"pid={final_pid}, locks={last_locks}, final_result={final_result}"
        )
        assert not writer_finished.is_set(), "writer finished before lock wait was observed"

        release_writer.set()
        assert writer_finished.wait(timeout=10), "writer did not finish after commit release"
        assert final_finished.wait(timeout=10), "final apply did not finish after writer commit"
        writer_thread.join(timeout=1)
        final_thread.join(timeout=1)
        assert not writer_thread.is_alive()
        assert not final_thread.is_alive()
        assert not ownership.snapshot("writer").owns_connection
        assert not ownership.snapshot("final").owns_connection
        if writer_errors:
            raise writer_errors[0]

        final_exception = final_result.get("exception")
        if not isinstance(final_exception, ProvisioningError):
            if isinstance(final_exception, BaseException):
                raise final_exception
            pytest.fail(f"final apply unexpectedly returned: {final_result}")
        assert "final plan" in str(final_exception)
        assert not provision_called.is_set()

        conflict_user_id = writer_result["user_id"]
        with engine.connect() as conn:
            conflict = conn.execute(
                text("SELECT login FROM public.users WHERE user_id=:id"),
                {"id": conflict_user_id},
            ).scalar_one()
            created_for_roster = conn.execute(
                text("SELECT COUNT(*) FROM public.users WHERE employee_id=ANY(:ids)"),
                {"ids": employee_ids},
            ).scalar_one()
        assert conflict == specs[0].login
        assert int(created_for_roster) == 0
        assert password not in capsys.readouterr().out
    except BaseException as exc:
        primary_exception = exc
    finally:
        def cleanup_conflict_user() -> None:
            nonlocal conflict_user_id
            if conflict_user_id is None:
                conflict_user_id = writer_result.get("user_id")
            if conflict_user_id is not None:
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM public.users WHERE user_id=:id"),
                        {"id": conflict_user_id},
                    )

        def cleanup_catalog() -> None:
            _cleanup_integration_catalog(
                role=role,
                unit=unit,
                position_id=position_id,
                created_role=created_role,
                created_unit=created_unit,
                created_position=created_position,
            )

        _finish_concurrency_orchestration(
            release_writer=release_writer,
            writer_thread=writer_thread,
            final_thread=final_thread,
            ownership=ownership,
            termination_channel_factory=lambda: _open_direct_termination_channel(engine),
            writer_errors=writer_errors,
            final_result=final_result,
            primary_exception=primary_exception,
            remove_listener=lambda: event.remove(
                engine.pool,
                "checkin",
                ownership.on_checkin,
            ),
            cleanup_conflict=cleanup_conflict_user,
            cleanup_employees=lambda: _cleanup_integration_rows(employee_ids),
            cleanup_catalog=cleanup_catalog,
            join_timeout=10,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_load_snapshot_ignores_inactive_grant_and_access_role(
    monkeypatch,
) -> None:
    token = uuid4().hex[:10]
    role_code = f"pytest_hr_reg_{token}"
    inactive_access_code = f"PYTEST_INACTIVE_{token}"
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            grantor_id = conn.execute(
                text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")
            ).scalar_one_or_none()
            if grantor_id is None:
                pytest.skip("grantor user is required")
            role_id = int(
                conn.execute(
                    text(
                        "INSERT INTO public.roles (code,name) "
                        "VALUES (:code,:name) RETURNING role_id"
                    ),
                    {"code": role_code, "name": "pytest HR baseline role"},
                ).scalar_one()
            )
            inactive_access_role_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.access_roles (
                            code,name,description,access_level,level_rank,is_system,is_active
                        )
                        VALUES (
                            :code,:name,'pytest inactive','OBSERVER',10,FALSE,FALSE
                        )
                        RETURNING access_role_id
                        """
                    ),
                    {"code": inactive_access_code, "name": "pytest inactive permission"},
                ).scalar_one()
            )
            observer_id = int(
                conn.execute(
                    text(
                        "SELECT access_role_id FROM public.access_roles "
                        "WHERE code='ACCESS_OBSERVER' AND is_active=TRUE"
                    )
                ).scalar_one()
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id,target_type,target_id,granted_by_user_id,reason
                    )
                    VALUES
                        (:observer,'ROLE',:role_id,:grantor,'pytest baseline'),
                        (:inactive_role,'ROLE',:role_id,:grantor,'pytest inactive role')
                    """
                ),
                {
                    "observer": observer_id,
                    "inactive_role": inactive_access_role_id,
                    "role_id": role_id,
                    "grantor": int(grantor_id),
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id,target_type,target_id,active_flag,
                        granted_by_user_id,reason,revoked_at
                    )
                    VALUES (
                        :observer,'ROLE',:role_id,FALSE,
                        :grantor,'pytest inactive grant',statement_timestamp()
                    )
                    """
                ),
                {
                    "observer": observer_id,
                    "role_id": role_id,
                    "grantor": int(grantor_id),
                },
            )
            monkeypatch.setattr(provisioner, "ORDINARY_HR_ROLE_CODE", role_code)

            snapshot = load_snapshot(conn)

            assert len(snapshot.roles) == 1
            assert snapshot.roles[0].active_grant_codes == ("ACCESS_OBSERVER",)
        finally:
            transaction.rollback()
