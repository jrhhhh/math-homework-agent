"""A portable import contains the resources the teaching router refers to."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.package_harness_skill import package, SKILLS, ROOT


class HarnessPackageTests(unittest.TestCase):
    def test_import_bundle_contains_router_and_skill_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'teacher.zip'
            package(output)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                prefix = 'high-school-math-teacher-agent/'
                names = set(archive.namelist())
                for skill in SKILLS:
                    name = prefix + skill + '/SKILL.md'
                    self.assertIn(name, names)
                    self.assertEqual(archive.read(name), (ROOT / skill / 'SKILL.md').read_bytes())
                for resource in ('AGENTS.md', 'docs/teaching-loop.md',
                                 'lesson-materials-builder/assets/base.pptx',
                                 'lesson-materials-builder/scripts/build_pptx.py',
                                 'lesson-materials-builder/references/classroom-design.md'):
                    self.assertIn(prefix + resource, names)
                router = archive.read(prefix + 'SKILL.md').decode('utf-8')
                self.assertIn('工作台及数据库不包含', router)
                self.assertNotIn('../docs/teaching-loop.md', router)
                self.assertTrue(all(not n.startswith('/') and '..' not in Path(n).parts for n in names))


if __name__ == '__main__':
    unittest.main()
