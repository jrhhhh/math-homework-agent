import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from app.server import Application, Store
from app.teaching_loop import TeachingLoop, _evidence


class TeachingLoopTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.sqlite')
        self.loop = TeachingLoop(self.store)
        self.task = self.loop.create({'title': '方程任务', 'items': [
            {'problem': '解 x+1=2。', 'objective': '等式两边同时减去1'}]})
        self.item = self.task['items'][0]

    def tearDown(self):
        self.temp.cleanup()

    def submit(self, solution='x=3', mode='check'):
        opened = self.loop.open_item(self.task['id'], self.item['id'])
        rid = self.store.submit(opened['session_id'], {'problem': self.item['problem'], 'solution': solution, 'mode': mode})
        return rid

    def result(self, rid, judgment='incorrect', state='ready'):
        self.store.update(rid, state, {'status': state, 'output': {'reply': '检查结果', 'result': {
            'judgment': judgment, 'first_error': {'step': 1, 'quote': 'x=3', 'reason': '3+1不等于2'} if judgment=='incorrect' else None}}})

    def plan(self):
        rid = self.loop.report(self.task['id'])['items'][0]['submission_id']
        self.loop.generator = lambda prompt: {'raw': json.dumps({'draft_markdown': '# 补救课\n依据提交 '+rid+'。让学生用逆运算修订原题。'}, ensure_ascii=False)}
        return self.loop.plan(self.task['id'])

    def test_published_problem_is_fixed_and_open_reuses_bound_session(self):
        first = self.loop.open_item(self.task['id'], self.item['id'])
        self.assertEqual(first, self.loop.open_item(self.task['id'], self.item['id']))
        self.assertEqual(first['problem'], '解 x+1=2。')
        self.assertEqual(self.loop.report(self.task['id'])['counts']['unsubmitted'], 1)

    def test_latest_revision_invalidates_old_diagnosis_and_plan(self):
        old = self.submit(); self.result(old)
        report = self.loop.report(self.task['id']); plan = self.plan()
        self.assertEqual(report['counts']['incorrect'], 1)
        new = self.submit('x=1')
        current = self.loop.report(self.task['id'])
        self.assertEqual(current['counts']['pending'], 1)
        self.assertEqual(current['items'][0]['submission_id'], new)
        self.assertNotEqual(current['evidence_version'], plan['evidence_version'])
        self.assertTrue(self.loop.get(self.task['id'])['plan']['stale'])
        self.result(new, 'correct')
        self.assertEqual(self.loop.report(self.task['id'])['counts']['correct'], 1)
        self.assertEqual(self.loop.report(self.task['id'])['counts']['incorrect'], 0)

    def test_old_evidence_cannot_publish_followup(self):
        rid=self.submit(); self.result(rid); plan=self.plan()
        payload={'title':'再练习','items':[{'problem':'解 x+2=4。','objective':'逆运算'}],
                 'parent_id':self.task['id'],'evidence_version':plan['evidence_version']}
        followup=self.loop.create(payload)
        self.assertEqual(followup['parent_id'], self.task['id'])
        self.submit('x=1')
        with self.assertRaisesRegex(ValueError, '证据已经变化'):self.loop.create(payload)

    def test_changed_problem_or_grade_or_source_does_not_inherit_correctness(self):
        for changed in ({'problem':'解 x+2=4。'},{'grade_level':'大学'},{'source':'assistant'}):
            with self.subTest(changed=changed):
                sid=self.loop.open_item(self.task['id'], self.item['id'])['session_id']
                data={'problem':self.item['problem'],'solution':'x=1','mode':'check'}|changed
                rid=self.store.submit(sid, data);self.result(rid,'correct')
                self.assertEqual(self.loop.report(self.task['id'])['counts']['binding_changed'],1)

    def test_failure_hint_and_answer_only_never_become_process_judgment(self):
        rid=self.submit();self.result(rid,state='gate_failed')
        self.assertEqual(self.loop.report(self.task['id'])['counts']['unavailable'],1)
        with self.assertRaises(ValueError):self.loop.plan(self.task['id'])
        rid=self.submit(mode='hint');self.result(rid,'correct')
        self.assertEqual(self.loop.report(self.task['id'])['counts']['needs_input'],1)
        sid=self.loop.open_item(self.task['id'],self.item['id'])['session_id']
        rid=self.store.submit(sid,{'problem':self.item['problem'],'solution':'x=1','mode':'answer_check'},True);self.result(rid,'correct')
        self.assertEqual(self.loop.report(self.task['id'])['counts']['answer_only'],1)

    def test_model_task_draft_is_validated_and_does_not_publish_itself(self):
        prompts=[]
        self.loop.generator=lambda prompt:prompts.append(prompt) or {'raw':json.dumps({'title':'草案','items':[{'problem':'解 x+2=4。','objective':'逆运算','success_criteria':'同一运算并验根'}]})}
        draft=self.loop.design({'title':'草案','objective':'逆运算'})
        self.assertEqual(len(self.loop.list()),1)
        self.assertIn('尚未进行数学核验',draft['review_status'])
        self.assertIn('学习任务设计',prompts[0])
        self.loop.generator=lambda prompt:{'raw':'{"title":"坏草案","items":[]}'}
        with self.assertRaises(ValueError):self.loop.design({'title':'草案','objective':'逆运算'})

    def test_changed_evidence_during_generation_rejects_plan(self):
        rid=self.submit();self.result(rid)
        def generator(prompt):
            self.submit('x=1')
            return {'raw':json.dumps({'draft_markdown':'依据 '+rid+' 让学生修订。'})}
        self.loop.generator=generator
        with self.assertRaisesRegex(ValueError,'生成期间'):self.loop.plan(self.task['id'])
        self.assertIsNone(self.loop.get(self.task['id'])['plan'])

    def test_plan_must_cite_actual_current_submission(self):
        rid=self.submit();self.result(rid)
        self.loop.generator=lambda prompt:{'raw':'{"draft_markdown":"所有学生都不会逆运算。"}'}
        with self.assertRaisesRegex(ValueError,'缺少当前提交编号'):self.loop.plan(self.task['id'])

    def test_one_learner_revisions_count_as_one_task_item(self):
        for solution in ('x=3','x=2','x=1'):
            rid=self.submit(solution);self.result(rid, 'correct' if solution=='x=1' else 'incorrect')
        report=self.loop.report(self.task['id'])
        self.assertEqual(sum(report['counts'].values()),1)
        self.assertEqual(report['items'][0]['revision'],3)

    def test_async_student_diagnosis_returns_to_teacher_evidence(self):
        def runner(data):
            return {'status':'ready','output':{'reply':'检查逆运算。','result':{'judgment':'incorrect','first_error':{'step':1,'quote':'x=3','reason':'代回不成立'}}}}
        app=Application(self.store,runner=runner)
        try:
            sid=app.teaching.open_item(self.task['id'],self.item['id'])['session_id']
            rid=app.submit(sid,{'problem':self.item['problem'],'solution':'x=3','mode':'check'})
            deadline=time.monotonic()+3
            while self.store.get(rid)['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
            report=app.teaching.report(self.task['id'])
            self.assertEqual(report['items'][0]['submission_id'],rid)
            self.assertEqual(report['counts']['incorrect'],1)
        finally:app.close()


if __name__=='__main__':unittest.main()
