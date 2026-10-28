async (page) => {
  const card=page.locator('.job-row').filter({hasText:'课件大纲'}).first();
  await card.getByRole('button',{name:'查看结果 →',exact:true}).waitFor({timeout:30000});
  await card.getByRole('button',{name:'查看结果 →',exact:true}).click();
  await page.locator('#lesson-outline-stage').waitFor({state:'visible'});
  const outline=await page.locator('#lesson-outline').inputValue();const missing=await page.locator('#lesson-missing').innerText().catch(()=>'');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/09-重试后真实模型课件大纲.png',fullPage:true});
  return {stage:'lesson outline recovered',outline,missing};
}
