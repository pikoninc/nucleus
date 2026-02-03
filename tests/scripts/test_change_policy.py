import unittest


class TestChangePolicy(unittest.TestCase):
    def _eval(self, changed_files, pr_body=None, work_tasks_files=None):
        # Import lazily so tests clearly fail if module is missing.
        from scripts.check_change_policy import evaluate_change_policy

        return evaluate_change_policy(
            changed_files=changed_files,
            pr_body=pr_body,
            work_tasks_files=work_tasks_files or {},
        )

    def test_docs_only_changes_skip_guard(self) -> None:
        rc, _msg = self._eval(
            changed_files=[
                "README.md",
                "specs/framework/00_overview.md",
                "work/plans/some.md",
                ".github/workflows/ci.yml",
            ]
        )
        self.assertEqual(rc, 0)

    def test_code_change_without_tests_fails(self) -> None:
        rc, msg = self._eval(changed_files=["nucleus/core/kernel.py"])
        self.assertEqual(rc, 1)
        self.assertIn("tests", msg.lower())

    def test_code_change_with_tests_passes(self) -> None:
        rc, _msg = self._eval(changed_files=["nucleus/core/kernel.py", "tests/nucleus/test_safety_and_trace.py"])
        self.assertEqual(rc, 0)

    def test_override_via_pr_body_passes(self) -> None:
        pr_body = "\n".join(
            [
                "## Summary",
                "Refactor internals only.",
                "",
                "Test-Impact: none",
                "Test-Impact-Reason: No input/output changes; refactor only.",
            ]
        )
        rc, _msg = self._eval(changed_files=["tools/fs/_path.py"], pr_body=pr_body)
        self.assertEqual(rc, 0)

    def test_override_requires_reason(self) -> None:
        pr_body = "\n".join(["Test-Impact: none"])
        rc, msg = self._eval(changed_files=["tools/fs/_path.py"], pr_body=pr_body)
        self.assertEqual(rc, 1)
        self.assertIn("reason", msg.lower())

    def test_override_via_work_task_passes(self) -> None:
        task_md = "\n".join(
            [
                "# Task",
                "",
                "TestImpact: none",
                "TestImpactReason: No input/output changes; rename only.",
            ]
        )
        rc, _msg = self._eval(
            changed_files=["nucleus/cli/nuc.py", "work/tasks/TASK-0001.md"],
            work_tasks_files={"work/tasks/TASK-0001.md": task_md},
        )
        self.assertEqual(rc, 0)

    def test_override_work_task_requires_reason(self) -> None:
        task_md = "\n".join(["TestImpact: none"])
        rc, msg = self._eval(
            changed_files=["nucleus/cli/nuc.py", "work/tasks/TASK-0001.md"],
            work_tasks_files={"work/tasks/TASK-0001.md": task_md},
        )
        self.assertEqual(rc, 1)
        self.assertIn("reason", msg.lower())


if __name__ == "__main__":
    unittest.main()

