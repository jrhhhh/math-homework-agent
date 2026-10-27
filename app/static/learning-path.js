let learningPath=null,pathEpoch=0,pathBusy=false,widgetEpoch=0,pathScene='attempt';
function supportLabel(condition){return {no_recorded_support:'提交前未记录系统帮助',supported:'在已记录帮助后提交',answer_seen_or_requested:'已请求或获得完整讲解',unknown_legacy:'旧记录，帮助条件不明',not_attempted:'尚未作答'}[condition]||condition;}
async function openLearningPath(taskId,itemId){
  const epoch=++pathEpoch;const opened=await api('/api/teaching/'+taskId+'/open/'+itemId,{});if(epoch!==pathEpoch)return;
  const path=await api('/api/teaching/'+taskId+'/path/'+itemId);if(epoch!==pathEpoch)return;
  learningPath=path;learningPath.session_id=opened.session_id;pathBusy=false;
  const records=await api('/api/sessions/'+opened.session_id);if(epoch!==pathEpoch)return;
  $('path-solution').value=records.at(-1)?.data.solution||'';$('path-feedback').replaceChildren(node('p','先写出自己的尝试。'));
  $('path-guidance').hidden=true;$('path-widget').hidden=true;$('path-widget-note').textContent=path.item.interactive_template==='none'?'本题未设置数学操作活动，可以回到作答或请教师补充。':'活动可以帮助观察；打开后会记录为本题的一次帮助。';
  $('path-open-widget').disabled=path.item.interactive_template==='none';
  switchWorkspace('path');paintPath(path);showPathScene('attempt');
  if(records.length){paintPathFeedback(records.at(-1));if(['queued','running'].includes(records.at(-1).state))pollPath(records.at(-1).id,epoch);}
}
function paintPath(path){
  $('path-goal').textContent=path.item.objective;$('path-criteria').textContent='成功标准：'+path.item.success_criteria;
  $('path-problem').textContent=path.item.problem;$('path-condition').textContent=(path.assessment_kind==='independent_check'?'这是一道同目标新题复核。选择帮助后，结果会注明帮助条件。':'先独立尝试，需要时再请求帮助。')+' 记录限本题当前练习；其他练习或系统外的帮助请主动补充。';
  const tabs=$('path-scene-tabs');tabs.replaceChildren();for(const scene of path.scenes){const button=node('button',scene.title);button.dataset.scene=scene.id;button.onclick=()=>showPathScene(scene.id);tabs.append(button);}
  const records=$('path-records');records.replaceChildren(node('h3','本题的尝试与帮助条件'));
  for(const attempt of path.attempts){const row=node('div',undefined,'history-row');row.append(node('strong','第 '+attempt.revision+' 次'),node('span',supportLabel(attempt.support.condition)),node('small',labels[attempt.state]||attempt.state));records.append(row);}
  if(!path.attempts.length)records.append(node('p','还没有提交记录。','history-empty'));
  if(path.support_history.length){const details=node('details');details.append(node('summary','已记录的帮助（'+path.support_history.length+'）'));for(const event of path.support_history)details.append(node('p',({hint_requested:'请求提示',hint_available:'提示已生成',feedback_available:'诊断反馈已生成',solution_requested:'请求完整讲解',solution_available:'完整讲解已生成',guidance_opened:'查看教师提示',interactive_opened:'打开数学活动',external_help:'补充外部帮助',teacher_guidance:'教师帮助'}[event.kind]||event.kind)+(event.detail?'：'+event.detail:'')));records.append(details);}
  const follows=$('path-followups');follows.replaceChildren();
  if(path.current.independent_check_passed)follows.append(node('p','本次新题复核通过，且提交前未记录系统帮助。这只说明本题在该条件下的表现。','source-note'));
  for(const task of path.followups){const button=node('button',task.title+' · '+(task.assessment_kind==='independent_check'?'独立复核':'练习'),'text-button');button.onclick=async()=>{try{const next=await api('/api/teaching/'+task.id);await openLearningPath(task.id,next.items[0].id);}catch(error){$('path-status').textContent=error.message;}};follows.append(button);}
  if(!path.followups.length)follows.append(node('p','尚未发布关联的新题。请教师根据当前证据布置，不能用重做原题代替独立复核。'));
  showPathScene(pathScene);renderMath($('path-view'));
}
function showPathScene(id){pathScene=id;for(const [scene,element] of [['attempt','path-attempt-scene'],['explain','path-explain-scene'],['interactive','path-interactive-scene'],['independent_check','path-check-scene']])$(element).hidden=scene!==id;for(const tab of $('path-scene-tabs').children){tab.classList.toggle('active',tab.dataset.scene===id);tab.setAttribute('aria-pressed',String(tab.dataset.scene===id));}}
function pathWorking(value,message=''){pathBusy=value;for(const id of ['path-submit','path-hint','path-answer','path-record-help'])$(id).disabled=value;$('path-status').textContent=message;}
async function refreshPath(){if(!learningPath)return;const epoch=pathEpoch;const value=await api('/api/teaching/'+learningPath.assignment_id+'/path/'+learningPath.item.id);if(epoch!==pathEpoch)return;learningPath={...value,session_id:learningPath.session_id};paintPath(learningPath);}
function paintPathFeedback(item){const area=$('path-feedback');area.replaceChildren();area.append(node('p',labels[item.state]||item.state));if(item.result?.output?.reply)area.append(node('div',item.result.output.reply));else if(item.result?.error)area.append(node('p',item.result.error,'error-message'));if(item.support)area.append(node('p',supportLabel(item.support.condition),'result-meta'));renderMath(area);}
async function pollPath(id,epoch){pathWorking(true,'正在检查本次尝试…');try{while(epoch===pathEpoch){const item=await api('/api/submissions/'+id);if(epoch!==pathEpoch)return;paintPathFeedback(item);if(!['queued','running'].includes(item.state)){await refreshPath();pathWorking(false,item.state==='error'||item.state==='interrupted'?'诊断未完成，请到任务中心继续。':'记录已更新；下一步可以修订或查看关联新题。');return;}await new Promise(resolve=>setTimeout(resolve,850));}}catch(error){if(epoch===pathEpoch)pathWorking(false,error.message);}}
async function submitPath(mode){if(pathBusy||!learningPath)return;const epoch=pathEpoch;pathWorking(true,'正在保存本次尝试…');try{const {id}=await api('/api/sessions/'+learningPath.session_id+'/submissions',{problem:learningPath.item.problem,solution:$('path-solution').value,mode,grade_level:'高中',source:'student',allow_mode_change:true});pollPath(id,epoch);}catch(error){pathWorking(false,error.message);}}
$('path-form').onsubmit=event=>{event.preventDefault();submitPath('check');};$('path-hint').onclick=()=>submitPath('hint');$('path-answer').onclick=()=>submitPath($('path-solution').value.trim()?'full_correction':'solve');
async function pathSupport(kind,detail=''){if(!learningPath)throw Error('请先领取任务。');await api('/api/sessions/'+learningPath.session_id+'/support',{kind,problem:learningPath.item.problem,detail});await refreshPath();}
$('path-record-help').onclick=async()=>{try{const text=$('path-external-help').value.trim();if(!text)throw Error('请简要填写得到过的帮助。');await pathSupport('external_help',text);$('path-external-help').value='';$('path-status').textContent='帮助条件已记录；不会改写已经提交的历史条件。';}catch(error){$('path-status').textContent=error.message;}};
$('path-show-guidance').onclick=async()=>{try{await pathSupport('guidance_opened','查看教师填写的教学提示');$('path-guidance').textContent=learningPath.item.guidance||'回看原题条件，说明每一步的依据；需要时请求一个提示。';$('path-guidance').hidden=false;renderMath($('path-guidance'));}catch(error){$('path-status').textContent=error.message;}};
$('path-explain-return').onclick=()=>showPathScene('attempt');$('path-refresh').onclick=()=>refreshPath().catch(error=>$('path-status').textContent=error.message);
$('path-back').onclick=()=>{pathEpoch++;switchWorkspace('teaching');refreshTasks(learningPath?.assignment_id);};$('path-ask-check').onclick=()=>{pathEpoch++;switchWorkspace('teaching');refreshTasks(learningPath?.assignment_id);};
function svgNode(tag,attrs={}){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,String(value));return el;}
function drawWidget(data){const svg=$('widget-chart');svg.replaceChildren();const circle=data.template==='unit_circle';const xmin=circle?-1.35:-4,xmax=-xmin,ymin=circle?-1.35:-5,ymax=circle?1.35:10;
  const sx=x=>(circle?140:35)+(x-xmin)/(xmax-xmin)*(circle?280:490),sy=y=>310-(y-ymin)/(ymax-ymin)*280;
  const line=(points,color,width=2)=>{const path=svgNode('path',{d:points.map(([x,y],i)=>(i?'L':'M')+sx(x)+','+sy(y)).join(' '),fill:'none',stroke:color,'stroke-width':width,'clip-path':'url(#widget-clip)'});svg.append(path);};
  const defs=svgNode('defs'),clip=svgNode('clipPath',{id:'widget-clip'});clip.append(svgNode('rect',{x:35,y:30,width:490,height:280}));defs.append(clip);svg.append(defs);
  line([[xmin,0],[xmax,0]],'#b7aeb0',1);line([[0,ymin],[0,ymax]],'#b7aeb0',1);
  const point=(p,color)=>p[0]>=xmin&&p[0]<=xmax&&p[1]>=ymin&&p[1]<=ymax&&svg.append(svgNode('circle',{cx:sx(p[0]),cy:sy(p[1]),r:4,fill:color}));
  if(circle){line(Array.from({length:181},(_,i)=>{const t=i*Math.PI/90;return[Math.cos(t),Math.sin(t)];}),'#b70031');line([[0,0],data.point],'#316c54');line([[data.point[0],0],data.point,[0,data.point[1]]],'#b18445',1);point(data.point,'#316c54');}
  else{line(data.points,'#b70031');if(data.line)line(data.line,'#316c54');if(data.point)point(data.point,'#316c54');if(data.second_point)point(data.second_point,'#b18445');if(data.vertex&&data.vertex[0]>=xmin&&data.vertex[0]<=xmax)point(data.vertex,'#316c54');}
  const caption=svgNode('text',{x:38,y:22,fill:'#675e61','font-size':12});caption.textContent=circle?'单位圆坐标：('+data.point.map(x=>x.toFixed(3)).join(', ')+')':data.template==='derivative'?(data.mode==='tangent_limit'?'切线（导数给出的极限图示）':'割线')+' 斜率：'+data.slope.toFixed(4):data.vertex?'顶点：('+data.vertex.map(x=>x.toFixed(2)).join(', ')+')':'a=0：当前不是二次函数';svg.append(caption);
  $('widget-formula').textContent=data.formula;$('widget-question').textContent=data.question;$('widget-scope').textContent=data.scope;
}
async function initializeWidget(){const template=learningPath.item.interactive_template;const definitions={quadratic:[['a',1,-3,3,.1],['b',0,-5,5,.1],['c',0,-5,5,.1]],unit_circle:[['angle',45,-360,360,1]],derivative:[['x0',1,-2,2,.1],['h',1,-2,2,.01]]}[template];if(!definitions)return;
  const controls=$('widget-controls');controls.replaceChildren();const values={template};let timer;
  async function update(){const epoch=++widgetEpoch;const data=await api('/api/math-widget',values);if(epoch===widgetEpoch)drawWidget(data);}
  for(const [name,value,min,max,step] of definitions){values[name]=value;const label=node('label',({angle:'角度 θ（度）',x0:'切点横坐标 x₀',h:'步长 h'}[name]||name)+'：');const output=node('output',String(value));label.append(output);const input=node('input');input.type='range';input.min=min;input.max=max;input.step=step;input.value=value;input.setAttribute('aria-label',name);input.oninput=()=>{values[name]=Number(input.value);output.textContent=input.value;clearTimeout(timer);timer=setTimeout(()=>update().catch(error=>$('path-status').textContent=error.message),100);};label.append(input);controls.append(label);}
  await update();
}
$('path-open-widget').onclick=async()=>{try{await pathSupport('interactive_opened','数学活动：'+learningPath.item.interactive_template);await initializeWidget();$('path-widget').hidden=false;}catch(error){$('path-status').textContent=error.message;}};
if(openedFromFile)document.querySelectorAll('#path-view button,#path-view input,#path-view textarea').forEach(control=>control.disabled=true);
