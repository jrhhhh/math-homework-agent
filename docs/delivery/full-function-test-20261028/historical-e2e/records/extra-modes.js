async (page) => {
  const results=[];await page.setViewportSize({width:1440,height:1100});
  for(const test of [
    {mode:'answer_check',solution:'0，π/3，π，5π/3',name:'27-仅答案核对'},
    {mode:'full_correction',solution:'由二倍角公式 2sin x cos x=sin x。\n两边同除以 sin x，得 cos x=1/2。\n所以 x=π/3 或 5π/3。',name:'28-完整纠正'}]){
    await page.goto('http://127.0.0.1:8768/');await page.getByLabel('我需要',{exact:true}).selectOption(test.mode);
    await page.getByLabel('原题 保留完整条件与范围').fill('在 0≤x<2π 内，解方程 sin(2x)=sin x。');
    await page.getByLabel('我的解题过程 建议每一步另起一行').fill(test.solution);
    await page.getByRole('button',{name:'开始检查 →',exact:true}).click();
    await page.waitForFunction(()=>!document.getElementById('submit').disabled && !['排队中','正在思考','等待提交'].includes(document.getElementById('state-badge').textContent),null,{timeout:600000});
    const state=await page.locator('#state-badge').innerText(),reply=await page.locator('#result').innerText();
    await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/'+test.name+'.png',fullPage:true});
    results.push({mode:test.mode,state,reply});
  }
  return {stage:'answer-only and full correction modes',results};
}
