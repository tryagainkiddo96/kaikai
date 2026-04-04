from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kai_agent.desktop_tools import DesktopTools
from kai_agent.tool_policy import ToolPolicy


class ToolPolicyTests(unittest.TestCase):
    def test_default_mode_is_power_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy = ToolPolicy(Path(tmp_dir))
            status = policy.status()
            self.assertTrue(status["ok"])
            self.assertEqual(status["mode"], "power-user")

    def test_balanced_mode_blocks_write_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy = ToolPolicy(Path(tmp_dir))
            result = policy.set_mode("balanced")
            self.assertTrue(result["ok"])
            decision = policy.evaluate("write_file", {"path": "demo.txt", "chars_written": 4})
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["policy_mode"], "balanced")

    def test_power_user_blocks_destructive_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy = ToolPolicy(Path(tmp_dir))
            decision = policy.evaluate(
                "run_shell",
                {
                    "command": "Remove-Item demo.txt",
                    "action_level": 5,
                    "tags": ["destructive", "system-changing"],
                },
            )
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["policy_mode"], "power-user")


class DesktopToolsPolicyIntegrationTests(unittest.TestCase):
    def test_balanced_mode_blocks_write_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            tools = DesktopTools(workspace)
            update = json.loads(tools.set_policy_mode("balanced"))
            self.assertTrue(update["ok"])
            result = json.loads(tools.write_file("demo.txt", "hello"))
            self.assertFalse(result["ok"])
            self.assertTrue(result["blocked"])
            self.assertEqual(result["policy_mode"], "balanced")

    def test_power_user_allows_safe_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            tools = DesktopTools(workspace)
            result = json.loads(tools.run_shell("Write-Output 'hello from kai'"))
            self.assertEqual(result["action"], "run_shell")
            self.assertIn(result["returncode"], (0, 1))
            self.assertFalse(result.get("blocked", False))


if __name__ == "__main__":
    unittest.main()
