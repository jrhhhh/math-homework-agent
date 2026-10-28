async (page) => {
  await page.getByRole('button',{name:/^任务中心/}).click();
  const card=page.locator('.job-row').filter({hasText:'学生过程诊断'}).filter({hasText:'暂停，可继续'}).first();
  await card.getByRole('button',{name:'继续此任务',exact:true}).waitFor();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/23a-草稿分析超时暂停.png',fullPage:true});
  await card.getByRole('button',{name:'继续此任务',exact:true}).click();
  return {stage:'draft analysis retry',requested:true};
}
