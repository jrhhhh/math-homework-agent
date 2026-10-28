async (page) => {
  const editor=page.locator('#task-item-editor .task-edit-item');
  while(await editor.count()>1)await editor.last().getByRole('button',{name:'删除本题',exact:true}).click();
  await page.getByLabel('任务标题',{exact:true}).fill('三角方程：零因子与分类讨论');
  await page.getByLabel('原题',{exact:true}).fill('在 0≤x<2π 内，解方程 sin(2x)=sin x。');
  await page.getByLabel('本题目标',{exact:true}).fill('解三角方程时审查零因子、保留全部分支并在区间内验证解集');
  await page.getByLabel('成功标准',{exact:true}).fill('由因式分解或分类讨论完整保留 sin x=0 与非零分支，列出指定区间所有解并说明等价变形。');
  await page.getByLabel('需要时给学生的提示',{exact:true}).fill('检查每一步使用的除数是否可能为零；不能忽略这种情况。');
  await page.getByLabel('数学操作活动',{exact:true}).selectOption('unit_circle');
  await page.getByRole('button',{name:'检查完毕，发布任务 →',exact:true}).click();
  await page.getByText('任务已发布，学生可以从右侧领取题目。',{exact:true}).waitFor();
  const task=await page.getByLabel('已发布任务').inputValue();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/03-教师发布任务.png',fullPage:true});
  await page.getByRole('button',{name:'按学习路径学习 →',exact:true}).click();
  await page.getByLabel('我的解题过程',{exact:true}).fill('由二倍角公式，2sin x cos x=sin x。\n两边同除以 sin x，得到 cos x=1/2。\n因此在给定范围内，x=π/3 或 5π/3。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/04-学生首次解答.png',fullPage:true});
  await page.getByRole('button',{name:'提交本次尝试 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('path-submit').disabled && document.getElementById('path-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#path-status').innerText();const feedback=await page.locator('#path-feedback').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/05-真实模型诊断.png',fullPage:true});
  const evidence=await page.evaluate(async id=>await (await fetch('/api/teaching/'+id+'/evidence')).json(),task);
  return {stage:'first diagnostic',task,status,feedback,evidence};
}
