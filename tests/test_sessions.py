import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science import sessions
from codex_science.sessions import (
    ActivationState,
    RuntimePin,
    activation_path,
    claim_activation,
    new_activation_generation,
    parse_runtime_pin,
    read_activation_generation,
    read_activation_state,
    remove_activation,
    session_key,
    write_activation_state,
)

GEN = "a" * 64
PIN = RuntimePin("1.2.3", "b" * 40, "c" * 64)


class SessionsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.marker = self.root / "science-sessions" / "marker"

    def write_raw(self, payload) -> None:
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        self.marker.write_text(text, encoding="utf-8")


class SessionKeyTests(unittest.TestCase):
    def test_key_is_sha256_of_session_id(self) -> None:
        self.assertEqual(session_key("s"), hashlib.sha256(b"s").hexdigest())

    def test_generation_changes_key_and_is_deterministic(self) -> None:
        self.assertEqual(session_key("s", GEN), session_key("s", GEN))
        self.assertNotEqual(session_key("s", GEN), session_key("s"))
        self.assertNotEqual(session_key("s", GEN), session_key("s", "b" * 64))

    def test_empty_session_id_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            session_key("")

    def test_malformed_generation_rejected(self) -> None:
        for bad in ("", "A" * 64, "a" * 63, "a" * 65, "g" * 64):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "64-character lowercase hex"):
                    session_key("s", bad)

    def test_new_generation_is_valid_and_unique(self) -> None:
        first, second = new_activation_generation(), new_activation_generation()
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        self.assertNotEqual(first, second)

    def test_activation_path_layout(self) -> None:
        self.assertEqual(
            activation_path(Path("data"), "s"),
            Path("data") / "science-sessions" / session_key("s"),
        )


