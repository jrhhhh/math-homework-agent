import json
import math
from pathlib import Path
import tempfile
import unittest
from app.server import Store
from app.teaching_loop import TeachingLoop
from app.math_widgets import evaluate


class LearningPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db.sqlite');self.loop=TeachingLoop(self.store)
        self.task=self.loop.create({'title':'逆运算','items':[{'problem':'解 x+1=2。','objective':'逆运算','success_criteria':'写出等式两边的同一运算并验根','interactive_template':'quadratic'}]})
        self.item=self.task['items'][0];self.sid=self.loop.open_item(self.task['id'],self.item['id'])['session_id']
    def tearDown(self):self.tmp.cleanup()
    def submit(self,mode='check',solution='x=1',sid=None,problem='解 x+1=2。'):
        return self.store.submit(sid or self.sid,{'problem':problem,'solution':solution,'mode':mode},True)
    def ready(self,rid):self.store.update(rid,'ready',{'status':'ready','output':{'reply':'检查结果','result':{'judgment':'correct','first_error':None}}})
    def test_first_attempt_and_feedback_supported_revision_are_distinct(self):
        first=self.submit();self.assertEqual(self.store.get(first)['support']['condition'],'no_recorded_support');self.ready(first)
        second=self.submit();self.assertEqual(self.store.get(second)['support']['condition'],'supported')
        self.assertEqual(self.store.get(first)['support']['condition'],'no_recorded_support')
    def test_hint_requested_and_full_solution_are_recorded_before_inference(self):
        hinted=self.submit('hint');self.assertEqual(self.store.get(hinted)['support']['condition'],'supported')
        answer=self.submit('full_correction');self.assertEqual(self.store.get(answer)['support']['condition'],'answer_seen_or_requested')
        next_try=self.submit();self.assertEqual(self.store.get(next_try)['support']['condition'],'answer_seen_or_requested')
    def test_guidance_and_widget_opening_disqualify_independent_check(self):
        for kind in ('guidance_opened','interactive_opened','external_help','teacher_guidance'):
            self.store.support.record(self.sid,{'kind':kind,'problem':self.item['problem'],'detail':'已接受帮助'})
        rid=self.submit();self.assertEqual(len(self.store.get(rid)['support']['events']),4)
        self.assertEqual(self.store.get(rid)['support']['condition'],'supported')
    def followup(self,problem='解 x+2=4。'):
        return {'title':'独立复核','parent_id':self.task['id'],'evidence_version':self.loop.report(self.task['id'])['evidence_version'],
                'assessment_kind':'independent_check','target_item_id':self.item['id'],'items':[{'problem':problem,'objective':self.item['objective'],'success_criteria':self.item['success_criteria']}]}
    def test_independent_check_requires_new_problem_and_same_success_criteria(self):
        for question in ('解 x+1=2。',' 解 x + 1 = 2. '):
            with self.assertRaisesRegex(ValueError,'不同原题'):self.loop.create(self.followup(question))
        payload=self.followup();payload['items'][0]['success_criteria']='算出答案'
        with self.assertRaisesRegex(ValueError,'成功标准'):self.loop.create(payload)
        with self.assertRaisesRegex(ValueError,'关联'):self.loop.create({'title':'复核','assessment_kind':'independent_check','items':self.task['items']})
    def test_fresh_independent_check_has_no_old_help_and_reports_condition(self):
        self.submit('hint')
        task=self.loop.create(self.followup());item=task['items'][0];sid=self.loop.open_item(task['id'],item['id'])['session_id']
        rid=self.submit(sid=sid,problem=item['problem']);self.ready(rid)
        report=self.loop.report(task['id']);self.assertTrue(report['items'][0]['independent_check_passed'])
        self.submit(sid=sid,problem=item['problem']);self.assertFalse(self.loop.report(task['id'])['items'][0]['independent_check_passed'])
    def test_learning_path_preserves_goal_criteria_and_attempt_conditions(self):
        rid=self.submit();self.ready(rid)
        path=self.loop.learning_path(self.task['id'],self.item['id'])
        self.assertEqual([scene['id'] for scene in path['scenes']],['attempt','explain','interactive','independent_check'])
        self.assertEqual(path['scenes'][0]['success_criteria'],self.item['success_criteria'])
        self.assertEqual(path['attempts'][0]['support']['condition'],'no_recorded_support')
    def test_events_for_another_problem_do_not_create_false_help(self):
        self.store.support.record(self.sid,{'kind':'external_help','problem':'另一道题','detail':'帮助'})
        self.assertEqual(self.store.get(self.submit())['support']['condition'],'no_recorded_support')
    def test_legacy_rows_remain_unknown_instead_of_clean(self):
        rid=self.submit()
        with self.store.connect() as db:db.execute('DELETE FROM submission_support WHERE submission_id=?',(rid,))
        self.assertEqual(self.store.get(self.submit())['support']['condition'],'unknown_legacy')

    def test_sibling_retest_and_duplicate_items_cannot_be_fresh(self):
        self.loop.create(self.followup())
        with self.assertRaisesRegex(ValueError,'不同原题'):self.loop.create(self.followup())
        payload=self.followup('解 x+3=5。');payload['items']*=2
        with self.assertRaisesRegex(ValueError,'不同原题'):self.loop.create(payload)
    def test_rebinding_original_question_preserves_exposure(self):
        self.submit('full_correction')
        self.submit(problem='修改成另一题')
        sid=self.loop.open_item(self.task['id'],self.item['id'])['session_id']
        self.assertNotEqual(sid,self.sid)
        rid=self.submit(sid=sid)
        self.assertEqual(self.store.get(rid)['support']['condition'],'answer_seen_or_requested')
    def test_generated_tasks_require_observable_success_criteria(self):
        self.loop.generator=lambda _: {'raw':json.dumps({'title':'草案','items':[{'problem':'x=1?','objective':'逆运算'}]})}
        with self.assertRaisesRegex(ValueError,'success_criteria'):self.loop.design({'title':'任务','objective':'逆运算'})


