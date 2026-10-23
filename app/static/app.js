const $ = id => document.getElementById(id);
let sessionId = null, history = [], busy = false, currentPoll = 0, verificationAvailable = true;
const labels = {queued:'排队中',running:'正在思考',ready:'反馈已生成',needs_input:'待补充材料',gate_failed:'需要复核',error:'调用失败',interrupted:'运行已中断'};
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败');
  return result;
}
function node(tag, text, cls) {
  const el = document.createElement(tag); if(text !== undefined) el.textContent = text; if(cls) el.className = cls; return el;
}
function renderMath(area) {
  if(typeof renderMathInElement==='function')renderMathInElement(area,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false},{left:'$',right:'$',display:false}],throwOnError:false,trust:false,strict:'ignore',maxExpand:1000,maxSize:20});
}
function setMode() {
  const draft = ['draft','partition'].includes($('mode').value);
  $('draft-field').hidden = !draft; $('solution-field').hidden = draft;
  $('submit').firstChild.textContent = draft ? '分析草稿 ' : $('mode').value === 'solve' ? '开始求解 ' : $('mode').value === 'refine' ? '先核验再优化 ' : '开始检查 ';
  $('verify-equation').disabled=!verificationAvailable||draft||$('mode').value==='hint';if($('verify-equation').disabled)$('verify-equation').checked=false;
}
let workFiles=[], workFileUrls=[];
const ATTACHMENT_TYPES=new Set(['image/png','image/jpeg','image/webp','application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain','text/markdown']);
function fileKey(file){return file.name+'|'+file.size+'|'+file.lastModified;}
function fileExtension(file){const parts=file.name.toLowerCase().split('.');return parts.length>1?parts.pop():'';}
function isImageFile(file){return file.type.startsWith('image/')||['png','jpg','jpeg','webp'].includes(fileExtension(file));}
function allowedFile(file){return ATTACHMENT_TYPES.has(file.type)||['png','jpg','jpeg','webp','pdf','docx','txt','md'].includes(fileExtension(file));}
function formatSize(bytes){return bytes<1024?bytes+' B':bytes<1048576?(bytes/1024).toFixed(1)+' KB':(bytes/1048576).toFixed(1)+' MB';}
function hideExtractPanel(){const panel=$('work-extract-panel');if(panel)panel.hidden=true;const area=$('work-extract-text');if(area)area.value='';}
function clearWorkFiles(){
  workFiles=[];workFileUrls.forEach(URL.revokeObjectURL);workFileUrls=[];
  const input=$('work-files');if(input)input.value='';
  const list=$('work-file-list');if(list)list.replaceChildren();
  hideExtractPanel();
}
function addWorkFiles(files){
  for(const file of files){
    if(workFiles.length>=3){$('form-status').textContent='最多上传 3 个附件。';break;}
    if(!allowedFile(file)){$('form-status').textContent='只支持图片、PDF、DOCX、TXT 或 MD 附件。';continue;}
    if(file.size>5*1024*1024){$('form-status').textContent='单个附件不能超过 5 MB。';continue;}
    if(workFiles.some(item=>item.key===fileKey(file)))continue;
    workFiles.push({file,key:fileKey(file)});
  }
  renderWorkFiles();
}
function renderWorkFiles(){
  workFileUrls.forEach(URL.revokeObjectURL);workFileUrls=[];
  const list=$('work-file-list');if(!list)return;
  list.replaceChildren();
  for(const [index,item] of workFiles.entries()){
    const row=node('div',undefined,'work-file-row');
    if(isImageFile(item.file)){
      const url=URL.createObjectURL(item.file);workFileUrls.push(url);
      const img=document.createElement('img');img.src=url;img.alt='附件预览';row.append(img);
    }
    const info=node('div',undefined,'work-file-info');
    info.append(node('strong',item.file.name));
    info.append(node('small',formatSize(item.file.size)));
    row.append(info);
    if(!isImageFile(item.file)){
      const extract=node('button','提取文字','text-button');extract.type='button';
      extract.onclick=()=>extractWorkFile(item.file);row.append(extract);
    }
    const remove=node('button','移除','text-button');remove.type='button';
    remove.onclick=()=>{workFiles.splice(index,1);renderWorkFiles();};
    row.append(remove);
    list.append(row);
  }
}
async function extractWorkFile(file){
  try{
    $('form-status').textContent='正在提取附件文字…';
    const data=await api('/api/attachments/extract',{name:file.name,base64:await fileToBase64(file)});
    $('work-extract-text').value=data.text||'';
    $('work-extract-panel').hidden=false;
    $('form-status').textContent=data.warning||'已提取文字；请核对后选择填入位置。';
  }catch(error){$('form-status').textContent=error.message;}
}
$('extract-to-problem').onclick=()=>{const text=$('work-extract-text').value.trim();if(!text)return;$('problem').value=text;hideExtractPanel();$('problem').focus();};
$('extract-to-solution').onclick=()=>{const text=$('work-extract-text').value.trim();if(!text)return;$('solution').value=text;hideExtractPanel();$('solution').focus();};
$('extract-close').onclick=hideExtractPanel;
let showArchived=false;
function sessionRow(row, archived){
  const wrapper=node('div',undefined,'session-row'+(row.id===sessionId?' active':'')+(archived?' archived':''));
  const title=node('button',row.title,'session-title');title.title=row.title;
  title.onclick=()=>loadSession(row.id);wrapper.append(title);
  const actions=node('div',undefined,'session-actions');
  const archive=node('button',archived?'恢复':'归档','session-action');archive.type='button';
  archive.title=archived?'取消归档':'归档';archive.setAttribute('aria-label',archive.title);
  archive.onclick=async event=>{event.stopPropagation();await setArchived(row.id,!archived);};
  const trash=node('button','🗑','session-action delete');trash.type='button';
  trash.title='删除练习';trash.setAttribute('aria-label','删除练习');
  trash.onclick=async event=>{event.stopPropagation();await removeSession(row);};
  actions.append(archive,trash);wrapper.append(actions);
  return wrapper;
}
async function sessions() {
  const rows=await api('/api/sessions');
  const active=rows.filter(row=>!row.archived), archived=rows.filter(row=>row.archived);
  const archivedCurrent=archived.find(row=>row.id===sessionId);
  const list=$('sessions');list.replaceChildren();
  for(const row of active)list.append(sessionRow(row,false));
  if(showArchived&&archived.length){
    list.append(node('div','已归档','session-group-label'));
    for(const row of archived)list.append(sessionRow(row,true));
  }else if(archivedCurrent){
    list.append(node('div','当前练习 · 已归档','session-group-label'));
    list.append(sessionRow(archivedCurrent,true));
  }
  $('toggle-archived').textContent=showArchived?'收起归档':'归档';
  $('toggle-archived').classList.toggle('active',showArchived);
}
async function setArchived(id,archived){
  try{await api('/api/sessions/'+id+'/archive',{archived});$('session-status').textContent=archived?'已归档。':'已取消归档。';await sessions();}
  catch(error){$('session-status').textContent=error.message;}
}
async function deleteSession(id){
  const response=await fetch('/api/sessions/'+id,{method:'DELETE'});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'删除失败');
  return result;
}
async function removeSession(row){
  if(!confirm('删除“'+row.title+'”及其全部提交？此操作不可恢复。'))return;
  try{
    await deleteSession(row.id);
    $('session-status').textContent='已删除练习。';
    if(sessionId===row.id){
      sessionId=null;history=[];renderHistory();populate({});
      $('result').replaceChildren(node('p','练习已删除。新建一份练习继续。','history-empty'));
      $('state-badge').textContent='等待提交';
    }
    await sessions();
  }catch(error){$('session-status').textContent=error.message;}
}
function populate(data) {
  clearWorkFiles();
  for(const key of ['problem','solution','draft','request','mode']) $(key).value = data[key] || (key==='mode'?'check':'');
  $('grade').value = data.grade_level || '高中'; setMode();
  $('verify-equation').checked=Boolean(data.verification_requested)&&!$('verify-equation').disabled;
}
async function loadSession(id) {
  currentPoll++; sessionId=id; busy=false; $('submit').disabled=false;$('session-status').textContent='';
  history = await api('/api/sessions/'+id); await sessions(); renderHistory();
  if(history.length){populate(history.at(-1).data); renderResult(history.at(-1)); if(['queued','running'].includes(history.at(-1).state)) poll(history.at(-1).id);}
  else {populate({});$('result').replaceChildren(node('p','写下你的尝试，开始新的练习。','history-empty'));$('state-badge').textContent='等待提交';}
}
function renderHistory() {
  $('history').replaceChildren(); $('export').disabled=!history.length;
  if(!history.length){$('history').textContent='完成第一次提交后，在这里对照每次修改。';return;}
  for(const item of [...history].reverse()) {
    const row=node('div',undefined,'history-row');row.append(node('strong','第 '+item.revision+' 次提交'));
    row.append(node('small',new Date(item.created).toLocaleString('zh-CN')));
    if(item.data?.attachments?.length || item.data?.image?.sha256)row.append(node('small','含附件'));
    row.append(node('span',item.is_current?'当前版本':'历史版本 · 已失效'));
    const button=node('button','查看');button.onclick=()=>{renderResult(item);$('feedback-heading').scrollIntoView({behavior:'smooth',block:'start'});};row.append(button);$('history').append(row);
  }
  $('revision-note').textContent='下一次提交将保存为第 '+(history.at(-1).revision+1)+' 版，旧结果保留为历史。';
}
function renderResult(item) {
  const area=$('result');area.replaceChildren();$('state-badge').textContent=labels[item.state]||item.state;
  if(!item.is_current)area.append(node('p','这是历史版本的反馈，不代表当前解答。','error-message'));
  const attachments=item.data?.attachments || (item.data?.image?.sha256?[item.data.image]:[]);
  for(const attachment of attachments){
    if(!attachment?.sha256)continue;
    const url='/api/uploads/'+attachment.sha256+attachment.ext;
    const isImage=attachment.kind==='image'||['.png','.jpg','.webp'].includes(attachment.ext);
    if(isImage){
      const figure=node('figure',undefined,'work-image-card');
      const image=document.createElement('img');
      image.src=url;image.alt='第 '+item.revision+' 次提交的附件';image.loading='lazy';
      figure.append(image);
      figure.append(node('figcaption','第 '+item.revision+' 次提交的图片 · 仅本地查看，系统未识别其中文字'));
      area.append(figure);
    }else{
      const link=node('a',(attachment.ext==='.pdf'?'查看 PDF 附件':'查看附件')+' ↗','attachment-link');
      link.href=url;link.target='_blank';link.rel='noopener noreferrer';
      area.append(link);
    }
  }
  if(['queued','running'].includes(item.state)){area.append(node('div','正在检查你的思路，请稍等。','loading'));return;}
  const run=item.result;
  if(!run || run.error){area.append(node('p',run?.error||'运行已中断，请重新提交。','error-message'));return;}
  if(run.status==='gate_failed'){area.append(node('p','输出未通过校验，本次不作为可交付反馈。请重新提交或查看运行记录。','error-message'));}
  else if(run.output){area.append(node('div',run.output.reply,'reply'));
    const checks=(run.attempts?.at(-1)?.gates||[]).filter(g=>g.gate==='exact-math');
    for(const check of checks){const card=node('div',undefined,'evidence-card');card.append(node('h3',check.exit_code===0?'已执行等式核验':'等式核验待复核'));card.append(node('p',check.source_quote||'核验请求'));for(const point of check.record?.checks||[])card.append(node('p',(check.record.request?.variable||'x')+'='+point.value+'：左边 '+point.left+'，右边 '+point.right+'，差值 '+point.residual));if(check.record?.residual!==undefined)card.append(node('p','展开后差值为 '+check.record.residual));card.append(node('p',check.record?.scope||check.scope));area.append(card);}
    const error=run.output.result?.first_error;
    if(error && item.data.mode!=='hint'){
      const card=node('div',undefined,'evidence-card');card.append(node('h3','首个实质问题 · 第 '+error.step+' 步'));card.append(node('blockquote',error.quote));card.append(node('p',error.reason));area.append(card);
    }
    const fix=run.output.result?.minimal_fix;
    if(fix && item.data.mode!=='hint'){const card=node('div',undefined,'evidence-card');card.append(node('h3','最小修改'));card.append(node('p',fix));area.append(card);}
    const opportunities=run.output.result?.optimization_opportunities;
    if(Array.isArray(opportunities)){const section=node('div',undefined,'evidence-card');section.append(node('h3','三个可尝试的优化方向'));for(const [i,op] of opportunities.entries()){const block=node('section',undefined,'optimization-item');block.append(node('strong',(i+1)+' · '+op.direction));block.append(node('p',op.suggestion));block.append(node('p','本解答尚未展示：'+op.exposed_gap));block.append(node('small','现在可以试：'+op.training_suggestion));section.append(block);}area.append(section);}
    if(item.is_current && item.data.solution){const actions=node('div',undefined,'result-actions');const revise=node('button','修改后再检查 ↗');revise.onclick=()=>{$('solution').focus();$('solution').scrollIntoView({behavior:'smooth',block:'center'});};actions.append(revise);area.append(actions);}
  }
  area.append(node('div',(run.stage||run.routing?.skill||'待补充')+' · 第 '+item.revision+' 版 · '+item.version.slice(0,10),'result-meta'));
  const details=node('details');details.append(node('summary','查看校验与运行记录'));
  const safe={routing:run.routing,status:run.status,stage:run.stage,handoff:run.handoff,limitation:run.limitation,attempts:(run.attempts||[]).map(a=>({elapsed_seconds:a.response?.elapsed_seconds,usage:a.response?.usage,gates:a.gates,stage:a.stage})),structured_result:run.output?.result};
  details.append(node('pre',JSON.stringify(safe,null,2)));area.append(details);
  renderMath(area);
}
async function poll(id) {
  const token=++currentPoll;busy=true;$('submit').disabled=true;
  while(token===currentPoll){
    try {const item=await api('/api/submissions/'+id);if(token!==currentPoll)return;renderResult(item);
      if(!['queued','running'].includes(item.state)){history=await api('/api/sessions/'+sessionId);renderHistory();busy=false;$('submit').disabled=false;$('form-status').textContent='';if(window.matchMedia('(max-width:1080px)').matches)$('feedback-heading').scrollIntoView({behavior:'smooth',block:'start'});return;}
    } catch(error){$('form-status').textContent=error.message;busy=false;$('submit').disabled=false;return;}
    await new Promise(resolve=>setTimeout(resolve,1500));
  }
}
$('submission-form').onsubmit=async event=>{
  event.preventDefault();if(busy)return;$('form-status').textContent='正在提交…';$('submit').disabled=true;
  try{
    if(!sessionId)sessionId=(await api('/api/sessions',{})).id;
    const data=Object.fromEntries(['problem','solution','draft','request','mode'].map(k=>[k,$(k).value]));data.grade_level=$('grade').value;
    data.verification_requested=$('verify-equation').checked;
    const old=history.at(-1);data.allow_mode_change=Boolean(old && old.data.mode==='hint' && data.mode!=='hint');
    if(['draft','partition'].includes(data.mode))data.solution='';else data.draft='';
    if(workFiles.length){
      data.attachments=await Promise.all(workFiles.map(async item=>({name:item.file.name,base64:await fileToBase64(item.file)})));
    }
    const {id}=await api('/api/sessions/'+sessionId+'/submissions',data);clearWorkFiles();await sessions();history=await api('/api/sessions/'+sessionId);renderHistory();poll(id);
  }catch(error){$('form-status').textContent=error.message;$('submit').disabled=false;}
};
$('new-session').onclick=async()=>{const {id}=await api('/api/sessions',{});await loadSession(id);};
$('toggle-archived').onclick=()=>{showArchived=!showArchived;sessions();};
$('mode').onchange=setMode;
$('work-files').onchange=()=>{
  addWorkFiles([...$('work-files').files]);
  $('work-files').value='';
};
$('example').onclick=()=>{populate({problem:'在 0≤x<2π 内解 sin(2x)=sin(x)。',solution:'用二倍角公式得 2sin(x)cos(x)=sin(x)。\n两边除以 sin(x)，得 cos(x)=1/2。\n所以解只有 π/3 和 5π/3。',mode:'hint'});$('problem').focus();};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),session_id:sessionId,submissions:history},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download='数学练习-'+sessionId.slice(0,8)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};

