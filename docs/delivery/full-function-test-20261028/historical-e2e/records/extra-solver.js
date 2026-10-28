async (page) => {
  await page.goto('http://127.0.0.1:8768/');await page.setViewportSize({width:1440,height:1100});
  await page.getByLabel('我需要',{exact:true}).selectOption('solve');
  await page.getByLabel('原题 保留完整条件与范围').fill('在 0≤x<2π 内，解方程 sin(2x)=sin x。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/20-教师求解输入.png',fullPage:true});
  await page.getByRole('button',{name:'开始求解 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('submit').disabled && !['排队中','正在思考','等待提交'].includes(document.getElementById('state-badge').textContent),null,{timeout:600000});
  const state=await page.locator('#state-badge').innerText();const reply=await page.locator('#result').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/21-真实模型完整求解.png',fullPage:true});
  return {stage:'math solver',state,reply};
}
