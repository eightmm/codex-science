import copy
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import create_checkpoint, validate_checkpoint

DIGEST = "b" * 64


def passed_review(**overrides):
    review = {"reviewer": "r", "verdict": "passed", "artifact_ref": "review.json",
              "recorded_at": "2026-01-01T00:00:00Z", "artifact_sha256": DIGEST,
              "independence_attested": True}
    review.update(overrides)
    return review


def stopped(cp, **changes):
    cp.update(state="abandoned", current_step=None, next_action="", **changes)
    cp["steps"][0]["status"] = "pending"
    return cp


def completed(cp):
    cp.update(state="complete", current_step=None, next_action="", review_receipt=passed_review())
    cp["steps"][0]["status"] = "completed"
    cp["done_criteria"][0].update(status="satisfied", evidence_refs=["e.txt"], evidence_sha256={"e.txt": DIGEST})
    return cp


class ValidateCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = create_checkpoint(
            Path(cls.temp.name) / "run", goal="g", deliverable="d", done_criteria=["c"],
            steps=[("s", "step")], next_action="work", session_key="a" * 64,
            rigor_tier="standard", budget_policy="tier-v1")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def cp(self, mutate=None):
        checkpoint = copy.deepcopy(self.base)
        if mutate:
            mutate(checkpoint)
        return checkpoint

    def reject(self, pattern, mutate):
        with self.assertRaisesRegex(ValueError, pattern):
            validate_checkpoint(self.cp(mutate))

    def test_base_and_completed_fixtures_are_valid(self):
        validate_checkpoint(self.cp())
        validate_checkpoint(self.cp(completed))

    def test_schema_version_session_key_and_budget_rejections(self):
        def key(value):
            return lambda c: c.update(session_key=value)
        def limits(attempts, rounds):
            return lambda c: c["run_budget"].update(max_failed_attempts_per_class=attempts, max_review_rounds=rounds)
        cases = [
            ("unsupported checkpoint schema version", lambda c: c.update(schema_version=5)),
            ("unsupported checkpoint schema version", lambda c: c.update(schema_version=0)),
            ("session_key must be a 64-character", key("A" * 64)),
            ("session_key must be a 64-character", key("a" * 63)),
            ("session_key must be a 64-character", key(None)),
            ("below tier-v1 defaults", limits(1, 1)),
            ("max_failed_attempts_per_class must be", limits(0, 1)),
            ("run_budget tier must match rigor tier", lambda c: c["run_budget"].update(tier="full")),
            ("run_budget policy or tier is invalid", lambda c: c["run_budget"].update(policy_version=2)),
            ("run_budget is invalid", lambda c: c.update(schema_version=3)),
            ("run_budget is invalid", lambda c: c["run_budget"].pop("deadline_at")),
        ]
        for pattern, mutate in cases:
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(ValueError, pattern):
                    validate_checkpoint(self.cp(mutate))

    def test_full_tier_floor_is_three_attempts_and_two_rounds(self):
        def full(attempts, rounds):
            def mutate(c):
                c["rigor"] = {"tier": "full", "history": [{"tier": "full", "at": "t", "reason": "r"}]}
                c["run_budget"].update(tier="full", max_failed_attempts_per_class=attempts, max_review_rounds=rounds)
            return mutate
        validate_checkpoint(self.cp(full(3, 2)))
        for attempts, rounds in ((2, 2), (3, 1)):
            with self.subTest(attempts=attempts, rounds=rounds):
                self.reject("below tier-v1 defaults", full(attempts, rounds))

    def test_review_rounds_requirements(self):
        round_ = {"id": "r1", "started_at": "t", "receipt_ref": "x.json", "receipt_sha256": DIGEST}
        validate_checkpoint(self.cp(lambda c: c.update(review_rounds=[round_])))
        self.reject("budgeted checkpoints require review_rounds", lambda c: c.pop("review_rounds"))
        self.reject("budgeted checkpoints require review_rounds", lambda c: c.update(review_rounds=None))
        self.reject("review_rounds entry is invalid", lambda c: c.update(review_rounds=["x"]))
        self.reject("review_rounds entry is invalid", lambda c: c.update(review_rounds=[{**round_, "extra": 1}]))
        self.reject("review round ids must be unique", lambda c: c.update(review_rounds=[round_, dict(round_)]))
        self.reject("review round id", lambda c: c.update(review_rounds=[{**round_, "id": ""}]))
        self.reject("review receipt hash is invalid", lambda c: c.update(review_rounds=[{**round_, "receipt_sha256": "B" * 64}]))
        self.reject("review receipt hash is invalid", lambda c: c.update(review_rounds=[{**round_, "receipt_sha256": 7}]))

    def test_review_rounds_without_run_budget_is_rejected(self):
        self.reject("review_rounds requires run_budget", lambda c: c.pop("run_budget"))

    def test_partial_termination_rejections(self):
        def terminate(**changes):
            def mutate(c):
                stopped(c, termination_reason="budget_exhausted")
                c["termination"] = {"kind": "partial", "reason_code": "budget_exhausted", "exhausted_limit": "attempts",
                                    "recorded_at": "t", "artifact_ref": "p.json", "artifact_sha256": DIGEST}
                c["termination"].update(changes)
            return mutate
        validate_checkpoint(self.cp(terminate()))
        self.reject("partial termination is invalid", terminate(kind="other"))
        self.reject("partial termination is invalid", terminate(reason_code="other"))
        self.reject("partial termination is invalid", lambda c: (terminate()(c), c.update(state="active")))
        self.reject("partial termination is invalid", lambda c: (terminate()(c), c.pop("run_budget"), c.pop("review_rounds")))
        self.reject("termination artifact hash is invalid", terminate(artifact_sha256="x"))
        self.reject("termination exhausted_limit", terminate(exhausted_limit=""))
        self.reject("termination_reason must match", lambda c: (terminate()(c), c.update(termination_reason="deadline_passed")))

    def test_per_status_requirements(self):
        cases = [
            ("an active checkpoint requires next_action", lambda c: c.update(next_action="  ")),
            ("approval_required requires pending_decisions", lambda c: c.update(state="approval_required")),
            ("waiting_external requires wait metadata", lambda c: c.update(state="waiting_external")),
            ("blocked requires blocker", lambda c: c.update(state="blocked", blocker=" ")),
            ("abandoned requires termination_reason",
             lambda c: stopped(c)),
        ]
        for pattern, mutate in cases:
            with self.subTest(pattern=pattern):
                self.reject(pattern, mutate)

    def test_terminal_states_cannot_retain_gates(self):
        def abandoned(**changes):
            def mutate(c):
                stopped(c, termination_reason="stop")
                c.update(changes)
            return mutate
        validate_checkpoint(self.cp(abandoned()))
        self.reject("abandoned cannot have a current step",
                    lambda c: (abandoned(current_step="s")(c), c["steps"][0].update(status="in_progress")))
        self.reject("abandoned cannot have a current step", abandoned(next_action="more"))
        self.reject("abandoned cannot retain a gate", abandoned(blocker="b"))
        self.reject("abandoned cannot retain a gate", abandoned(pending_decisions=[{"question": "q", "reason": "r"}]))

    def test_complete_requires_completed_steps(self):
        self.reject("complete requires every step to be completed", lambda c: (completed(c), c["steps"][0].update(status="pending")))
        self.reject("complete cannot have a current step", lambda c: (completed(c), c.update(next_action="more")))
        self.reject("complete cannot retain a gate", lambda c: (completed(c), c.update(blocker="b")))

    def test_verified_completion_rejections(self):
        def tweak(**review):
            return lambda c: (completed(c), c["review_receipt"].update(review))
        self.reject("every criterion to be satisfied", lambda c: (completed(c), c["done_criteria"][0].update(status="pending")))
        self.reject("requires a passed independent review", lambda c: (completed(c), c.update(review_receipt=None)))
        self.reject("requires a passed independent review", tweak(verdict="failed"))
        self.reject("requires a passed independent review", tweak(independence_attested=False))

    def test_completion_pending_requires_verified_completion(self):
        def pending(c):
            c["outer_goal"] = {"mode": "native", "phase": "completion_pending", "task_key": "c" * 64, "receipt": None}
        validate_checkpoint(self.cp(lambda c: (completed(c), c.update(state="active", next_action="x"),
                                               pending(c), c["steps"][0].update(status="completed"))))
        self.reject("verified completion requires every step to be completed", pending)
        self.reject("verified completion requires every criterion to be satisfied",
                    lambda c: (pending(c), c["steps"][0].update(status="completed"), c.update(current_step=None)))
        self.reject("completion_pending requires active state", lambda c: (pending(c), c.update(state="blocked", blocker="b")))

    def test_review_receipt_shape_rejections(self):
        def receipt(**changes):
            return lambda c: c.update(review_receipt=passed_review(**changes))
        validate_checkpoint(self.cp(receipt()))
        self.reject("review_receipt must be null or an object", lambda c: c.update(review_receipt="x"))
        self.reject("review reviewer", receipt(reviewer=""))
        self.reject("review artifact_sha256 must be a SHA-256", receipt(artifact_sha256="short"))
        self.reject("review verdict must be passed or failed", receipt(verdict="maybe"))
        self.reject("review independence_attested must be boolean", receipt(independence_attested="yes"))

    def test_wait_and_termination_reason_shape(self):
        wait = {"reason": "r", "next_action": "n", "terminal_rule": "t", "recorded_at": "t", "poll_interval_seconds": 5}
        validate_checkpoint(self.cp(lambda c: c.update(state="waiting_external", wait=wait)))
        self.reject("wait must be null or an object", lambda c: c.update(wait="x"))
        self.reject("wait terminal_rule", lambda c: c.update(wait={**wait, "terminal_rule": ""}))
        self.reject("wait poll_interval_seconds", lambda c: c.update(wait={**wait, "poll_interval_seconds": 0}))
        self.reject("termination_reason must be a string", lambda c: c.update(termination_reason=None))

    def test_missing_fields_are_listed(self):
        self.reject("missing checkpoint fields: goal", lambda c: c.pop("goal"))
        self.reject("missing checkpoint fields: continuation_count", lambda c: c.pop("continuation_count"))
        self.reject("missing checkpoint fields: revision", lambda c: c.pop("revision"))


if __name__ == "__main__":
    unittest.main()
