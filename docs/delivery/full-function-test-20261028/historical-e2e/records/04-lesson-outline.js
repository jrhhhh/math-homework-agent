async (page) => {
  const button=page.getByRole('button',{name:'交给教师备课 →',exact:true});
  if(await button.isDisabled())return {stage:'lesson outline',error:'补救教案不可交接'};
  await button.click();await page.getByText('已带入学习证据和教师草稿；请补齐年级、教材、课时，再生成大纲。',{exact:true}).waitFor();
  await page.getByLabel('年级',{exact:true}).fill('高中一年级');
  await page.getByLabel('教材版本 用来对齐术语与符号').fill('人教 A 版高中数学（由教师指定，具体页码待核）');
  const draft=page.locator('#lesson-draft');await draft.fill((await draft.inputValue())+'\n\n教师已核对的数学材料：原题在 0≤x<2π 内解 sin(2x)=sin x，等价于 sin x(2cos x−1)=0，解集为 {0,π/3,π,5π/3}。禁止除以可能为零的 sin x 而丢失分支。学生动作：检查除数、分支求解、代入验证。课时 45 分钟，教师讲解与学生修订结合，不虚构学情和教材页码。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/08-教案交接备课.png',fullPage:true});
  await page.getByRole('button',{name:'生成课件大纲 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('lesson-outline-button').disabled && document.getElementById('lesson-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#lesson-status').innerText();const outline=await page.locator('#lesson-outline').inputValue();const missing=await page.locator('#lesson-missing').innerText().catch(()=>'');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/09-真实模型课件大纲.png',fullPage:true});
  return {stage:'real-model lesson outline',status,outline,missing};
}
