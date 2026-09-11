"""Regression tests for Git's commit-hook environment; no remote operations."""

import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class UpdateSubmodulesTests(unittest.TestCase):
    def test_hook_index_is_isolated_only_for_submodule_checks(self):
        main = runpy.run_path(str(Path(__file__).with_name("update-submodules.py")))["main"]
        real_git = main.__globals__["git"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "child"
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".git/modules").mkdir()
            subprocess.run(
                ["git", "init", "-q", "--separate-git-dir", str(root / ".git/modules/child"), str(child)],
                check=True,
            )
            (root / ".gitmodules").write_text('[submodule "child"]\npath = child\n')
            calls = []

            def checked_git(*args, **kwargs):
                if args[0] in {"submodule", "add"}:
                    calls.append((args, kwargs, os.environ.get("GIT_INDEX_FILE")))
                    return subprocess.CompletedProcess(args, 0)
                if args == ("rev-parse", "--show-toplevel"):
                    kwargs["cwd"] = root
                return real_git(*args, **kwargs)

            with patch.dict(os.environ, {"GIT_INDEX_FILE": ".git/index"}), patch.dict(
                main.__globals__, {"git": checked_git}
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(), 0)
                self.assertEqual(len(calls), 3)
                for _, kwargs, index in calls:
                    self.assertIsNone(kwargs.get("env"))
                    self.assertEqual(index, ".git/index")
                calls.clear()
                (child / "uncommitted.txt").write_text("preserve this work\n")
                self.assertEqual(main(), 1)
                self.assertEqual(calls, [])
                self.assertTrue((child / "uncommitted.txt").exists())

    def test_git_errors_remain_visible(self):
        git = runpy.run_path(str(Path(__file__).with_name("update-submodules.py")))["git"]
        with patch("subprocess.run") as run:
            git("status", cwd=Path.cwd(), capture_output=True)
            self.assertEqual(run.call_args.kwargs["stdout"], subprocess.PIPE)
            self.assertNotIn("stderr", run.call_args.kwargs)
            self.assertNotIn("capture_output", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
