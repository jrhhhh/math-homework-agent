from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "lesson-materials-builder",
    "math-solver",
    "math-error-diagnosis",
    "solution-refiner",
    "draft-coach",
    "learning-task-designer",
    "learning-evidence-bridge",
    "remedial-lesson-planner",
)


class TeacherAgentContractTest(unittest.TestCase):
    def test_orchestrator_links_every_project_skill(self):
        entry = ROOT / "high-school-math-teacher-agent" / "SKILL.md"
        text = entry.read_text(encoding="utf-8")
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertTrue((ROOT / skill / "SKILL.md").is_file())
                self.assertIn(f"`{skill}`", text)

    def test_cross_skill_workflows_preserve_gates_and_privacy(self):
        text = (ROOT / "high-school-math-teacher-agent" / "SKILL.md").read_text(encoding="utf-8")
        for contract in ("完整诊断", "等待用户确认", "课后补救", "去身份化", "不证明课件中的数学结论正确"):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

    def test_root_agent_entry_points_to_teacher_orchestrator(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("high-school-math-teacher-agent/SKILL.md", text)
        self.assertIn("Lesson Materials Builder", text)


if __name__ == "__main__":
    unittest.main()
