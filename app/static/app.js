const $ = id => document.getElementById(id);
let sessionId = null, history = [], busy = false, currentPoll = 0, verificationAvailable = true, renderedMode = null;
let setupRequired = false;
function refreshSubmitState(){const button=$('submit');if(button)button.disabled=Boolean(busy||setupRequired);}
const labels = {queued:'排队中',running:'正在思考',ready:'反馈已生成',needs_input:'待补充材料',gate_failed:'需要复核',diagnosis_required:'需先完成纠错',handoff_rejected:'交接未通过',error:'调用失败',interrupted:'运行已中断'};
const skillNames = {'math-error-diagnosis':'过程诊断','answer-key-builder':'参考答案','draft-coach':'草稿版面','draft-coach-partition':'草稿版面分块','solution-refiner':'解法优化',diagnosis:'过程诊断',handoff:'交接核验'};
const MODE_COPY = {
  check: {eyebrow:'YOUR NEXT STEP IN MATHEMATICS',h1:'把思路写下来，<em>再向前一步。</em>',subtitle:'从一个有依据的提示开始，逐步完善自己的解答。',folio:'练习工作台',headerNote:'过程反馈',title:'练习工作台',inputHeading:'这一次，练什么？',submit:'开始检查 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:4,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'写下你实际做过的步骤，暂时不会的地方也可以留着。',feedbackHeading:'反馈与下一步',revisionNote:'你的原过程会随每次提交保留。',requestPlaceholder:'例如：沿用我的方法，暂时不要给答案。',exampleLabel:'载入示例 ↗',empty:{mark:'f′(x)',h3:'先写出你的尝试',p:'这里会展示检查依据、首错位置，或一个帮助你继续思考的提示。',small:'过程比一个答案更值得被看见'}},
  hint: {eyebrow:'ONE STEP AT A TIME',h1:'卡住时，先要一个<em>提示</em>。',subtitle:'一次只给一点提示，保留自己继续推理的空间。',folio:'练习工作台',headerNote:'过程反馈',title:'练习工作台',inputHeading:'这一次，练什么？',submit:'给我一个提示 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:4,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'写下你实际做过的步骤，暂时不会的地方也可以留着。',feedbackHeading:'反馈与下一步',revisionNote:'你的原过程会随每次提交保留。',requestPlaceholder:'例如：只提示下一步，不要给答案。',exampleLabel:'载入示例 ↗',empty:{mark:'?',h3:'需要一点提示？',p:'提交后会收到一个最小提示，答案不会一次给完。',small:'先保留自己的尝试'}},
  full_correction: {eyebrow:'FULL CORRECTION',h1:'把问题讲清楚，<em>再完整走一遍。</em>',subtitle:'解释问题并给出完整纠正；这会记录为一次获得讲解。',folio:'练习工作台',headerNote:'过程反馈',title:'练习工作台',inputHeading:'这一次，练什么？',submit:'完整纠正 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:4,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'写下你实际做过的步骤，暂时不会的地方也可以留着。',feedbackHeading:'反馈与下一步',revisionNote:'这次反馈会记录为一次获得完整讲解。',requestPlaceholder:'例如：先指出问题，再给出完整纠正。',exampleLabel:'载入示例 ↗',empty:{mark:'f′(x)',h3:'写下的过程会得到完整纠正',p:'这里会指出问题所在，并给出完整的纠正过程。',small:'完整纠正会记录为获得讲解'}},
  answer_check: {eyebrow:'ANSWER CHECK',h1:'先对上答案，<em>再决定要不要查过程。</em>',subtitle:'只核对最终答案；系统不会推断你没有写出的步骤。',folio:'练习工作台',headerNote:'仅核对答案',title:'练习工作台',inputHeading:'这一次，练什么？',submit:'核对答案 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:4,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的答案',solutionHint:'只写最终答案',solutionRows:3,solutionPlaceholder:'例如：x=π/3 和 x=5π/3。',feedbackHeading:'答案核验',revisionNote:'只核验答案时，过程不会被推断或评价。',requestPlaceholder:'例如：只告诉我答案对不对。',exampleLabel:'载入示例 ↗',empty:{mark:'=',h3:'只写最终答案也可以',p:'这里会告诉你答案是否成立；不会推断你没有写出的步骤。',small:'需要过程反馈时，切换到“检查我的过程”'}},
  refine: {eyebrow:'REFINE A VERIFIED SOLUTION',h1:'已经写对，<em>再往简洁处走一步。</em>',subtitle:'先核验当前过程，再讨论更简洁或更通用的方法。',folio:'练习工作台',headerNote:'解法优化',title:'练习工作台',inputHeading:'提交已完成的解法',submit:'先核验再优化 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:4,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的解题过程',solutionHint:'提交完整步骤，系统会先核验',solutionPlaceholder:'写下完整的解题步骤，暂时不会的地方也可以留着。',feedbackHeading:'优化方向与下一步',revisionNote:'只有核验通过后才会进入优化；未通过时先回到诊断。',requestPlaceholder:'例如：想看看有没有更短的方法。',exampleLabel:'载入示例 ↗',empty:{mark:'↗',h3:'先提交一份完整解法',p:'核验通过后，这里会给出有依据的优化方向。',small:'不是错因诊断，也不替你重写整题'}},
  solve: {eyebrow:'SOLVE FROM THE PROBLEM',h1:'把题目交给我，<em>给出一份完整解答。</em>',subtitle:'从题目出发求解并核验；保存为助手求解稿，不会当作你的作业。',folio:'求解工作台',headerNote:'完整求解',title:'完整求解',inputHeading:'输入题目',submit:'开始求解 ',problemLabel:'原题 ',problemHint:'保留完整条件与范围',problemRows:7,problemPlaceholder:'例如：在 0≤x<2π 内解 sin(2x)=sin(x)。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'',feedbackHeading:'完整解答与核验',revisionNote:'这里生成的是助手解答，不是你的解答。',requestPlaceholder:'例如：优先使用高中方法，给出完整推导。',exampleLabel:'载入题目示例 ↗',empty:{mark:'∑',h3:'完整解答会在这里生成',p:'提交原题后，查看推导、答案与独立核验。',small:'助手解答，不是你的作业'}},
  exam_answer: {eyebrow:'MATHEMATICS · ANSWER STUDIO',h1:'一份试卷，一份有依据的参考答案。',subtitle:'面向整份试卷的编制工具，让解答与每一个采分点清晰对应。',folio:'参考答案编制',headerNote:'试卷参考答案',title:'试卷参考答案',inputHeading:'输入试卷',submit:'生成参考答案 ',problemLabel:'试卷题目与分值 ',problemHint:'保留完整条件与范围',problemRows:14,problemPlaceholder:'粘贴完整试卷，保留题号、小问、条件与分值。\n例如：1.（5分）……\n2.（12分）（1）……（2）……',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'',feedbackHeading:'参考答案与评分建议',revisionNote:'未给分值将标为待确认；建议评分仍需教师核定。',requestPlaceholder:'例如：高三复习；保留全部小问；优先使用高中方法。',exampleLabel:'载入试卷示例 ↗',empty:{mark:'∑ → ▢',h3:'参考答案将在这里生成',p:'提交试卷后，逐题查看解答、采分点、分值、思路和难度评价。',small:'完整条件，是可靠答案的起点'}},
  draft: {eyebrow:'DRAFT LAYOUT · SIX DIMENSIONS',h1:'先看草稿怎么排，<em>不看算得对不对。</em>',subtitle:'只看分区、分行、划改与留白；数学对错请用“检查我的过程”。',folio:'草稿版面',headerNote:'草稿版面',title:'草稿版面',inputHeading:'草稿怎么排的？',submit:'分析草稿 ',problemLabel:'原题（可选） ',problemHint:'有原题时便于核对',problemRows:3,problemPlaceholder:'有原题就粘贴在这里；没有也可以只描述草稿版面。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'',feedbackHeading:'版面观察与下一步',revisionNote:'草稿原文会随每次提交保留；这里不判断计算对错。',requestPlaceholder:'例如：重点看看分类讨论有没有标号。',exampleLabel:'载入草稿示例 ↗',empty:{mark:'▤',h3:'草稿会按版面来读',p:'这里会展示六个版面维度的观察，以及下一道题能做的一个动作。',small:'不判断计算对错'}},
  partition: {eyebrow:'DRAFT LAYOUT · PARTITION',h1:'一张草稿纸，<em>先按版面分块。</em>',subtitle:'给出块数与估计范围；块数不等于题目数，归属由你确认。',folio:'草稿版面',headerNote:'草稿版面',title:'草稿版面',inputHeading:'整张草稿怎么分块？',submit:'分析草稿 ',problemLabel:'原题（可选） ',problemHint:'有原题时便于核对',problemRows:3,problemPlaceholder:'有原题就粘贴在这里；没有也可以只描述草稿版面。',solutionLabel:'我的解题过程',solutionHint:'建议每一步另起一行',solutionPlaceholder:'',feedbackHeading:'版面分块与确认',revisionNote:'草稿原文会随每次提交保留；块数不等于题目数。',requestPlaceholder:'例如：只按版面分块，不读具体算式。',exampleLabel:'载入草稿示例 ↗',empty:{mark:'▥',h3:'先分块，再确认归属',p:'这里会给出块数、估计范围与确认问题。',small:'块数不等于题目数'}}
};
function modeCopy(mode){return MODE_COPY[mode]||MODE_COPY.check;}
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
  const mode=$('mode').value, draft=['draft','partition'].includes(mode), exam=mode==='exam_answer';
  $('draft-field').hidden=!draft;
  $('solution-field').hidden=draft||exam||mode==='solve';
  updateModePresentation(mode);
  $('submit').firstChild.textContent=modeCopy(mode).submit;
  const verify=$('verify-equation');
  verify.disabled=!verificationAvailable||draft||mode==='hint';if(verify.disabled)verify.checked=false;
  $('verify-option').hidden=draft;
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
  currentPoll++; sessionId=id; busy=false; refreshSubmitState();$('session-status').textContent='';
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
  const area=$('result');area.replaceChildren();renderedMode=item.data?.mode||null;$('state-badge').textContent=labels[item.state]||item.state;
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
    renderStructuredResult(area,item,run.output.result);
    const checks=(run.attempts?.at(-1)?.gates||[]).filter(g=>g.gate==='exact-math');
    for(const check of checks){const card=node('div',undefined,'evidence-card');card.append(node('h3',check.exit_code===0?'已执行等式核验':'等式核验待复核'));card.append(node('p',check.source_quote||'核验请求'));for(const point of check.record?.checks||[])card.append(node('p',(check.record.request?.variable||'x')+'='+point.value+'：左边 '+point.left+'，右边 '+point.right+'，差值 '+point.residual));if(check.record?.residual!==undefined)card.append(node('p','展开后差值为 '+check.record.residual));card.append(node('p',check.record?.scope||check.scope));area.append(card);}
    if(item.is_current && item.data.solution){const actions=node('div',undefined,'result-actions');const revise=node('button','修改后再检查 ↗');revise.onclick=()=>{$('solution').focus();$('solution').scrollIntoView({behavior:'smooth',block:'center'});};actions.append(revise);area.append(actions);}
    if(item.is_current && item.data.mode==='partition'){const actions=node('div',undefined,'result-actions');const next=node('button','换到草稿习惯分析 ↗');next.onclick=()=>{populate({...item.data,mode:'draft'});$('draft').focus();$('draft').scrollIntoView({behavior:'smooth',block:'center'});};actions.append(next);area.append(actions);}
    if(item.is_current && item.data.mode==='exam_answer')mountExamExport(area,item);
  }
  const routed=run.routing?.action==='partition'?'draft-coach-partition':(run.stage||run.routing?.skill);
  area.append(node('div',(skillNames[routed]||routed||'待补充')+' · 第 '+item.revision+' 版 · '+item.version.slice(0,10),'result-meta'));
  const details=node('details');details.append(node('summary','查看校验与运行记录'));
  const safe={routing:run.routing,status:run.status,stage:run.stage,handoff:run.handoff,limitation:run.limitation,attempts:(run.attempts||[]).map(a=>({elapsed_seconds:a.response?.elapsed_seconds,usage:a.response?.usage,gates:a.gates,stage:a.stage})),structured_result:run.output?.result};
  details.append(node('pre',JSON.stringify(safe,null,2)));area.append(details);
  renderMath(area);
}
const judgementNames={correct:'过程成立',incorrect:'存在错误',gap:'论证有缺口',insufficient:'信息不足',answer_only:'仅核验了答案'};
const dimensionNames={organization:'分区与边距',skipping:'步骤分行与密度',correction_pattern:'划改与自纠',trial_and_error:'多路径标记',graphic_use:'图形与标注',draft_to_solution:'留白与检验区'};
const solveStatusNames={solved:'完整求解',partially_solved:'部分完成',needs_clarification:'需要补充信息',failed:'求解失败'};
function resultCard(area,title){const card=node('div',undefined,'evidence-card');if(title)card.append(node('h3',title));area.append(card);return card;}
function renderStructuredResult(area,item,result){
  if(!result || typeof result!=='object')return;
  if(result.judgment){
    if(judgementNames[result.judgment])area.append(node('p','判断：'+judgementNames[result.judgment],'result-judgment'));
    if(item.data.mode==='answer_check'){
      area.append(node('p','本次只核验最终答案；没有评价解题过程。','source-note'));
      if(result.minimal_fix){const card=resultCard(area,'正确结果');card.append(node('p',result.minimal_fix));}
      return;
    }
    if(item.data.mode!=='hint' && Array.isArray(result.evidence) && result.evidence.length){
      const card=resultCard(area,'检查依据'),list=node('ul');
      for(const line of result.evidence)list.append(node('li',String(line)));
      card.append(list);
    }
    if(item.data.mode==='hint' && result.hint){const card=resultCard(area,'提示');card.append(node('p',result.hint));}
    if(result.first_error && item.data.mode!=='hint'){
      const card=resultCard(area,'首个实质问题 · 第 '+result.first_error.step+' 步');
      card.append(node('blockquote',result.first_error.quote));card.append(node('p',result.first_error.reason));
    }
    if(result.minimal_fix && item.data.mode!=='hint'){const card=resultCard(area,'最小修改');card.append(node('p',result.minimal_fix));}
    return;
  }
  if(result.dimensions){
    const card=resultCard(area,'六维版面观察');
    if(result.scope)card.append(node('p',result.scope,'result-scope'));
    const grid=node('div',undefined,'dimension-grid');
    for(const [key,name] of Object.entries(dimensionNames)){
      const dimension=result.dimensions[key];if(!dimension)continue;
      const row=node('section',undefined,'dimension-row'),head=node('div',undefined,'dimension-head');
      head.append(node('strong',name));head.append(node('span',dimension.score||'','dimension-score'));row.append(head);
      if(dimension.observation)row.append(node('p',dimension.observation));
      if(dimension.evidence)row.append(node('p','依据：'+dimension.evidence,'dimension-detail'));
      if(dimension.risk)row.append(node('p','风险：'+dimension.risk,'dimension-detail'));
      if(dimension.positive)row.append(node('p','积极信号：'+dimension.positive,'dimension-positive'));
      grid.append(row);
    }
    if(grid.children.length)card.append(grid);
    if(Array.isArray(result.top_3_habits)&&result.top_3_habits.length){
      card.append(node('h3','值得调整的版面习惯'));
      for(const [index,habit] of result.top_3_habits.entries()){
        const block=node('section',undefined,'optimization-item');
        block.append(node('strong',(index+1)+' · '+(habit.habit||'')));
        if(habit.impact)block.append(node('p','可能影响：'+habit.impact));
        if(habit.training)block.append(node('small','下一道题可以：'+habit.training));
        card.append(block);
      }
    }
    if(result.next_step)card.append(node('p','下一步只做一件事：'+result.next_step,'result-next-step'));
    return;
  }
  if(Array.isArray(result.blocks)){
    const card=resultCard(area,'版面分块');
    if(result.estimated_problem_count!==undefined){
      const range=Array.isArray(result.count_range)?result.count_range.join('–'):'';
      card.append(node('p','估计 '+result.estimated_problem_count+' 道题'+(range?'（范围 '+range+'）':'')+'。这是版面块数，不等于题目数。','result-judgment'));
    }
    for(const block of result.blocks){
      const row=node('section',undefined,'partition-block'),head=node('div',undefined,'dimension-head');
      head.append(node('strong',(block.block_id||'')+' · '+(block.location||'')));
      head.append(node('span',(block.confidence?'置信度 '+block.confidence:'')+(block.separate_problem?' · 像独立题目':' · 可能不是独立题目'),'dimension-score'));
      row.append(head);
      if(block.visual_cues)row.append(node('p','版面依据：'+block.visual_cues,'dimension-detail'));
      if(block.note)row.append(node('p',block.note,'dimension-detail'));
      card.append(row);
    }
    if(result.uncertainty)card.append(node('p','分不准的地方：'+result.uncertainty));
    if(result.confirmation_question)card.append(node('p','请确认：'+result.confirmation_question,'result-next-step'));
    if(Array.isArray(result.limitations)&&result.limitations.length){const list=node('ul');for(const line of result.limitations)list.append(node('li',String(line)));card.append(list);}
    return;
  }
  if(Array.isArray(result.optimization_opportunities)){
    const card=resultCard(area,'三个可尝试的优化方向');
    if(result.current_method)card.append(node('p','当前方法：'+result.current_method));
    if(result.overall_diagnosis)card.append(node('p',result.overall_diagnosis,'result-scope'));
    for(const [index,option] of result.optimization_opportunities.entries()){
      const block=node('section',undefined,'optimization-item');
      block.append(node('strong',(index+1)+' · '+option.direction));
      block.append(node('p',option.suggestion));
      block.append(node('p','本解答尚未展示：'+option.exposed_gap));
      block.append(node('small','现在可以试：'+option.training_suggestion));
      card.append(block);
    }
    if(result.next_step)card.append(node('p','下一步动作：'+result.next_step,'result-next-step'));
    return;
  }
  if(result.status && result.solution && item.data.mode==='solve'){
    const card=resultCard(area,'求解状态与核验');
    card.append(node('p','状态：'+(solveStatusNames[result.status]||result.status),'result-judgment'));
    if(result.solution.answer)card.append(node('p','答案：'+result.solution.answer));
    const details=node('details');details.append(node('summary','查看结构化推导与核验'));
    for(const step of result.solution.derivation||[])details.append(node('p','第 '+step.step+' 步：'+(step.expression||'')+(step.justification?'（依据：'+step.justification+'）':'')));
    if(result.verification){
      if(result.verification.status)details.append(node('p','核验状态：'+result.verification.status));
      for(const check of result.verification.checks||[])details.append(node('p',(check.name||'检查')+'：'+(check.status||'')+(check.details?' · '+check.details:'')));
      for(const issue of result.verification.issues||[])details.append(node('p','未解决：'+issue,'error-message'));
    }
    card.append(details);
  }
}
function mountExamExport(area,item){
  const card=node('div',undefined,'evidence-card exam-export');
  area.append(card);
  async function refresh(errorMessage=''){
    card.replaceChildren(node('h3','导出参考答案文件'));
    let data;
    try{data=await api('/api/submissions/'+item.id+'/export');}
    catch(error){card.append(node('p',error.message,'error-message'));return;}
    const report=data.report,files=data.files||{};
    if(files.pdf){const links=node('div',undefined,'result-actions');const pdf=node('a','下载 PDF ↗','attachment-link');pdf.href=files.pdf;pdf.target='_blank';pdf.rel='noopener noreferrer';links.append(pdf);card.append(links);}
    if(report){
      card.append(node('p',report.success?'PDF 已编译完成；请打开逐页检查公式、分页与评分标记。':'导出尚未完成，可重试。', report.success?'':'error-message'));
      if(report.issues?.length){const list=node('ul');for(const issue of report.issues.slice(0,8))list.append(node('li',String(issue)));card.append(list);}
    }
    if(!data.can_compile){
      card.append(node('p','本机未找到 XeLaTeX，暂时无法导出 PDF。','source-note'));
    }else{
      const actions=node('div',undefined,'result-actions');
      const run=node('button',report?'重新生成 PDF':'生成并导出 PDF');
      run.onclick=async()=>{
        run.disabled=true;run.textContent='正在排版并编译…';
        let failure='';
        try{
          let job=await api('/api/jobs',{kind:'exam-export',payload:{submission_id:item.id}});
          refreshJobs();
          while(['queued','running'].includes(job.state)){await new Promise(resolve=>setTimeout(resolve,900));job=await api('/api/jobs/'+job.id);}
          if(job.state!=='completed')throw new Error((job.error||'导出任务未完成')+' 可在任务中心查看并继续。');
        }catch(error){failure=error.message;}
        await refresh(failure);
      };
      actions.append(run);card.append(actions);
    }
    if(errorMessage)card.append(node('p',errorMessage,'error-message'));
    card.append(node('p','导出只做排版与实际编译，不重新验证数学、题号覆盖或评分建议；请对照在线答案人工核对。','source-note'));
  }
  refresh();
}

async function poll(id) {
  const token=++currentPoll;busy=true;refreshSubmitState();
  while(token===currentPoll){
    try {const item=await api('/api/submissions/'+id);if(token!==currentPoll)return;renderResult(item);
      if(!['queued','running'].includes(item.state)){history=await api('/api/sessions/'+sessionId);renderHistory();busy=false;refreshSubmitState();$('form-status').textContent='';if(window.matchMedia('(max-width:1080px)').matches)$('feedback-heading').scrollIntoView({behavior:'smooth',block:'start'});return;}
    } catch(error){$('form-status').textContent=error.message;busy=false;refreshSubmitState();return;}
    await new Promise(resolve=>setTimeout(resolve,1500));
  }
}
$('submission-form').onsubmit=async event=>{
  event.preventDefault();
  if(setupRequired){openSettings();settingsStatus('请先选择模型服务并保存，再开始检查。',true);return;}
  if(busy)return;busy=true;$('form-status').textContent='正在提交…';refreshSubmitState();
  try{
    if(!sessionId)sessionId=(await api('/api/sessions',{})).id;
    const data=Object.fromEntries(['problem','solution','draft','request','mode'].map(k=>[k,$(k).value]));data.grade_level=$('grade').value;
    data.verification_requested=$('verify-equation').checked;
    const old=history.at(-1);data.allow_mode_change=Boolean(old && old.data.mode==='hint' && data.mode!=='hint');
    if(['draft','partition','exam_answer','solve'].includes(data.mode))data.solution='';else data.draft='';
    if(data.mode==='exam_answer'||data.mode==='solve')data.draft='';
    if(workFiles.length){
      data.attachments=await Promise.all(workFiles.map(async item=>({name:item.file.name,base64:await fileToBase64(item.file)})));
    }
    const {id}=await api('/api/sessions/'+sessionId+'/submissions',data);clearWorkFiles();await sessions();history=await api('/api/sessions/'+sessionId);renderHistory();poll(id);
  }catch(error){$('form-status').textContent=error.message;busy=false;refreshSubmitState();}
};
$('new-session').onclick=async()=>{const exam=$('mode').value==='exam_answer';const {id}=await api('/api/sessions',{});await loadSession(id);if(exam){$('mode').value='exam_answer';setMode();}};
$('toggle-archived').onclick=()=>{showArchived=!showArchived;sessions();};
$('mode').onchange=setMode;
$('work-files').onchange=()=>{
  addWorkFiles([...$('work-files').files]);
  $('work-files').value='';
};
const EXAMPLES={
  exam_answer:{mode:'exam_answer',problem:'高中数学小卷（共15分）\n1.（5分，填空题）解方程 √(x+2)=x。\n2.（10分，解答题）已知 f(x)=x²-2x。\n（1）求 f(x) 的最小值；（2）解不等式 f(x)≤3。',request:'保留题号与小问；步骤分值请标为建议，给出思路点拨和难度理由。'},
  draft:{mode:'draft',problem:'在 0≤x<2π 内解 sin(2x)=sin(x)。',draft:'整张纸只写了一道题。左上是抄写的题目，中间推导分成四行；有一处划改，旧值没有划掉，新值直接写在右边；右侧留出一栏写分类讨论的第二种情况，但没有编号；底部留了三行空白，没有检验区。'},
  partition:{mode:'partition',draft:'纸面大致分三块：左上以“第一题”开头，围绕三角函数写了五六行；左下另起一块，标着“第二题”，只有两行；右侧一整块画着带坐标轴的图，图旁另有几行计算。左下和右侧之间只有一道横线，可能是同一题的继续，也可能不是。'},
  answer_check:{mode:'answer_check',problem:'解方程 x+1=2。',solution:'x=1'},
  refine:{mode:'refine',problem:'在 0≤x<2π 内解 sin(2x)=sin(x)。',solution:'移项得 2sin(x)cos(x)-sin(x)=0。\n提取 sin(x)：sin(x)(2cos(x)-1)=0。\n所以 sin(x)=0 或 cos(x)=1/2。\n在 0≤x<2π 内，解为 x=0, π, π/3, 5π/3。'},
  solve:{mode:'solve',problem:'在 0≤x<2π 内解 sin(2x)=sin(x)。'},
  practice:{mode:null,problem:'在 0≤x<2π 内解 sin(2x)=sin(x)。',solution:'用二倍角公式得 2sin(x)cos(x)=sin(x)。\n两边除以 sin(x)，得 cos(x)=1/2。\n所以解只有 π/3 和 5π/3。'}
};
$('example').onclick=()=>{
  const mode=$('mode').value, sample=EXAMPLES[mode]||EXAMPLES.practice;
  const data={...sample};if(mode&&mode!=='exam_answer'&&mode!=='draft'&&mode!=='partition'&&mode!=='answer_check'&&mode!=='solve')data.mode=mode;
  populate(data);
  (mode==='draft'||mode==='partition'?$('draft'):mode==='solve'||mode==='exam_answer'?$('problem'):mode==='answer_check'?$('solution'):$('problem')).focus();
};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),session_id:sessionId,submissions:history},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download='数学练习-'+sessionId.slice(0,8)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};

