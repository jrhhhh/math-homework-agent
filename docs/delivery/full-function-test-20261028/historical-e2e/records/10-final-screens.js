async (page) => {
  const parent='d7f1bd26997c449cbdee8939060113b3';
  await page.getByRole('button',{name:'返回师生任务 ↗',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#task-evidence .task-evidence-item'),null,{timeout:30000});
  const childEvidence=await page.locator('#task-evidence').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/19a-教师查看独立复核.png',fullPage:true});
  await page.getByLabel('已发布任务').selectOption(parent);
  await page.waitForFunction(()=>document.querySelector('#task-evidence')?.textContent.includes('当前过程正确'),null,{timeout:30000});
  await page.getByRole('button',{name:'按学习路径学习 →',exact:true}).click();
  await page.getByText('在已记录帮助后提交',{exact:true}).first().waitFor();
  const revision=await page.locator('#path-feedback').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/14b-重试后修订成功.png',fullPage:true});
  await page.getByRole('button',{name:/^任务中心/}).click();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/30-任务中心最终状态.png',fullPage:true});
  return {stage:'final evidence screenshots',childEvidence,revision};
}
