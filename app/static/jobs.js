let jobsRefreshVersion=0;
const jobNames={'diagnose':'学生过程诊断','task-design':'学习任务草案','remedial-plan':'针对性教学草稿','lesson-outline':'课件大纲','lesson-source':'课件源码','lesson-render':'课件渲染与检查'};
const jobStates={queued:'等待运行',running:'正在执行',paused:'暂停，可继续',completed:'已完成',cancelled:'已停止'};
function jobStepName(value){return {diagnosis:'过程诊断',task_design:'起草学习任务',remedial_plan:'规划针对性教学',lesson_outline:'整理逐页大纲',lesson_source:'生成课件源码',figures:'制作配图',build:'构建 PowerPoint',verify:'独立结构检查'}[value?.split(':')[0]]||value||'等待开始';}
async function jobApi(path,data){
  let kind,payload={...data};
  if(path==='/api/teaching/design')kind='task-design';
  else if(/^\/api\/teaching\/[^/]+\/plan$/.test(path)){kind='remedial-plan';payload.assignment_id=path.split('/')[3];}
  else if(path==='/api/lessons/outline')kind='lesson-outline';
  else if(/^\/api\/lessons\/[^/]+\/(source|render)$/.test(path)){kind=path.endsWith('/source')?'lesson-source':'lesson-render';payload.lesson_id=path.split('/')[3];}
  else return api(path,data);
  let job=await api('/api/jobs',{kind,payload,request_key:crypto.randomUUID()});refreshJobs();
  while(['queued','running'].includes(job.state)){await new Promise(resolve=>setTimeout(resolve,750));job=await api('/api/jobs/'+job.id);}
  refreshJobs();if(job.state!=='completed')throw new Error((job.error||jobStates[job.state])+' 可在任务中心查看并继续。');return job.result;
}
async function showJobResult(job){
  if(!job.result)return;
  if(job.kind==='diagnose'){const item=await api('/api/submissions/'+job.result.submission_id);switchWorkspace('practice');await loadSession(item.session_id);}
  else if(job.kind==='task-design'){switchWorkspace('teaching');await adoptTaskDraft(job.result);$('task-status').textContent='已恢复草案，请核对题意、条件和成功标准后发布。';}
  else if(job.kind==='remedial-plan'){switchWorkspace('teaching');await refreshTasks(job.result.assignment_id);}
  else{switchWorkspace('teacher');showLesson(await api('/api/lessons/'+job.result.id));await refreshLessonHistory();}
  setJobsOpen(false);
}
async function refreshJobs(){
  if(openedFromFile)return;const sequence=++jobsRefreshVersion;
  try{const rows=await api('/api/jobs');if(sequence!==jobsRefreshVersion)return;$('jobs-count').textContent=rows.filter(row=>['queued','running','paused'].includes(row.state)).length;
    const list=$('jobs-list');const signature=JSON.stringify(rows);if(list.dataset.signature===signature)return;list.dataset.signature=signature;const focused=document.activeElement?.closest('[data-job-action]');const focusKey=focused?.dataset.jobAction;list.replaceChildren();if(!rows.length)list.append(node('p','还没有后台任务。','history-empty'));
    for(const job of rows){const card=node('div',undefined,'job-row');card.dataset.state=job.state;card.append(node('strong',jobNames[job.kind]||job.kind),node('span',(job.cancel_requested&&job.state==='running'?'已请求停止，等待当前步骤返回':jobStates[job.state]),'badge'));
      const latest=job.events.filter(event=>['step','checkpoint','reused'].includes(event.type)).at(-1);if(latest)card.append(node('small',jobStepName(latest.detail)+(latest.type==='reused'?' · 使用已保存结果':'')));
      if(job.completed_steps.length)card.append(node('small','已保存：'+job.completed_steps.map(jobStepName).join('、')));if(job.error)card.append(node('p',job.error,'error-message'));
      const actions=node('div',undefined,'path-actions');if(['paused','cancelled'].includes(job.state)){const retry=node('button','继续此任务','text-button');retry.dataset.jobAction=job.id+'-retry';retry.onclick=async()=>{try{await api('/api/jobs/'+job.id+'/retry',{});refreshJobs();}catch(error){card.append(node('p',error.message));}};actions.append(retry);}
      if(['queued','running','paused'].includes(job.state)){const cancel=node('button','停止','text-button');cancel.dataset.jobAction=job.id+'-cancel';cancel.disabled=Boolean(job.cancel_requested);cancel.onclick=async()=>{try{await api('/api/jobs/'+job.id+'/cancel',{});refreshJobs();}catch(error){card.append(node('p',error.message));}};actions.append(cancel);}
      if(job.result){const view=node('button','查看结果 →','text-button');view.dataset.jobAction=job.id+'-view';view.onclick=()=>showJobResult(job).catch(error=>card.append(node('p',error.message)));actions.append(view);}card.append(actions);list.append(card);
    }
    if(focusKey){const target=[...list.querySelectorAll('[data-job-action]')].find(el=>el.dataset.jobAction===focusKey);(target||$('jobs-refresh')).focus();}
  }catch(error){if(sequence!==jobsRefreshVersion)return;delete $('jobs-list').dataset.signature;$('jobs-list').replaceChildren(node('p',error.message,'error-message'));}
}
function setJobsOpen(open){
  const dock=$('jobs-dock');
  if(open){dock.hidden=false;if(!dock.open)dock.showModal();refreshJobs();}
  else{dock.close();dock.hidden=true;}
  $('jobs-toggle').setAttribute('aria-expanded',String(open));
}
$('jobs-toggle').onclick=()=>setJobsOpen(!$('jobs-dock').open);
$('jobs-close').onclick=()=>setJobsOpen(false);
$('jobs-dock').addEventListener('close',()=>{$('jobs-dock').hidden=true;$('jobs-toggle').setAttribute('aria-expanded','false');$('jobs-toggle').focus();});
$('jobs-dock').addEventListener('click',event=>{if(event.target!==$('jobs-dock'))return;const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)setJobsOpen(false);});
$('jobs-refresh').onclick=refreshJobs;
if(!openedFromFile){refreshJobs();setInterval(()=>{if(!$('jobs-dock').hidden)refreshJobs();},1800);}
