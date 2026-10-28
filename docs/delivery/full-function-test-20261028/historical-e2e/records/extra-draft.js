async (page) => {
  await page.goto('http://127.0.0.1:8768/');await page.setViewportSize({width:1440,height:1100});
  await page.getByLabel('我需要',{exact:true}).selectOption('draft');
  await page.getByLabel('草稿布局描述 分区、分行、划改与留白').fill('我把两道题写在同一列，没有单独标题号。左上角写了三角方程，右侧是推导；中间三次划改，旧值和新值写在一起。最下面的检验区很小，有几行写不下挤到了旁边。');
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/22-草稿描述输入.png',fullPage:true});
  await page.getByRole('button',{name:'分析草稿 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('submit').disabled && !['排队中','正在思考','等待提交'].includes(document.getElementById('state-badge').textContent),null,{timeout:600000});
  const state=await page.locator('#state-badge').innerText();const reply=await page.locator('#result').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/23-真实模型草稿反馈.png',fullPage:true});
  return {stage:'draft-coach layout feedback',state,reply};
}
