"""Discovery shims must resolve to the project's authoritative skill files."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    'high-school-math-teacher-agent', 'learning-task-designer', 'math-solver',
    'math-error-diagnosis', 'solution-refiner', 'draft-coach',
    'learning-evidence-bridge', 'remedial-lesson-planner',
    'lesson-materials-builder',
}


class HarnessEntryTests(unittest.TestCase):
    def test_entries_are_discoverable_and_point_to_existing_sources(self):
        for folder in ('.agents/skills', '.claude/skills'):
            root = ROOT / folder
            self.assertEqual({p.parent.name for p in root.glob('*/SKILL.md')}, SKILLS)
            for name in SKILLS:
                with self.subTest(folder=folder, skill=name):
                    entry = (root / name / 'SKILL.md').read_text(encoding='utf-8')
                    self.assertTrue(entry.startswith(f'---\nname: {name}\ndescription: '))
                    self.assertIn(f'`{name}/SKILL.md`', entry)
                    self.assertTrue((ROOT / name / 'SKILL.md').is_file())


if __name__ == '__main__':
    unittest.main()