class MathWidgetsTest(unittest.TestCase):
    def test_circle_identity_and_quadrant_known_values(self):
        for angle in range(-360,361,15):
            result=evaluate({'template':'unit_circle','angle':angle});self.assertAlmostEqual(result['identity'],1,places=12)
        self.assertAlmostEqual(evaluate({'template':'unit_circle','angle':90})['point'][1],1)
        self.assertAlmostEqual(evaluate({'template':'unit_circle','angle':180})['point'][0],-1)
    def test_quadratic_vertex_and_degenerate_linear_case(self):
        result=evaluate({'template':'quadratic','a':2,'b':-4,'c':1});self.assertEqual(result['vertex'],[1,-1])
        result=evaluate({'template':'quadratic','a':0,'b':2,'c':1});self.assertIsNone(result['vertex'])
        for x,y in result['points']:self.assertAlmostEqual(y,2*x+1)
    def test_secant_difference_quotient_and_zero_limit(self):
        for x0 in (-2,0,1,2):
            for h in (-1,-.001,0,.001,1):
                result=evaluate({'template':'derivative','x0':x0,'h':h})
                if h:self.assertAlmostEqual(result['slope'],((x0+h)**2-x0*x0)/h,places=9)
                else:self.assertEqual(result['slope'],2*x0);self.assertEqual(result['mode'],'tangent_limit')
    def test_nonfinite_invalid_types_and_unsupported_templates_rejected(self):
        for value in (math.nan,math.inf,True,'1',None,10):
            with self.assertRaises(ValueError):evaluate({'template':'quadratic','a':value})
        with self.assertRaises(ValueError):evaluate({'template':'generated_js'})


if __name__=='__main__':unittest.main()
