async (page) => {
  await page.setViewportSize({width:1440,height:1100});
  await page.getByRole('button',{name:/^任务中心/}).click();
  const view=page.locator('[data-job-action="fecb420981dd476dabca47e84db873fa-view"]');await view.waitFor({timeout:30000});
  await view.click();await page.getByRole('dialog',{name:'任务中心'}).waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.getElementById('mode').value==='draft' && document.getElementById('state-badge').textContent==='反馈已生成',null,{timeout:30000});
  const reply=await page.locator('#result').innerText();await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/23-重试后真实草稿反馈.png',fullPage:true});
  return {stage:'draft-coach recovered',reply};
}
