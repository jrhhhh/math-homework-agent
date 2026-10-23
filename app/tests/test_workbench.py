import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.core import gate, normalize, prompt_for, route, run
from app.server import Store


class RoutingTest(unittest.TestCase):
    def test_explicit_solve_cannot_replace_student_work(self):
        data = normalize({'problem': '解 x+1=2', 'solution': 'x=1', 'mode': 'solve'})
        self.assertEqual(route(data)['skill'], 'math-error-diagnosis')

    def test_draft_check_intent_uses_diagnosis(self):
        data = normalize({'problem': '解 x+1=2', 'draft': 'x=3', 'mode': 'check'})
        self.assertEqual(route(data)['skill'], 'math-error-diagnosis')

    def test_layout_does_not_require_problem(self):
        self.assertEqual(route(normalize({'draft': '左边密集，右边留白', 'mode': 'draft'}))['skill'], 'draft-coach')

    def test_attachments_are_accepted_in_any_mode_but_never_enter_the_prompt(self):
        data = normalize({'problem': '解 x+1=2', 'solution': 'x=1', 'mode': 'check',
                          'attachments': [{'name': 'work.png', 'base64': 'iVBORw0KGgo='}]})
        self.assertEqual(data['attachments'][0]['name'], 'work.png')
        prompt = prompt_for(data, route(data))
        self.assertNotIn('"attachments"', prompt)
        self.assertNotIn('iVBORw0KGgo=', prompt)

    def test_draft_attachment_never_enters_the_model_prompt(self):
        data = normalize({'draft': '左栏第1题，右栏第2题；中间有划改。', 'mode': 'draft',
                          'attachments': [{'name': 'draft.pdf', 'base64': 'JVBERi0='}]})
        prompt = prompt_for(data, route(data))
        self.assertNotIn('"attachments"', prompt)
        self.assertNotIn('JVBERi0=', prompt)

    def test_multiple_problem_markers_partition_before_card(self):
        data=normalize({'draft':'左栏第1题，右栏第2题，中间有竖线','mode':'draft'})
        self.assertEqual(route(data)['action'],'partition')

    def test_ordinary_function_parentheses_are_not_question_markers(self):
        data=normalize({'draft':'左边写 f(1)，右边写 f(2)，中间有留白','mode':'draft'})
        self.assertEqual(route(data)['action'],'draft')

    def test_assistant_solution_not_student(self):
        self.assertIsNone(route(normalize({'problem': 'x=1?', 'solution': 'x=1', 'source': 'assistant'}))['skill'])

    def test_missing_student_work_clarifies(self):
        self.assertIsNone(route(normalize({'problem': '解 x+1=2'}))['skill'])

    def test_only_problem_solves_when_requested(self):
        self.assertEqual(route(normalize({'problem': '解 x+1=2', 'mode': 'solve'}))['skill'], 'math-solver')

    def test_refinement_is_a_staged_fourth_skill_route(self):
        data=normalize({'problem':'求 x²-5x+6=0 的根。','solution':'用求根公式：x=(5±√1)/2，所以x1=3，x2=2。','mode':'refine'})
        self.assertEqual(route(data)['action'],'diagnose_then_refine')

    def test_refiner_runs_only_after_correct_diagnosis(self):
        data=normalize({'problem':'求 x²-5x+6=0 的根。','solution':'用求根公式：x=(5±√1)/2，所以x1=3，x2=2。','mode':'refine'})
        diagnosis={'judgment':'correct','first_error':None,'minimal_fix':'','hint':'','evidence':['原式分解与验根成立']}
        card=json.loads((Path(__file__).resolve().parents[2]/'solution-refiner/example/correct_card.json').read_text(encoding='utf-8'))
        outputs=iter([{'raw':json.dumps({'reply':'过程正确。','result':diagnosis},ensure_ascii=False)},
                      {'raw':json.dumps({'reply':'我已经运行脚本，沿用上一轮真实结果。','result':card},ensure_ascii=False)}])
        result=run(data,generator=lambda _:next(outputs))
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['stage'],'solution-refiner')
        self.assertEqual(len(result['attempts']),3)
        self.assertEqual(result['attempts'][-1]['gates'][0]['gate'],'solution-refiner-handoff')
        self.assertTrue(result['handoff']['eligible'])
        self.assertNotIn('沿用',result['output']['reply'])
        self.assertIn('模型判断',result['output']['reply'])

    def test_refiner_is_blocked_when_diagnosis_finds_error(self):
        data=normalize({'problem':'解 x+1=2','solution':'x=3','mode':'refine'})
        diagnosis={'judgment':'incorrect','first_error':{'step':1,'quote':'x=3','reason':'代回不成立'},'minimal_fix':'x=1','hint':'','evidence':['3+1≠2']}
        calls=[]
        result=run(data,generator=lambda _:calls.append(1) or {'raw':json.dumps({'reply':'代回检查。','result':diagnosis},ensure_ascii=False)})
        self.assertEqual(result['status'],'diagnosis_required')
        self.assertEqual(result['stage'],'diagnosis')
        self.assertEqual(len(calls),1)


