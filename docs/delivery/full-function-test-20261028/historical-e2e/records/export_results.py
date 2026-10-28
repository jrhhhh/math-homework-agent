"""Save synthetic end-to-end test evidence from the isolated local service."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
import json,sqlite3,subprocess
root=Path(__file__).resolve().parents[1]
def get(path):
 with urlopen('http://127.0.0.1:8768'+path,timeout=10) as response:return json.load(response)
settings=get('/api/settings');sessions=get('/api/sessions');tasks=get('/api/teaching');lessons=get('/api/lessons');jobs=get('/api/jobs')
out={'captured_at':datetime.now(timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'scope':'合成教师与学生数据；真实工作台和模型，不代表真实学生或教学效果。',
 'backend':settings,'jobs':jobs,'tasks':[{'task':get('/api/teaching/'+t['id']),'evidence':get('/api/teaching/'+t['id']+'/evidence')} for t in tasks],
 'sessions':[{'session':s,'submissions':get('/api/sessions/'+s['id'])} for s in sessions],
 'lessons':[get('/api/lessons/'+lesson['id']) for lesson in lessons]}
Path(__file__).with_name('完整运行快照.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source=sqlite3.connect(root/'workbench.sqlite3');destination=sqlite3.connect(root/'records/隔离数据库快照.sqlite3')
try:source.backup(destination)
finally:destination.close();source.close()
print(json.dumps({'tasks':len(tasks),'sessions':len(sessions),'lessons':len(lessons),'jobs':len(jobs),'unfinished':sum(j['state']!='completed' for j in jobs)},ensure_ascii=False))
