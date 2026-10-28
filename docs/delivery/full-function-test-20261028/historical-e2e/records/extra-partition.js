async (page) => {
  await page.goto('http://127.0.0.1:8768/');await page.setViewportSize({width:1440,height:1100});
  await page.getByLabel('我需要',{exact:true}).selectOption('partition');
  await page.getByLabel('草稿布局描述 分区、分行、划改与留白').fill('纸面左上有“1”并围绕三角函数写了几行，左下另有“2”和一块独立演算；右侧有一整块带坐标轴的图，图旁另有少量计算。左下和右侧是否属于同一题尚不确定。');
  await page.getByRole('button',{name:'分析草稿 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('submit').disabled && !['排队中','正在思考','等待提交'].includes(document.getElementById('state-badge').textContent),null,{timeout:600000});
  const state=await page.locator('#state-badge').innerText(),reply=await page.locator('#result').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/29-草稿版面分块.png',fullPage:true});
  return {stage:'draft partition mode',state,reply};
}