class GateTest(unittest.TestCase):
    def setUp(self):
        self.data = normalize({'problem': '解 x+1=2', 'solution': 'x=3\n所以得解', 'mode': 'check'})
        self.routing = route(self.data)

    def card(self):
        return {'reply': '第一步有误。', 'result': {'judgment': 'incorrect', 'first_error': {'step': 1, 'quote': 'x=3', 'reason': '代回不成立'}, 'minimal_fix': 'x=1', 'hint': '', 'evidence': ['3+1≠2']}}

    def test_fabricated_quote_rejected(self):
        card = self.card();card['result']['first_error']['quote'] = '未提供的步骤'
        self.assertEqual(gate(card, self.data, self.routing)[0]['exit_code'], 1)

    def test_right_quote_wrong_line_rejected(self):
        card = self.card();card['result']['first_error']['step'] = 2
        self.assertEqual(gate(card, self.data, self.routing)[0]['exit_code'], 1)

    def test_correction_cannot_be_hidden_in_hint_fields(self):
        data = dict(self.data, mode='hint')
        self.assertEqual(gate(self.card(), data, self.routing)[0]['exit_code'], 1)

    def test_answer_only_mode_cannot_claim_process_error(self):
        self.assertEqual(gate(self.card(),dict(self.data,mode='answer_check'),self.routing)[0]['exit_code'],1)

    def test_repair_gets_actual_errors(self):
        prompts = []
        def fake(prompt):
            prompts.append(prompt)
            return {'raw': 'not JSON' if len(prompts) == 1 else json.dumps(self.card())}
        result = run(self.data, generator=fake)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(result['attempts']), 2)
        self.assertIn('校验失败', prompts[1])
        self.assertEqual(result['attempts'][0]['gates'][0]['exit_code'], 1)

    def test_bounded_retry_and_no_failed_delivery(self):
        result = run(self.data, generator=lambda _: {'raw': '{}'}, max_repairs=2)
        self.assertEqual(result['status'], 'gate_failed')
        self.assertEqual(len(result['attempts']), 3)

    def test_baseline_never_repairs(self):
        result = run(self.data, arm='baseline', generator=lambda _: {'raw': '{}'})
        self.assertEqual(len(result['attempts']), 1)

    def test_native_solver_gate_replayed(self):
        root=Path(__file__).resolve().parents[2]
        card=json.loads((root/'math-solver/example/sqrt_equation_solved.json').read_text(encoding='utf-8'))
        data=normalize({'problem':'解 √(x+2)=x', 'mode':'solve'})
        logs=gate({'reply':'x=2','result':card}, data, route(data))
        self.assertEqual(logs[0]['exit_code'],0)

    def test_external_math_rejects_failed_candidate(self):
        card=self.card();card['tool_requests']=[{'source_quote':'解 x+1=2', 'request':{'kind':'substitute','left':'x+1','right':'2','values':['3']}}]
        self.assertEqual(gate(card,self.data,self.routing)[-1]['exit_code'],1)

    def test_external_math_records_real_residual(self):
        card=self.card();card['tool_requests']=[{'source_quote':'解 x+1=2', 'request':{'kind':'substitute','left':'x+1','right':'2','values':['1']}}]
        record=gate(card,self.data,self.routing)[-1]
        self.assertEqual(record['exit_code'],0)
        self.assertEqual(record['record']['checks'][0]['residual'],'0')

    def test_hint_never_executes_candidate_tool_request(self):
        card=self.card();card['tool_requests']=[{'source_quote':'解 x+1=2','request':{'kind':'substitute','left':'x+1','right':'2','values':['1']}}]
        log=gate(card,dict(self.data,mode='hint'),self.routing)[-1]
        self.assertEqual(log['exit_code'],1)
        self.assertNotIn('command',log)

    def test_requested_tool_cannot_be_replaced_by_self_check(self):
        data=dict(self.data,verification_requested=True)
        self.assertEqual(gate(self.card(),data,self.routing)[-1]['exit_code'],1)

    def test_auto_partition_uses_partition_gate_instead_of_card_gate(self):
        root=Path(__file__).resolve().parents[2]
        card=json.loads((root/'draft-coach/example/partition_sheet.json').read_text(encoding='utf-8'))
        card['block_source']='student_text'
        data=normalize({'draft':'第1题在左栏，第2题在右栏','mode':'draft'})
        logs=gate({'reply':'先确认各块归属。','result':card},data,route(data))
        self.assertEqual(logs[0]['gate'],'scripts/partition_check.py')
        self.assertEqual(logs[0]['exit_code'],0)


class RevisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'data.db');self.sid=self.store.create_session()

    def tearDown(self):
        self.tmp.cleanup()

    def test_revision_invalidates_old_even_if_old_finishes_later(self):
        one=self.store.submit(self.sid, {'problem':'x+1=2','solution':'x=3'})
        two=self.store.submit(self.sid, {'problem':'x+1=2','solution':'x=1'})
        self.store.update(one,'ready', {'status':'ready'})
        self.assertFalse(self.store.get(one)['is_current'])
        self.assertTrue(self.store.get(two)['is_current'])
        self.assertNotEqual(self.store.get(one)['version'], self.store.get(two)['version'])
        self.assertEqual(self.store.get(one)['data']['solution'], 'x=3')

    def test_hint_persists_until_explicit_switch(self):
        self.store.submit(self.sid, {'problem':'x+1=2','solution':'x=3','mode':'hint'})
        two=self.store.submit(self.sid, {'problem':'x+1=2','solution':'x=1','mode':'check'})
        self.assertEqual(self.store.get(two)['data']['mode'], 'hint')
        three=self.store.submit(self.sid, {'problem':'x+1=2','solution':'x=1','mode':'check'}, allow_mode_change=True)
        self.assertEqual(self.store.get(three)['data']['mode'], 'check')


class StoreMigrationTest(unittest.TestCase):
    def test_existing_session_table_gets_archived_column(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, created TEXT)')
            db.commit()
            db.close()
            store = Store(path)
            sid = store.create_session()
            row = store.list_sessions()[0]
            self.assertEqual(row['id'], sid)
            self.assertEqual(row['archived'], 0)
            store.set_archived(sid, True)
            self.assertEqual(store.list_sessions()[0]['archived'], 1)
            store.delete_session(sid)
            self.assertEqual(store.list_sessions(), [])


if __name__ == '__main__':
    unittest.main()
