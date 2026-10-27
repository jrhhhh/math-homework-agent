/* Progressive interaction helpers; no changes to teaching or model contracts. */
(() => {
  const modeHelp={check:'检查你写出的过程，定位需要调整的关键一步。',hint:'一次只给一点提示，保留自己继续推理的空间。',full_correction:'解释问题并给出完整纠正；这会记录为获得讲解。',answer_check:'只核对答案，不推断你没有提供的过程。',refine:'先核验当前过程，再讨论更简洁的方法。',solve:'从题目出发给出完整解答，保存为助手求解稿。',draft:'根据文字描述反馈草稿布局，不判断数学对错。',partition:'依据你提供的布局描述分块，题目归属由你确认。'};
  const help=document.createElement('p');help.id='mode-explanation';help.className='mode-explanation';
  $('submission-form').querySelector('.field-row').after(help);$('mode').setAttribute('aria-describedby',help.id);
  const updateMode=()=>{help.textContent=modeHelp[$('mode').value]||'';};$('mode').addEventListener('change',updateMode);updateMode();
  // Programmatic session loads also update mode without dispatching a change event.
  const originalSetMode=setMode;setMode=function(...args){const result=originalSetMode(...args);updateMode();return result;};
  const views=[['practice','show-practice'],['teacher','show-teacher'],['teaching','show-teaching']];
  for(const [,id] of views)$(id).setAttribute('aria-pressed',$(id).classList.contains('active'));
  document.querySelector('.workspace-switcher').addEventListener('keydown',event=>{
    const index=views.findIndex(([,id])=>id===event.target.id);if(index<0)return;
    const next=event.key==='Home'?0:event.key==='End'?2:['ArrowRight','ArrowDown'].includes(event.key)?(index+1)%3:['ArrowLeft','ArrowUp'].includes(event.key)?(index+2)%3:null;
    if(next===null)return;event.preventDefault();$(views[next][1]).focus();$(views[next][1]).click();$(views[next][1]).focus();
  });
  const originalSwitch=switchWorkspace;switchWorkspace=function(name){
    const fromNav=views.some(([,id])=>id===document.activeElement?.id);
    originalSwitch(name);for(const [key,id] of views)$(id).setAttribute('aria-pressed',String(key===name||(key==='practice'&&name==='path')));
    if(fromNav){const heading=$(name==='path'?'path-view':name==='teaching'?'teaching-view':name==='teacher'?'teacher-view':'practice-view').querySelector('h1');heading.tabIndex=-1;heading.focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
  };
  for(const id of ['submit','lesson-outline-button','task-publish','path-submit']){$(id).title='Ctrl / ⌘ + Enter 提交';$(id).setAttribute('aria-keyshortcuts','Control+Enter Meta+Enter');}
  document.addEventListener('keydown',event=>{
    if(!(event.ctrlKey||event.metaKey)||event.key!=='Enter'||event.isComposing||document.querySelector('dialog[open]'))return;
    const form=document.activeElement?.closest('form');if(!form||form.closest('[hidden]'))return;
    const submit=form.querySelector('button[type="submit"],button:not([type])');if(submit&&!submit.disabled){event.preventDefault();form.requestSubmit(submit);}
  });
  const extras=$('practice-extras');
  $('work-files').addEventListener('change',()=>{if($('work-files').files.length)extras.open=true;});
  // If a restored record contains preferences, keep them discoverable.
  const originalPopulate=populate;populate=function(data){originalPopulate(data);extras.open=Boolean(data.request);};
  for(const id of ['form-status','lesson-status','task-status','path-status']){
    const el=$(id);new MutationObserver(()=>{el.classList.toggle('has-message',Boolean(el.textContent.trim()));}).observe(el,{childList:true,subtree:true,characterData:true});
  }
  // Dragging a local file onto the optional upload area follows the existing file limits.
  const drop=$('work-file-field');let dragDepth=0;
  drop.addEventListener('dragenter',event=>{if(!event.dataTransfer.types.includes('Files'))return;event.preventDefault();dragDepth++;drop.classList.add('drag-over');});
  drop.addEventListener('dragover',event=>{if(event.dataTransfer.types.includes('Files'))event.preventDefault();});
  drop.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;drop.classList.remove('drag-over');}});
  drop.addEventListener('drop',event=>{event.preventDefault();dragDepth=0;drop.classList.remove('drag-over');if(!openedFromFile){addWorkFiles(event.dataTransfer.files);$('ui-announcement').textContent='附件已添加，请核对后提交。';}});
})();
