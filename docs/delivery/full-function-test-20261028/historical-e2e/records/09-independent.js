async (page) => {
  const parent=await page.getByLabel('已发布任务').inputValue();
  await page.getByRole('button',{name:'布置关联的再练习 →',exact:true}).click();
  await page.getByText('将关联前序任务 '+parent.slice(0,8)+' 及当前证据版本。',{exact:true}).waitFor();
  await page.getByLabel('任务用途',{exact:true}).selectOption('independent_check');
  await page.getByLabel('原题',{exact:true}).fill('在 0≤x<2π 内，解方程 sin(2x)=-sin x。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/17-教师布置关联新题.png',fullPage:true});
  await page.getByRole('button',{name:'检查完毕，发布任务 →',exact:true}).click();
  await page.getByText('关联前序任务：'+parent.slice(0,8),{exact:true}).waitFor();
  const task=await page.getByLabel('已发布任务').inputValue();
  await page.getByRole('button',{name:'按学习路径学习 →',exact:true}).click();
  await page.getByLabel('我的解题过程',{exact:true}).fill('由二倍角公式得 2sin x cos x=−sin x，整理为 sin x(2cos x+1)=0。\n所以 sin x=0 或 cos x=−1/2。\n在 0≤x<2π 内，前者给出 x=0, π；后者给出 x=2π/3, 4π/3。\n逐一代入均满足原方程，2π 不属于题目范围，故解集为 {0, 2π/3, π, 4π/3}。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/18-学生独立新题.png',fullPage:true});
  await page.getByRole('button',{name:'提交本次尝试 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('path-submit').disabled && document.getElementById('path-status').textContent.trim().length>0,null,{timeout:600000});
  const status=await page.locator('#path-status').innerText();const feedback=await page.locator('#path-feedback').innerText();
  const evidence=await page.evaluate(async id=>await (await fetch('/api/teaching/'+id+'/evidence')).json(),task);
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/19-独立新题复核结果.png',fullPage:true});
  return {stage:'independent new-problem diagnostic',parent,task,status,feedback,evidence};
}
