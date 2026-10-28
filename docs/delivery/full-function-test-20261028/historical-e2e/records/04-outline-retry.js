async (page) => {
  await page.getByRole('button',{name:/^任务中心/}).click();
  const card=page.locator('.job-row').filter({hasText:'课件大纲'}).first();await card.getByText('暂停，可继续',{exact:true}).waitFor();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/09a-课件大纲超时暂停.png',fullPage:true});
  await card.getByRole('button',{name:'继续此任务',exact:true}).click();
  const jobs=await page.evaluate(async()=>await(await fetch('/api/jobs')).json());
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/09b-任务中心手动重试.png',fullPage:true});
  return {stage:'lesson outline manual retry',job:jobs.find(item=>item.kind==='lesson-outline')};
}
