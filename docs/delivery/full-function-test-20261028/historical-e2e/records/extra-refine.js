async (page) => {
  await page.goto('http://127.0.0.1:8768/');await page.setViewportSize({width:1440,height:1100});
  await page.getByLabel('我需要',{exact:true}).selectOption('refine');
  await page.getByLabel('原题 保留完整条件与范围').fill('在 0≤x<2π 内，解方程 sin(2x)=sin x。');
  await page.getByLabel('我的解题过程 建议每一步另起一行').fill('由二倍角公式得 2sin x cos x=sin x，整理为 sin x(2cos x−1)=0。\n所以 sin x=0 或 cos x=1/2。\n在 0≤x<2π 内，前者得到 x=0 或 π，后者得到 x=π/3 或 5π/3。\n逐一代入均满足原方程，故解集为 {0, π/3, π, 5π/3}。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/24-正确解法优化输入.png',fullPage:true});
  await page.getByRole('button',{name:'先核验再优化 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('submit').disabled && !['排队中','正在思考','等待提交'].includes(document.getElementById('state-badge').textContent),null,{timeout:600000});
  const state=await page.locator('#state-badge').innerText();const reply=await page.locator('#result').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/25-真实模型正解优化.png',fullPage:true});
  return {stage:'diagnose then refine',state,reply};
}
