async (page) => {
  if(await page.locator('#jobs-dock').isVisible())await page.getByRole('button',{name:'关闭任务中心',exact:true}).click();
  await page.getByRole('button',{name:'师生任务',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#task-evidence .task-evidence-item'),null,{timeout:30000});
  const evidence=await page.locator('#task-evidence').innerText();const planNote=await page.locator('#task-plan-note').innerText();
  const stale=await page.getByRole('button',{name:'交给教师备课 →',exact:true}).isDisabled();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/15-修订后教案过期.png',fullPage:true});
  await page.getByRole('button',{name:'依据当前诊断起草补救教案',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('task-refresh').disabled && document.getElementById('task-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#task-status').innerText();const plan=await page.locator('#task-plan-draft').inputValue();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/16-更新后的巩固教案.png',fullPage:true});
  return {stage:'stale evidence and renewed plan',evidence,planNote,stale,status,plan};
}
