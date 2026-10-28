async (page) => {
  if(!(await page.locator('#lesson-source').inputValue()))return {stage:'lesson render',error:'没有可渲染的课件源码'};
  await page.getByRole('button',{name:'渲染并检查 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('lesson-render-button').disabled && document.getElementById('lesson-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#lesson-status').innerText();const result=await page.locator('#lesson-result').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/11-课件构建与复核.png',fullPage:true});
  return {stage:'lesson builder',status,result,deck:await page.locator('a').filter({hasText:'下载 PowerPoint'}).count()};
}
