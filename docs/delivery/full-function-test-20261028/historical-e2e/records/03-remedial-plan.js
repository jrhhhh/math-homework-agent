async (page) => {
  await page.getByRole('button',{name:'返回师生任务 ↗',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#task-evidence .task-evidence-item'),null,{timeout:30000});
  const state=await page.locator('#task-evidence').innerText();await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/06-教师查看诊断证据.png',fullPage:true});
  if(await page.locator('#task-plan').isDisabled())return {stage:'remedial plan',state,error:'当前诊断没有进入可规划状态。'};
  await page.getByRole('button',{name:'依据当前诊断起草补救教案',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('task-refresh').disabled && document.getElementById('task-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#task-status').innerText();const plan=await page.locator('#task-plan-draft').inputValue();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/07-模型补救教案.png',fullPage:true});
  return {stage:'real-model remedial plan',state,status,plan};
}
