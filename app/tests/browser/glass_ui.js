async (page) => {
  async function settled(){await page.evaluate(async()=>{await Promise.all(document.getAnimations().filter(a=>a.effect?.getTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));});}
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8767/');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'载入示例 ↗',exact:true}).click();
  if(await page.locator('#practice-extras').getAttribute('open')!==null)throw Error('Optional form should start collapsed');
  await page.getByLabel('我需要',{exact:true}).selectOption('hint');await page.getByText('一次只给一点提示，保留自己继续推理的空间。',{exact:true}).waitFor();
  await page.getByLabel('我需要',{exact:true}).selectOption('check');
  await page.getByText('附件与补充要求',{exact:true}).click();await page.getByLabel('补充要求 可选').fill('沿用我的方法');
  await page.locator('#work-files').setInputFiles({name:'example.txt',mimeType:'text/plain',buffer:Buffer.from('核对附件中的数学文字')});
  await page.getByRole('button',{name:'提取文字',exact:true}).click();
  await page.locator('#work-extract-panel').waitFor({state:'visible'});
  if(await page.locator('#work-extract-text').inputValue()!=='核对附件中的数学文字')throw Error('Attachment text extraction failed');
  await page.getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('button',{name:'移除',exact:true}).click();
  await page.getByLabel('原题 保留完整条件与范围').fill('解 x+1=2。');await page.getByLabel('我的解题过程 建议每一步另起一行').fill('x=1');
  const completed=page.waitForResponse(async r=>r.url().includes('/api/submissions/')&&r.request().method()==='GET'&&(await r.json()).state==='ready');
  await page.getByLabel('我的解题过程 建议每一步另起一行').press('Control+Enter');await completed;
  await page.locator('#state-badge').getByText('反馈已生成',{exact:true}).waitFor();
  await page.getByRole('button',{name:/^任务中心/}).click();await page.getByRole('dialog',{name:'任务中心',exact:true}).waitFor();
  await page.getByRole('button',{name:'查看结果 →',exact:true}).first().waitFor();
  // Native dialog traps keyboard focus and closes with Escape.
  await page.keyboard.press('Tab');const trapped=await page.evaluate(()=>document.getElementById('jobs-dock').contains(document.activeElement));if(!trapped)throw Error('Drawer focus escaped');
  await page.keyboard.press('Escape');await page.getByRole('dialog',{name:'任务中心',exact:true}).waitFor({state:'hidden'});
  if(!await page.getByRole('button',{name:/^任务中心/}).evaluate(el=>el===document.activeElement))throw Error('Drawer focus was not restored');
  await page.getByRole('button',{name:/^任务中心/}).click();await page.getByRole('button',{name:'查看结果 →',exact:true}).first().click();
  await page.getByRole('dialog',{name:'任务中心',exact:true}).waitFor({state:'hidden'});await page.getByText('当前过程正确。',{exact:true}).waitFor();
  if(!await page.locator('#practice-extras').evaluate(el=>el.open))throw Error('Restored preferences are hidden');
  await page.getByRole('button',{name:'教师备课',exact:true}).focus();await page.keyboard.press('ArrowRight');
  if(await page.getByRole('button',{name:'师生任务',exact:true}).getAttribute('aria-pressed')!=='true')throw Error('Keyboard workspace navigation failed');
  const sizes=[];
  for(const width of [1440,1024,768,390,320]){
    await page.setViewportSize({width,height:900});
    for(const label of ['学生练习','教师备课','师生任务']){
      await page.getByRole('button',{name:label,exact:true}).click();
      const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
      if(size.scroll>size.width)throw Error('Overflow '+label+' '+JSON.stringify(size));
      const fits=await page.locator('header').evaluate(el=>{const b=el.getBoundingClientRect();return [...el.children].filter(e=>getComputedStyle(e).display!=='none').every(e=>{const r=e.getBoundingClientRect();return r.left>=b.left&&r.right<=b.right&&r.top>=b.top&&r.bottom<=b.bottom;});});
      if(!fits)throw Error('Header clipped at '+width);sizes.push({view:label,...size});
    }
    await page.getByRole('button',{name:'模型设置',exact:true}).click();await page.getByRole('dialog',{name:'模型设置',exact:true}).waitFor();await page.keyboard.press('Escape');
  }
  await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:'学生练习',exact:true}).click();await settled();await page.screenshot({path:'output/playwright/glass-student-desktop.png',fullPage:false});
  await page.getByRole('button',{name:'教师备课',exact:true}).click();await settled();await page.screenshot({path:'output/playwright/glass-teacher-desktop.png',fullPage:false});
  await page.getByRole('button',{name:/^任务中心/}).click();await settled();await page.screenshot({path:'output/playwright/glass-tasks-desktop.png',fullPage:false});await page.keyboard.press('Escape');
  await page.setViewportSize({width:390,height:1000});await page.getByRole('button',{name:'学生练习',exact:true}).click();await settled();await page.screenshot({path:'output/playwright/glass-mobile.png',fullPage:false});
  await page.emulateMedia({reducedMotion:'reduce'});const motion=await page.locator('#practice-view').evaluate(el=>getComputedStyle(el).animationName);if(motion!=='none')throw Error('Reduced motion not honored');
  if(errors.length)throw Error(errors.join('\n'));
  return {passed:true,backend:'explicit isolated fixture; interaction checks only',checks:'optional fields,attachment extraction,mode explanation,keyboard submission,drawer trap/Escape/focus restore,result handoff,workspace arrows,settings dialog,reduced motion',sizes,errors};
}
