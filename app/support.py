"""Append-only help ledger and immutable pre-submission support snapshots."""
import hashlib
import json
import re
import unicodedata
import uuid


def canonical_problem(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).rstrip('。.!！')


def problem_key(data):
    return hashlib.sha256((data.get('grade_level', '高中')+'\0'+canonical_problem(data.get('problem',''))).encode()).hexdigest()


class SupportLedger:
    def __init__(self, store):
        self.store=store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS learning_support (id TEXT PRIMARY KEY, session_id TEXT, problem_key TEXT, kind TEXT, reference TEXT, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(session_id,kind,reference))')
            db.execute('CREATE TABLE IF NOT EXISTS submission_support (submission_id TEXT PRIMARY KEY, snapshot TEXT)')

    def append(self, db, sid, data, kind, reference, detail=''):
        db.execute('INSERT OR IGNORE INTO learning_support(id,session_id,problem_key,kind,reference,detail) VALUES (?,?,?,?,?,?)',
                   (uuid.uuid4().hex,sid,problem_key(data),kind,reference,detail))

    def before_submit(self, db, sid, rid, data):
        # Requests themselves disqualify an independent check, even if inference later fails.
        kind={'hint':'hint_requested','full_correction':'solution_requested','solve':'solution_requested','refine':'explanation_requested'}.get(data['mode'])
        if kind:self.append(db,sid,data,kind,rid)
        rows=[dict(row) for row in db.execute('SELECT id,kind,reference,detail,created FROM learning_support WHERE session_id=? AND problem_key=? ORDER BY rowid',(sid,problem_key(data)))]
        # Old databases did not record exposure. Never invent a clean history for them.
        legacy=db.execute('SELECT COUNT(*) FROM submissions s LEFT JOIN submission_support p ON p.submission_id=s.id WHERE s.session_id=? AND s.id!=? AND p.submission_id IS NULL',(sid,rid)).fetchone()[0]
        answer=any(row['kind'] in ('solution_requested','solution_available') for row in rows)
        condition='answer_seen_or_requested' if answer else 'unknown_legacy' if legacy or any(row['kind']=='legacy_unknown' for row in rows) else 'supported' if rows else 'no_recorded_support'
        snapshot={'condition':condition,'events':rows,'scope':'只描述本题当前练习会话已记录的帮助；不判断其他练习会话或系统外的帮助。'}
        db.execute('INSERT INTO submission_support VALUES (?,?)',(rid,json.dumps(snapshot,ensure_ascii=False)))

    def feedback_available(self, db, rid, state, result):
        if state!='ready' or not result or result.get('status')!='ready':return
        row=db.execute('SELECT * FROM submissions WHERE id=?',(rid,)).fetchone()
        if not row:return
        data=json.loads(row['data'])
        kind='hint_available' if data['mode']=='hint' else 'solution_available' if data['mode'] in ('solve','full_correction') else 'feedback_available'
        self.append(db,row['session_id'],data,kind,rid)

    def snapshot(self, rid):
        with self.store.connect() as db:
            row=db.execute('SELECT snapshot FROM submission_support WHERE submission_id=?',(rid,)).fetchone()
        return json.loads(row['snapshot']) if row else {'condition':'unknown_legacy','events':[],'scope':'旧记录未保存帮助条件。'}

    def record(self, sid, payload):
        kind=payload.get('kind')
        if kind not in ('teacher_guidance','external_help','interactive_opened','guidance_opened'):
            raise ValueError('帮助记录类型无效。')
        detail=payload.get('detail','')
        problem=payload.get('problem')
        if not isinstance(detail,str) or len(detail)>2000 or not isinstance(problem,str) or not problem.strip() or len(problem)>10000:
            raise ValueError('请提供任务原题和不超过 2000 字的帮助说明。')
        with self.store.connect() as db:
            if not db.execute('SELECT id FROM sessions WHERE id=?',(sid,)).fetchone():raise ValueError('练习不存在。')
            self.append(db,sid,{'problem':problem,'grade_level':'高中'},kind,uuid.uuid4().hex,detail.strip())
        return {'recorded':True,'kind':kind}

    def inherit(self, old_sid, new_sid, problem):
        """A rebound task keeps recorded exposure to its original question."""
        data={'problem':problem,'grade_level':'高中'}
        with self.store.connect() as db:
            rows=db.execute('SELECT * FROM learning_support WHERE session_id=? AND problem_key=?',(old_sid,problem_key(data))).fetchall()
            for row in rows:self.append(db,new_sid,data,row['kind'],row['reference'],row['detail'])
            legacy=db.execute('SELECT 1 FROM submissions s LEFT JOIN submission_support p ON p.submission_id=s.id WHERE s.session_id=? AND p.submission_id IS NULL LIMIT 1',(old_sid,)).fetchone()
            if legacy:self.append(db,new_sid,data,'legacy_unknown',old_sid,'旧会话帮助条件未完整记录')

    def history(self,sid,problem):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('SELECT kind,detail,reference,created FROM learning_support WHERE session_id=? AND problem_key=? ORDER BY rowid',(sid,problem_key({'problem':problem,'grade_level':'高中'})))]