class RuntimePinTests(unittest.TestCase):
    def test_valid_pin_roundtrip(self) -> None:
        self.assertEqual(parse_runtime_pin(PIN.as_dict()), PIN)

    def test_invalid_pins_rejected(self) -> None:
        good = PIN.as_dict()
        cases = [
            None,
            "x",
            [],
            {**good, "runtime_version": ""},
            {**good, "runtime_version": "-1"},
            {**good, "runtime_version": "1" * 129},
            {**good, "runtime_version": 1},
            {**good, "runtime_commit": "b" * 39},
            {**good, "runtime_commit": "B" * 40},
            {**good, "receipt_sha256": "c" * 63},
            {**good, "receipt_sha256": None},
            {k: v for k, v in good.items() if k != "runtime_commit"},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(parse_runtime_pin(case))

    def test_version_length_boundary(self) -> None:
        self.assertIsNotNone(parse_runtime_pin({**PIN.as_dict(), "runtime_version": "1" * 128}))


class ReadActivationTests(SessionsTestBase):
    def test_missing_file(self) -> None:
        self.assertIsNone(read_activation_state(self.marker))
        self.assertIsNone(read_activation_generation(self.marker))

    def test_schema_v1_default(self) -> None:
        self.write_raw({"generation": GEN})
        self.assertEqual(read_activation_state(self.marker), ActivationState(GEN, None))
        self.assertEqual(read_activation_generation(self.marker), GEN)

    def test_schema_v2_with_pin(self) -> None:
        self.write_raw({"schema_version": 2, "generation": GEN, "runtime_pin": PIN.as_dict()})
        self.assertEqual(read_activation_state(self.marker), ActivationState(GEN, PIN))

    def test_rejected_markers(self) -> None:
        cases = {
            "v2 without pin": {"schema_version": 2, "generation": GEN},
            "v2 invalid pin": {"schema_version": 2, "generation": GEN, "runtime_pin": {}},
            "unknown schema": {"schema_version": 3, "generation": GEN},
            "bad generation": {"generation": "xyz"},
            "non-string generation": {"generation": 5},
            "no generation": {},
            "not an object": [GEN],
            "invalid json": "{nope",
        }
        for name, payload in cases.items():
            with self.subTest(name):
                self.write_raw(payload)
                self.assertIsNone(read_activation_state(self.marker))

    def test_non_utf8_rejected(self) -> None:
        self.marker.parent.mkdir(parents=True)
        self.marker.write_bytes(b"\xff\xfe\x00")
        self.assertIsNone(read_activation_state(self.marker))

    def test_schema_type_is_validated_without_refresh_or_marker_mutation(self) -> None:
        for schema in ([], {}, None, "1", True, False, 1.0, 2.0, 0):
            with self.subTest(schema=schema):
                self.write_raw({"schema_version": schema, "generation": GEN, "runtime_pin": PIN.as_dict()})
                before = self.marker.read_bytes()
                os.utime(self.marker, (1000, 1000))
                self.assertIsNone(read_activation_state(self.marker, refresh=True))
                self.assertIsNone(read_activation_generation(self.marker))
                self.assertEqual(before, self.marker.read_bytes())
                self.assertEqual(1000, int(self.marker.stat().st_mtime))

    def test_size_limit_boundary(self) -> None:
        base = json.dumps({"generation": GEN, "pad": ""})
        limit = sessions.MAX_MARKER_BYTES
        self.write_raw(json.dumps({"generation": GEN, "pad": "x" * (limit - len(base))}))
        self.assertEqual(self.marker.stat().st_size, limit)
        self.assertIsNotNone(read_activation_state(self.marker))
        self.write_raw(json.dumps({"generation": GEN, "pad": "x" * (limit - len(base) + 1)}))
        self.assertIsNone(read_activation_state(self.marker))

    def test_symlink_and_directory_rejected(self) -> None:
        self.write_raw({"generation": GEN})
        link = self.marker.with_name("link")
        link.symlink_to(self.marker)
        self.assertIsNone(read_activation_state(link))
        self.assertIsNone(read_activation_state(self.marker.parent))

    def test_refresh_updates_mtime_only_when_requested(self) -> None:
        self.write_raw({"generation": GEN})
        os.utime(self.marker, (1000, 1000))
        read_activation_state(self.marker)
        self.assertEqual(int(self.marker.stat().st_mtime), 1000)
        read_activation_state(self.marker, refresh=True)
        self.assertGreater(self.marker.stat().st_mtime, 1000)

    def test_refresh_not_applied_to_rejected_marker(self) -> None:
        self.write_raw({"generation": "bad"})
        os.utime(self.marker, (1000, 1000))
        self.assertIsNone(read_activation_state(self.marker, refresh=True))
        self.assertEqual(int(self.marker.stat().st_mtime), 1000)


class WriteActivationTests(SessionsTestBase):
    def test_write_then_read_with_private_modes(self) -> None:
        write_activation_state(self.marker, ActivationState(GEN, PIN))
        self.assertEqual(read_activation_state(self.marker), ActivationState(GEN, PIN))
        self.assertEqual(self.marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.marker.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual([p.name for p in self.marker.parent.iterdir()], ["marker"])
        self.assertEqual(json.loads(self.marker.read_text())["schema_version"], 2)

    def test_invalid_states_rejected_without_writing(self) -> None:
        bad_pin = RuntimePin("1.0", "short", "c" * 64)
        for state in (
            ActivationState("bad"),
            ActivationState(GEN, None),
            ActivationState(GEN, bad_pin),
        ):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "valid pinned activation state"):
                    write_activation_state(self.marker, state)
                self.assertFalse(self.marker.parent.exists())

    def test_symlinked_parent_rejected(self) -> None:
        real = self.root / "real"
        real.mkdir()
        (self.root / "science-sessions").symlink_to(real)
        with self.assertRaisesRegex(OSError, "not private regular storage"):
            write_activation_state(self.marker, ActivationState(GEN, PIN))
        self.assertEqual(list(real.iterdir()), [])

    def test_failed_write_keeps_old_marker_and_cleans_temp(self) -> None:
        write_activation_state(self.marker, ActivationState(GEN, PIN))
        before = self.marker.read_bytes()
        with mock.patch.object(sessions.os, "replace", side_effect=OSError("boom")):
            with self.assertRaisesRegex(OSError, "boom"):
                write_activation_state(self.marker, ActivationState("d" * 64, PIN))
        self.assertEqual(self.marker.read_bytes(), before)
        self.assertEqual([p.name for p in self.marker.parent.iterdir()], ["marker"])


class ClaimActivationTests(SessionsTestBase):
    def test_new_claim_requires_pin(self) -> None:
        with self.assertRaisesRegex(ValueError, "verified runtime pin"):
            claim_activation(self.marker, None)
        self.assertFalse(self.marker.exists())

    def test_new_claim_creates_pinned_generation(self) -> None:
        state = claim_activation(self.marker, PIN)
        self.assertEqual(state.runtime_pin, PIN)
        self.assertRegex(state.generation, r"^[0-9a-f]{64}$")
        self.assertEqual(read_activation_state(self.marker), state)

    def test_existing_claim_preserved_even_with_other_pin(self) -> None:
        first = claim_activation(self.marker, PIN)
        other = RuntimePin("9.9", "d" * 40, "e" * 64)
        self.assertEqual(claim_activation(self.marker, other), first)
        self.assertEqual(claim_activation(self.marker, None), first)
        self.assertEqual(read_activation_state(self.marker), first)

    def test_legacy_marker_upgraded_keeping_generation(self) -> None:
        self.write_raw({"generation": GEN})
        state = claim_activation(self.marker, PIN)
        self.assertEqual(state, ActivationState(GEN, PIN))
        self.assertEqual(read_activation_state(self.marker), state)

    def test_legacy_marker_without_pin_stays_legacy(self) -> None:
        self.write_raw({"generation": GEN})
        self.assertEqual(claim_activation(self.marker, None), ActivationState(GEN, None))
        self.assertNotIn("schema_version", json.loads(self.marker.read_text()))

    def test_invalid_existing_marker_refused_and_untouched(self) -> None:
        self.write_raw("{nope")
        with self.assertRaisesRegex(ValueError, "existing activation marker is invalid"):
            claim_activation(self.marker, PIN)
        self.assertEqual(self.marker.read_text(), "{nope")


class LockTests(SessionsTestBase):
    def test_lock_file_private(self) -> None:
        claim_activation(self.marker, PIN)
        lock = self.marker.with_name(".marker.lock")
        self.assertEqual(lock.stat().st_mode & 0o777, 0o600)

    def test_busy_lock_times_out(self) -> None:
        with sessions._activation_lock(self.marker):
            with mock.patch.object(sessions.time, "sleep"):
                with self.assertRaisesRegex(TimeoutError, "activation state is busy"):
                    with sessions._activation_lock(self.marker, timeout=0.0):
                        self.fail("lock acquired twice")

    def test_lock_released_after_exit(self) -> None:
        with sessions._activation_lock(self.marker):
            pass
        with sessions._activation_lock(self.marker, timeout=0.0):
            pass

    def test_lock_released_after_exception(self) -> None:
        with self.assertRaises(RuntimeError):
            with sessions._activation_lock(self.marker):
                raise RuntimeError("x")
        with sessions._activation_lock(self.marker, timeout=0.0):
            pass

    def test_symlinked_lock_parent_rejected(self) -> None:
        real = self.root / "real"
        real.mkdir()
        (self.root / "science-sessions").symlink_to(real)
        with self.assertRaisesRegex(OSError, "not private regular storage"):
            with sessions._activation_lock(self.marker):
                self.fail("lock acquired")

    def test_symlinked_lock_file_rejected(self) -> None:
        self.marker.parent.mkdir(parents=True)
        target = self.root / "target"
        target.write_text("keep")
        self.marker.with_name(".marker.lock").symlink_to(target)
        with self.assertRaises(OSError):
            with sessions._activation_lock(self.marker):
                self.fail("lock acquired")
        self.assertEqual(target.read_text(), "keep")


class RemoveActivationTests(SessionsTestBase):
    def test_removes_matching_generation(self) -> None:
        state = claim_activation(self.marker, PIN)
        self.assertTrue(remove_activation(self.marker, state.generation))
        self.assertFalse(self.marker.exists())

    def test_mismatched_generation_keeps_marker(self) -> None:
        state = claim_activation(self.marker, PIN)
        self.assertFalse(remove_activation(self.marker, "f" * 64))
        self.assertEqual(read_activation_state(self.marker), state)

    def test_malformed_expected_generation_refused_before_locking(self) -> None:
        state = claim_activation(self.marker, PIN)
        with mock.patch.object(sessions, "_activation_lock") as lock:
            self.assertFalse(remove_activation(self.marker, "nope"))
        lock.assert_not_called()
        self.assertTrue(self.marker.exists())
        self.assertEqual(read_activation_state(self.marker), state)

    def test_missing_marker_returns_false(self) -> None:
        self.assertFalse(remove_activation(self.marker, GEN))

    def test_invalid_marker_not_removed(self) -> None:
        self.write_raw("{nope")
        self.assertFalse(remove_activation(self.marker, GEN))
        self.assertTrue(self.marker.exists())

    def test_marker_vanishing_before_unlink_returns_false(self) -> None:
        self.write_raw({"generation": GEN})
        with mock.patch.object(Path, "unlink", side_effect=FileNotFoundError):
            self.assertFalse(remove_activation(self.marker, GEN))


if __name__ == "__main__":
    unittest.main()
