/* Local task handoff. No class-level identities or cross-device access are implied. */
let activeTask=null, activeEvidence=null, followupSource=null, taskWorking=false,taskLoadToken=0;
const evidenceNames={unsubmitted:'未提交',pending:'诊断中',unavailable:'诊断未完成/未通过',binding_changed:'原题或来源已变化',needs_input:'待补充过程',correct:'当前过程正确',incorrect:'当前过程有错',gap:'存在论证缺口',answer_only:'仅有答案'};
function addTaskItem(item={}){
  const area=$('task-item-editor');if(area.children.length>=10)return;
  const card=node('div',undefined,'task-edit-item');
  const problemLabel=node('label','原题');const problem=node('textarea');problem.rows=3;problem.required=true;problem.maxLength=10000;problem.className='task-problem';problem.value=item.problem||'';problemLabel.append(problem);
  const goalLabel=node('label','本题目标');const goal=node('input');goal.required=true;goal.maxLength=1000;goal.className='task-goal';goal.value=item.objective||$('task-objective').value.slice(0,1000);goalLabel.append(goal);
  const remove=node('button','删除本题','text-button');remove.type='button';remove.onclick=()=>card.remove();card.append(problemLabel,goalLabel,remove);area.append(card);
}
function taskBusy(value,message=''){
  taskWorking=value;for(const id of ['task-design','task-publish','task-add-item','task-plan','task-refresh','task-select','task-to-lesson','task-followup'])$(id).disabled=value;
  $('task-status').textContent=message;
  if(!value)$('task-plan').disabled=!activeEvidence||!activeEvidence.items.some(row=>['correct','incorrect','gap'].includes(row.state));
  if(!value&&activeTask?.plan?.stale){$('task-to-lesson').disabled=true;$('task-followup').disabled=true;}
}
async function loadTask(id){
  if(!id)return;
  const token=++taskLoadToken;taskBusy(true,'正在读取当前任务与证据…');
  const [task,evidence]=await Promise.all([api('/api/teaching/'+id),api('/api/teaching/'+id+'/evidence')]);
  if(token!==taskLoadToken)return;activeTask=task;activeEvidence=evidence;
  const area=$('task-evidence');area.replaceChildren();
  if(activeTask.parent_id)area.append(node('p','关联前序任务：'+activeTask.parent_id.slice(0,8),'loop-local-note'));
  area.append(node('p',activeEvidence.scope,'history-empty'));
  for(const row of activeEvidence.items){
    const card=node('div',undefined,'task-evidence-item');card.append(node('strong',row.objective),node('p',row.problem),node('span',evidenceNames[row.state]||row.state,'badge'));
    if(row.submission_id)card.append(node('small','第 '+row.revision+' 次提交 · '+row.submission_id.slice(0,8)));
    if(row.first_error){card.append(node('blockquote',row.first_error.quote||''));card.append(node('p',row.first_error.reason||''));}
    const begin=node('button',row.submission_id?'学生 · 继续修订 →':'学生 · 领取并作答 →','text-button');begin.onclick=async()=>{if(taskWorking)return;try{taskBusy(true,'正在打开任务对应的练习…');const opened=await api('/api/teaching/'+id+'/open/'+row.id,{});await loadSession(opened.session_id);if(!history.length)populate({problem:opened.problem,mode:'check',grade_level:'高中',request:'本题目标：'+opened.objective});switchWorkspace('practice');taskBusy(false);$('form-status').textContent='来自教学任务：'+activeTask.title+'。完成诊断后，在“师生任务”刷新查看。';$('problem').focus();}catch(error){taskBusy(false,error.message);}};card.append(begin);area.append(card);
  }
  $('task-plan-stage').hidden=!activeTask.plan;
  if(activeTask.plan){$('task-plan-draft').value=activeTask.plan.draft_markdown;$('task-plan-note').textContent=activeTask.plan.stale?'学生提交或诊断已经变化，这份教案依据已过期；请重新规划。':'依据绑定当前提交。请检查数学内容和引文后再用于课堂。';}
  taskBusy(false);
}
async function refreshTasks(preferred){
  const rows=await api('/api/teaching');const select=$('task-select');const selected=preferred||select.value;select.replaceChildren();
  if(!rows.length){select.append(new Option('先发布一份任务',''));return;}
  for(const row of rows)select.append(new Option(row.title,row.id));
  select.value=rows.some(row=>row.id===selected)?selected:rows[0].id;await loadTask(select.value);
}
$('show-teaching').onclick=()=>{switchWorkspace('teaching');refreshTasks().catch(error=>taskBusy(false,error.message));};
$('task-add-item').onclick=()=>addTaskItem();
$('task-design').onclick=async()=>{
  if(taskWorking)return;taskBusy(true,'正在依据目标起草任务…');
  try{const draft=await api('/api/teaching/design',{title:$('task-title').value,objective:$('task-objective').value,...(followupSource||{})});$('task-title').value=draft.title;$('task-item-editor').replaceChildren();draft.items.forEach(addTaskItem);$('task-review-note').textContent=draft.review_status;taskBusy(false,'草案已生成。请检查每题原题与目标后发布。');}catch(error){taskBusy(false,error.message);}
};
$('task-form').onsubmit=async event=>{
  event.preventDefault();if(taskWorking)return;taskBusy(true,'正在发布…');
  try{const payload={title:$('task-title').value,items:[...$('task-item-editor').children].map(card=>({problem:card.querySelector('.task-problem').value,objective:card.querySelector('.task-goal').value}))};if(followupSource)Object.assign(payload,followupSource);const task=await api('/api/teaching',payload);followupSource=null;$('task-parent-note').textContent='';await refreshTasks(task.id);taskBusy(false,'任务已发布，学生可以从右侧领取题目。');}catch(error){taskBusy(false,error.message);}
};
$('task-refresh').onclick=()=>{if(taskWorking)return;refreshTasks().catch(error=>taskBusy(false,error.message));};
$('task-select').onchange=()=>loadTask($('task-select').value).catch(error=>taskBusy(false,error.message));
$('task-plan').onclick=async()=>{
  if(taskWorking||!activeTask)return;taskBusy(true,'正在根据当前诊断整理教师教案草稿…');
  try{await api('/api/teaching/'+activeTask.id+'/plan',{});await loadTask(activeTask.id);taskBusy(false,'教案草稿已生成，先审阅再交给备课或布置再练习。');}catch(error){taskBusy(false,error.message);}
};
async function checkPlanCurrent(){
  if(!activeTask?.plan)throw new Error('请先生成教案草稿。');
  const report=await api('/api/teaching/'+activeTask.id+'/evidence');
  if(report.evidence_version!==activeTask.plan.evidence_version){await loadTask(activeTask.id);throw new Error('学生提交或诊断已变化，请重新规划。');}
}
$('task-to-lesson').onclick=async()=>{
  try{await checkPlanCurrent();currentLesson=null;lessonTeachingSource={assignment_id:activeTask.id,evidence_version:activeTask.plan.evidence_version};switchWorkspace('teacher');$('lesson-topic').value=activeTask.title+' · 针对性教学';$('lesson-draft').value=$('task-plan-draft').value; $('lesson-outline-stage').hidden=true;$('lesson-source-stage').hidden=true;$('lesson-empty').hidden=false;$('lesson-result').replaceChildren();$('lesson-badge').textContent='等待教案';$('lesson-status').textContent='已带入学习证据和教师草稿；请补齐年级、教材、课时，再生成大纲。';lessonStep(0);$('lesson-topic').focus();}catch(error){$('task-status').textContent=error.message;}
};
$('task-followup').onclick=async()=>{
  try{await checkPlanCurrent();followupSource={parent_id:activeTask.id,evidence_version:activeTask.plan.evidence_version};$('task-title').value=activeTask.title+' · 再练习';$('task-objective').value=activeEvidence.items.filter(row=>['incorrect','gap'].includes(row.state)).map(row=>row.objective).join('；')||'巩固当前已展示的推理';$('task-item-editor').replaceChildren();addTaskItem();$('task-parent-note').textContent='将关联前序任务 '+activeTask.id.slice(0,8)+' 及当前证据版本。';$('task-title').focus();}catch(error){$('task-status').textContent=error.message;}
};
addTaskItem();
if(openedFromFile)document.querySelectorAll('#teaching-view button,#teaching-view input,#teaching-view textarea,#teaching-view select').forEach(control=>control.disabled=true);