let settingsBusy=false;
function settingsStatus(message,isError=false){const el=$('settings-status');el.textContent=message;el.className=isError?'error-message':'source-note';}
function showSettingsFields(){const http=$('settings-backend').value==='http';$('settings-http-fields').hidden=!http;$('settings-codex-fields').hidden=http;}
function settingsPayload(){return {backend:$('settings-backend').value,base_url:$('settings-base').value,model:$('settings-model').value,style:$('settings-style').value,codex_bin:$('settings-codex-bin').value,api_key:$('settings-key').value};}
async function loadSettings(){
  try{
    const data=await api('/api/settings');
    $('settings-backend').value=data.backend==='http'?'http':'codex-cli';
    $('settings-base').value=data.base_url||'';
    $('settings-model').value=data.model||'';
    $('settings-style').value=data.style||'chat';
    $('settings-codex-bin').value=data.codex_bin&&data.codex_bin!=='codex'?data.codex_bin:'';
    $('settings-key').value='';
    $('settings-key').placeholder=data.has_key?'已设置，留空保持不变':'未设置';
    $('settings-source').textContent=data.environment_locked?'当前由环境变量 MATH_API_BASE 覆盖；网页保存不会生效。':data.source==='ui'?'当前使用网页保存的设置。':'当前使用默认 Codex CLI 配置。';
    for(const id of ['settings-backend','settings-base','settings-model','settings-style','settings-codex-bin','settings-key','settings-save','settings-test'])$(id).disabled=data.environment_locked;
    showSettingsFields();
  }catch(error){settingsStatus('读取设置失败：'+error.message,true);}
}
async function refreshConnection(){
  try{const data=await api('/api/health');
    $('connection').textContent=data.available?(data.backend==='http'?'HTTP 模型接口已连接':'本地 Codex 已连接'):'请在模型设置中配置';
    verificationAvailable=data.exact_verification_available;setMode();
  }catch(error){$('connection').textContent='服务未连接';}
}
async function saveSettings(event){
  event.preventDefault();if(settingsBusy)return;settingsBusy=true;settingsStatus('正在保存…');
  try{const data=await api('/api/settings',settingsPayload());await loadSettings();await refreshConnection();settingsStatus('已保存。当前后端：'+(data.backend==='http'?'HTTP 接口':'Codex CLI'));}
  catch(error){settingsStatus(error.message,true);}
  finally{settingsBusy=false;}
}
async function testSettings(){
  if(settingsBusy)return;settingsBusy=true;settingsStatus('正在测试连接…');
  try{const data=await api('/api/settings/test',settingsPayload());settingsStatus(data.message||(data.ok?'连接正常。':'连接失败。'),!data.ok);}
  catch(error){settingsStatus(error.message,true);}
  finally{settingsBusy=false;}
}
$('open-settings').onclick=async()=>{if(typeof $('settings-dialog').showModal==='function')$('settings-dialog').showModal();else $('settings-dialog').setAttribute('open','');await loadSettings();};
$('close-settings').onclick=()=>{if(typeof $('settings-dialog').close==='function')$('settings-dialog').close();else $('settings-dialog').removeAttribute('open');};
$('settings-form').onsubmit=saveSettings;
$('settings-test').onclick=testSettings;
$('settings-backend').onchange=showSettingsFields;
const openedFromFile=location.protocol==='file:';
if(openedFromFile){
  $('file-launch-notice').hidden=false;
  $('connection').textContent='请启动本地服务';
  document.querySelector('.brand').href='http://127.0.0.1:8765/';
  document.querySelectorAll('button,input,textarea,select').forEach(control=>control.disabled=true);
}else{
  refreshConnection();
  sessions();setMode();
}