let settingsBusy=false, settingsPresets=[], currentPreset='custom';
function settingsStatus(message,isError=false){const el=$('settings-status');el.textContent=message;el.className=isError?'error-message':'source-note';}
function backendLabel(backend){return backend==='http'?'HTTP 接口':backend==='dsh-cli'?'DeepSeek Harness':'Codex CLI';}
function showSettingsFields(){
  const backend=$('settings-backend').value;
  $('settings-http-fields').hidden=backend!=='http';
  $('settings-key-fields').hidden=backend==='codex-cli';
  $('settings-codex-fields').hidden=backend!=='codex-cli';
  $('settings-dsh-fields').hidden=backend!=='dsh-cli';
}
function settingsPayload(){return {backend:$('settings-backend').value,base_url:$('settings-base').value,model:$('settings-model').value,style:$('settings-style').value,codex_bin:$('settings-codex-bin').value,dsh_bin:$('settings-dsh-bin').value,api_key:$('settings-key').value,provider:currentPreset};}
function presetById(id){return settingsPresets.find(preset=>preset.id===id);}
function updateModelOptions(preset){
  const list=$('settings-model-options');if(!list)return;
  list.replaceChildren();
  for(const name of (preset?.models||[])){const option=document.createElement('option');option.value=name;list.append(option);}
}
function renderPresets(){
  const box=$('settings-presets');if(!box)return;
  box.replaceChildren();
  for(const preset of settingsPresets){
    const card=node('button',undefined,'preset-card');card.type='button';
    card.append(node('strong',preset.label));
    card.append(node('small',preset.description||''));
    if(preset.id==='custom')card.append(node('span','老师提供的地址','preset-tag'));
    card.classList.toggle('active',preset.id===currentPreset);
    card.disabled=Boolean($('settings-backend').disabled);
    card.onclick=()=>applyPreset(preset.id);
    box.append(card);
  }
}
function applyPreset(id){
  const preset=presetById(id);if(!preset)return;
  const previous=currentPreset;currentPreset=id;
  $('settings-backend').value=preset.backend;
  if(preset.backend==='http'){
    if(preset.base_url)$('settings-base').value=preset.base_url;
    if(preset.style)$('settings-style').value=preset.style;
    if(preset.model)$('settings-model').value=preset.model;
    if(preset.id==='custom'&&previous!=='custom'){$('settings-base').value='';$('settings-model').value='';}
  }
  updateModelOptions(preset);showSettingsFields();renderPresets();
  if(preset.requires_key===false){
    settingsStatus(preset.id==='ollama'?'本机服务不需要 API Key；确认 Ollama 已启动后点“测试并保存”。':'这个服务不需要 API Key；直接点“测试并保存”。');
    $('settings-model').focus();
  }else if(preset.id==='custom'){
    settingsStatus('请在高级设置中填写老师提供的接口地址，再填写模型名和 API Key。');
    $('settings-advanced').open=true;$('settings-base').focus();
  }else{
    settingsStatus('已选择 '+preset.label+'，填入 API Key 后点“测试并保存”。');
    $('settings-key').focus();
  }
}
function inferPreset(data){
  if(data.source==='default')return '';
  const match=settingsPresets.find(preset=>preset.base_url&&preset.backend===data.backend&&preset.base_url===data.base_url);
  if(match)return match.id;
  if(data.provider&&data.provider!=='custom'&&presetById(data.provider))return data.provider;
  return data.provider&&presetById(data.provider)?data.provider:(data.backend==='http'?'custom':data.backend);
}
async function loadSettings(){
  try{
    const data=await api('/api/settings');
    try{const payload=await api('/api/settings/presets');settingsPresets=Array.isArray(payload.presets)?payload.presets:[];}
    catch(_){settingsPresets=[];}
    $('settings-backend').value=['http','dsh-cli'].includes(data.backend)?data.backend:'codex-cli';
    $('settings-base').value=data.base_url||'';
    $('settings-model').value=data.model||'';
    $('settings-style').value=data.style||'chat';
    $('settings-codex-bin').value=data.codex_bin&&data.codex_bin!=='codex'?data.codex_bin:'';
    $('settings-dsh-bin').value=data.dsh_bin&&data.dsh_bin!=='dsh'?data.dsh_bin:'';
    $('settings-key').value='';
    $('settings-key').placeholder=data.has_key?'已设置，留空保持不变':'未设置';
    $('settings-source').textContent=data.environment_locked?'老师已通过环境变量统一配置，学生无需修改。':data.source==='ui'?'当前使用本机保存的配置。':'还没有配置模型服务；按下面两步即可开始。';
    currentPreset=inferPreset(data);
    updateModelOptions(presetById(currentPreset));
    renderPresets();showSettingsFields();
    const locked=Boolean(data.environment_locked);
    for(const id of ['settings-backend','settings-base','settings-model','settings-style','settings-codex-bin','settings-dsh-bin','settings-key','settings-save','settings-save-test','settings-test'])$(id).disabled=locked;
    document.querySelectorAll('#settings-presets button').forEach(button=>button.disabled=locked);
  }catch(error){settingsStatus('读取设置失败：'+error.message,true);}
}
async function refreshConnection(){
  try{const data=await api('/api/health');
    const setup=data.setup||{};
    setupRequired=Boolean(setup.required);
    $('connection').textContent=data.available?(data.backend==='http'?'HTTP 模型接口已配置':data.backend==='dsh-cli'?'DeepSeek Harness 已找到':'本地 Codex 已找到'):'模型未配置';
    if(setupRequired){
      $('setup-banner').hidden=false;
      $('setup-banner-title').textContent='还差一步：配置模型服务';
      $('setup-banner-text').textContent=setup.message||'配置模型服务后即可开始检查。';
      $('connection').textContent='模型未配置';
    }else{
      $('setup-banner').hidden=true;
    }
    verificationAvailable=data.exact_verification_available;setMode();refreshSubmitState();
  }catch(error){$('connection').textContent='服务未连接';setupRequired=true;refreshSubmitState();}
}
async function saveSettings(event){
  if(event)event.preventDefault();if(settingsBusy)return;settingsBusy=true;settingsStatus('正在保存…');
  try{const data=await api('/api/settings',settingsPayload());await loadSettings();await refreshConnection();settingsStatus('已保存。当前后端：'+backendLabel(data.backend));}
  catch(error){settingsStatus(error.message,true);}
  finally{settingsBusy=false;}
}
async function testSettings({saveAfter=false}={}){
  if(settingsBusy)return;settingsBusy=true;settingsStatus('正在测试连接…');
  try{
    const data=await api('/api/settings/test',settingsPayload());
    if(!data.ok){settingsStatus(data.message||'连接失败，请检查设置。',true);return;}
    if(saveAfter){
      settingsStatus('连接成功，正在保存…');
      const saved=await api('/api/settings',settingsPayload());
      await loadSettings();await refreshConnection();
      settingsStatus('连接成功，已保存。当前后端：'+backendLabel(saved.backend));
    }else{
      settingsStatus(data.message||'连接正常。');
    }
  }catch(error){settingsStatus(error.message,true);}
  finally{settingsBusy=false;}
}
async function openSettings(){
  const dialog=$('settings-dialog');
  if(!dialog.open){
    if(typeof dialog.showModal==='function')dialog.showModal();
    else dialog.setAttribute('open','');
  }
  await loadSettings();
}
$('open-settings').onclick=openSettings;
$('setup-banner-action').onclick=openSettings;
$('close-settings').onclick=()=>{if(typeof $('settings-dialog').close==='function')$('settings-dialog').close();else $('settings-dialog').removeAttribute('open');};
$('settings-form').onsubmit=saveSettings;
$('settings-save-test').onclick=()=>testSettings({saveAfter:true});
$('settings-test').onclick=()=>testSettings();
$('settings-backend').onchange=()=>{currentPreset=$('settings-backend').value==='http'?'custom':$('settings-backend').value;renderPresets();showSettingsFields();};
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
  if(name==='practice'&&$('mode').value==='exam_answer'){$('mode').value='check';setMode();}
  const teacher=name==='teacher', teaching=name==='teaching', path=name==='path';
  $('path-view').hidden=!path;
  $('practice-view').hidden=name!=='practice';$('teacher-view').hidden=!teacher;$('teaching-view').hidden=!teaching;
  document.title='高中数学教师 Agent · '+(teacher?'教师备课':teaching?'师生任务':path?'学习路径':'练习工作台');
  $('header-note').textContent='高中数学 · '+(teacher?'教师备课':teaching?'师生任务':path?'学习路径':'过程反馈');
  $('practice-sidebar').hidden=name!=='practice';$('teacher-sidebar').hidden=!teacher;
  for(const [key,id] of [['practice','show-practice'],['teacher','show-teacher'],['teaching','show-teaching']]){
    $(id).classList.toggle('active',key===name||(key==='practice'&&path));$(id).setAttribute('aria-pressed',String(key===name||(key==='practice'&&path)));
  }
  if(teacher)refreshLessonHistory();
}
function openAnswerKey(){
  switchWorkspace('practice');
  $('mode').value='exam_answer';
  setMode();
  $('problem').focus();
  $('input-heading').scrollIntoView({behavior:'smooth',block:'start'});
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
    currentLesson=await jobApi('/api/lessons/outline',payload);showLesson(currentLesson);lessonDone('请逐页核对大纲与待补充信息，再确认进入课件源码。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
$('lesson-source-button').onclick=async()=>{
  if(lessonBusy||!currentLesson)return;
  try{lessonBusyState('已提交大纲确认，正在生成可编辑课件源码…');
    currentLesson=await jobApi('/api/lessons/'+currentLesson.id+'/source',{outline:$('lesson-outline').value,clarifications:$('lesson-clarifications').value});
    showLesson(currentLesson);lessonDone('请检查页序、公式、例题和图示描述；确认后再渲染。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
$('lesson-render-button').onclick=async()=>{
  if(lessonBusy||!currentLesson)return;
  try{lessonBusyState('正在生成配图、渲染 PowerPoint，并运行独立版式检查…');
    const result=await jobApi('/api/lessons/'+currentLesson.id+'/render',{slides_markdown:$('lesson-source').value});
    currentLesson=await api('/api/lessons/'+currentLesson.id);showLesson(currentLesson);lessonDone(result.status==='ready'?'结构检查通过。请下载并在实际放映软件中通看，数学内容仍需教师审阅。':'检查未通过；根据上方告警修订源码后重试。');refreshLessonHistory();
  }catch(error){lessonDone(error.message);}
};
if(!openedFromFile)refreshLessonHistory();

function updateModePresentation(mode) {
  const copy=modeCopy(mode), exam=mode==='exam_answer';
  const view=$('practice-view'), heading=view.querySelector('.page-heading');
  heading.querySelector('.eyebrow').textContent=copy.eyebrow;
  heading.querySelector('h1').innerHTML=copy.h1;
  heading.querySelector('p').textContent=copy.subtitle;
  heading.querySelector('.folio span').textContent=copy.folio;
  $('exam-guide').hidden=!exam;
  view.classList.toggle('exam-workspace',exam);
  $('input-heading').textContent=copy.inputHeading;
  document.querySelector('label[for="problem"]').firstChild.textContent=copy.problemLabel;
  $('problem-hint').textContent=copy.problemHint;
  $('problem').rows=copy.problemRows;
  $('problem').placeholder=copy.problemPlaceholder;
  document.querySelector('label[for="solution"]').firstChild.textContent=copy.solutionLabel;
  $('solution-hint').textContent=copy.solutionHint;
  $('solution').rows=copy.solutionRows||7;
  $('solution').placeholder=copy.solutionPlaceholder;
  $('example').textContent=copy.exampleLabel;
  $('feedback-heading').textContent=copy.feedbackHeading;
  $('revision-note').textContent=copy.revisionNote;
  $('request').placeholder=copy.requestPlaceholder;
  $('practice-extras').open=exam||Boolean($('request').value);
  $('extract-to-problem').textContent=exam?'核对后填入试卷':'填入原题';
  $('extract-to-solution').hidden=exam||mode==='draft'||mode==='partition'||mode==='solve';
  const empty=$('result').querySelector('.empty-state');
  if(empty){empty.querySelector('.math-mark').textContent=copy.empty.mark;empty.querySelector('h3').textContent=copy.empty.h3;empty.querySelector('p').textContent=copy.empty.p;empty.querySelector('small').textContent=copy.empty.small;}
  const stale=renderedMode&&renderedMode!==mode&&$('result').querySelector('.reply');
  let mismatch=$('result').querySelector('.mode-mismatch');
  if(stale&&!mismatch){mismatch=node('p','这是上一次提交的反馈；提交后会按当前模式重新检查。','mode-mismatch');$('result').prepend(mismatch);}
  else if(!stale&&mismatch)mismatch.remove();
  if(!view.hidden){
    document.title='高中数学教师 Agent · '+copy.title;
    $('header-note').textContent='高中数学 · '+copy.headerNote;
  }
}
