async (page) => {
  await page.goto('http://127.0.0.1:8768/');await page.setViewportSize({width:1440,height:1100});
  await page.getByRole('button',{name:'师生任务',exact:true}).click();
  await page.getByLabel('任务标题',{exact:true}).fill('三角方程中的零因子与分类讨论');
  await page.getByLabel('教学目标 / 教材材料说明').fill('高一三角方程：以 sin(2x)=sin x 为例，训练学生通过因式分解保留零因子分支，在 0≤x<2π 中完整求解并验证。请设计 1 道适合这个目标的练习，并给出可观察的成功标准。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/01-任务设计输入.png'});
  await page.getByRole('button',{name:'依据目标起草练习',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('task-design').disabled && document.getElementById('task-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#task-status').innerText();await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/02-模型任务草案.png',fullPage:true});
  const rows=await page.locator('.task-edit-item').evaluateAll(cards=>cards.map(card=>({problem:card.querySelector('.task-problem').value,objective:card.querySelector('.task-goal').value,criteria:card.querySelector('.task-criteria').value})));
  return {stage:'real-model task design',status,rows};
}