function switchWorkspace(name) {
  const teacher=name==='teacher', teaching=name==='teaching';
  $('practice-view').hidden=name!=='practice';$('teacher-view').hidden=!teacher;$('teaching-view').hidden=!teaching;
  document.title='数学作业智能体 · '+(teacher?'教师备课':teaching?'师生任务':'练习工作台');
  $('header-note').textContent='高中数学 · '+(teacher?'教师备课':teaching?'师生任务':'过程反馈');
  $('practice-sidebar').hidden=name!=='practice';$('teacher-sidebar').hidden=!teacher;
  for(const [key,id] of [['practice','show-practice'],['teacher','show-teacher'],['teaching','show-teaching']]){
    $(id).classList.toggle('active',key===name);$(id).setAttribute('aria-selected',String(key===name));
  }
  if(teacher)refreshLessonHistory();
}
$('show-practice').onclick=()=>switchWorkspace('practice');
$('show-teacher').onclick=()=>switchWorkspace('teacher');
let currentLesson=null,lessonBusy=false,lessonTeachingSource=null;
const lessonLabels={outline_ready:'大纲待确认',source_ready:'源码待渲染',ready:'课件已通过结构检查',review_failed:'需修改后复核',build_failed:'生成失败'};
function lessonStep(n){document.querySelectorAll('.teacher-step').forEach((el,i)=>el.classList.toggle('active',i===n));}
function showLesson(lesson){
  currentLesson=lesson;lessonTeachingSource=lesson.data?.teaching_source||null;$('lesson-empty').hidden=Boolean(lesson.outline);$('lesson-outline-stage').hidden=!lesson.outline;
  $('lesson-source-stage').hidden=!lesson.slides_markdown;$('lesson-badge').textContent=lessonLabels[lesson.status]||lesson.status;
  $('lesson-outline').value=lesson.outline||'';$('lesson-source').value=lesson.slides_markdown||'';
  $('lesson-topic').value=lesson.data?.topic||lesson.title||'';$('lesson-grade').value=lesson.data?.grade||'';
  $('lesson-textbook').value=lesson.data?.textbook||'';$('lesson-duration').value=lesson.data?.duration||'45分钟';
  $('lesson-draft').value=lesson.data?.source_text||'';$('lesson-file').value='';
  const missing=$('lesson-missing');missing.replaceChildren();const required=[...(lesson.missing||[]),...(lesson.questions||[])];missing.hidden=!required.length;
  if(!missing.hidden){missing.append(node('strong','大纲中仍有待确认的信息'));const list=node('ul');for(const item of required)list.append(node('li',item));missing.append(list);}
  $('lesson-clarifications').value=lesson.data?.clarifications||'';$('lesson-result').replaceChildren();
  if(lesson.result)renderLessonResult(lesson.result,lesson.id);
  lessonStep(lesson.slides_markdown?2:lesson.outline?1:0);
}
function renderLessonResult(result,id){
  const area=$('lesson-result');area.replaceChildren();
  if(result.errors?.length){const card=node('div',undefined,'lesson-result-card error');card.append(node('h3','课件还需要修改'));const list=node('ul');for(const item of result.errors)list.append(node('li',typeof item==='string'?item:JSON.stringify(item)));card.append(list);card.append(node('p','可在上方源码中修正后重新渲染。'));area.append(card);}
  if(result.warnings?.length){const card=node('div',undefined,'lesson-result-card warning');card.append(node('h3','复核提醒 · '+result.warnings.length+' 项'));const list=node('ul');for(const item of result.warnings)list.append(node('li',typeof item==='string'?item:JSON.stringify(item)));card.append(list);area.append(card);}
  if(result.slides){const card=node('div',undefined,'lesson-result-card');card.append(node('h3',result.errors?.length?'结构检查未通过':'结构检查完成'));card.append(node('p','共 '+result.slides+' 页。'+(result.scope||'')));card.append(node('p',result.animation_check||''));area.append(card);}
  if(result.logs){const details=node('details');details.append(node('summary','查看本地构建日志'));details.append(node('pre',JSON.stringify(result.logs,null,2)));area.append(details);}
  const downloads=node('div',undefined,'lesson-downloads');const source=node('a','下载课件 Markdown');source.href='/api/lessons/'+id+'/files/source';downloads.append(source);
  if(currentLesson?.status==='ready'&&!result.errors?.length){const deck=node('a','下载 PowerPoint ↗');deck.href='/api/lessons/'+id+'/files/deck';downloads.append(deck);}
  area.append(downloads);
}
async function refreshLessonHistory(){
  try{const rows=await api('/api/lessons');const list=$('lesson-history');list.replaceChildren();
    if(!rows.length){list.append(node('p','还没有备课记录。','history-empty'));return;}
    for(const row of rows){const wrap=node('div',undefined,'lesson-history-row');const button=node('button',undefined);button.append(node('strong',row.title||'未命名课件'));button.append(node('small',(lessonLabels[row.status]||row.status)+' · '+new Date(row.created).toLocaleDateString('zh-CN')));button.onclick=async()=>{try{showLesson(await api('/api/lessons/'+row.id));}catch(error){$('lesson-status').textContent=error.message;}};wrap.append(button);list.append(wrap);}
  }catch(error){$('lesson-history').replaceChildren(node('p','读取备课记录失败。','history-empty'));}
}
function fileToBase64(file){
  return file.arrayBuffer().then(buffer=>{const bytes=new Uint8Array(buffer);let binary='';for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(binary);});
}
function lessonBusyState(message){
  lessonBusy=true;$('lesson-outline-button').disabled=true;$('lesson-source-button').disabled=true;$('lesson-render-button').disabled=true;
  $('lesson-status').textContent=message;
}
function lessonDone(message=''){
  lessonBusy=false;$('lesson-outline-button').disabled=false;$('lesson-source-button').disabled=false;$('lesson-render-button').disabled=false;
  $('lesson-status').textContent=message;
}
$('lesson-form').onsubmit=async event=>{
  event.preventDefault();if(lessonBusy)return;
  try{
    const file=$('lesson-file').files[0];if(file&&file.size>5*1024*1024)throw new Error('文件不能超过 5 MB。');
    const deckType=document.querySelector('input[name="deck-type"]:checked').value;
    const payload={topic:$('lesson-topic').value,grade:$('lesson-grade').value,textbook:$('lesson-textbook').value,duration:$('lesson-duration').value,deck_type:deckType,draft_text:$('lesson-draft').value};
    if(lessonTeachingSource)payload.teaching_source=lessonTeachingSource;
    if(file){payload.file_name=file.name;payload.file_base64=await fileToBase64(file);}
    lessonBusyState('正在依据课件 Skill 梳理教案并生成逐页大纲…');
    currentLesson=await api('/api/lessons/outline',payload);showLesson(currentLesson);lessonDone('请逐页核对大纲与待补充信息，再确认进入课件源码。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
$('lesson-source-button').onclick=async()=>{
  if(lessonBusy||!currentLesson)return;
  try{lessonBusyState('已提交大纲确认，正在生成可编辑课件源码…');
    currentLesson=await api('/api/lessons/'+currentLesson.id+'/source',{outline:$('lesson-outline').value,clarifications:$('lesson-clarifications').value});
    showLesson(currentLesson);lessonDone('请检查页序、公式、例题和图示描述；确认后再渲染。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
$('lesson-render-button').onclick=async()=>{
  if(lessonBusy||!currentLesson)return;
  try{lessonBusyState('正在生成配图、渲染 PowerPoint，并运行独立版式检查…');
    const result=await api('/api/lessons/'+currentLesson.id+'/render',{slides_markdown:$('lesson-source').value});
    currentLesson=await api('/api/lessons/'+currentLesson.id);showLesson(currentLesson);lessonDone(result.status==='ready'?'结构检查通过。请下载并在实际放映软件中通看，数学内容仍需教师审阅。':'检查未通过；根据上方告警修订源码后重试。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
if(!openedFromFile)refreshLessonHistory();
