async (page) => {
  await page.getByRole('button',{name:'师生任务',exact:true}).click();
  await page.getByRole('button',{name:'按学习路径学习 →',exact:true}).waitFor();
  await page.getByRole('button',{name:'按学习路径学习 →',exact:true}).click();
  await page.getByRole('button',{name:'给我一点提示',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('path-submit').disabled && document.getElementById('path-status').textContent.trim().length>0,null,{timeout:600000});
  const hint=await page.locator('#path-feedback').innerText();const hintStatus=await page.locator('#path-status').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/12-单步提示.png',fullPage:true});
  await page.getByRole('button',{name:'动手观察与解释',exact:true}).click();await page.getByRole('button',{name:'打开数学活动',exact:true}).click();
  await page.locator('#path-widget').waitFor({state:'visible'});await page.getByRole('slider',{name:'angle',exact:true}).fill('180');
  await page.getByText('单位圆坐标：(-1.000, 0.000)',{exact:true}).waitFor();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/13-单位圆数学活动.png',fullPage:true});
  await page.getByRole('button',{name:'先自己试一试',exact:true}).click();
  await page.getByLabel('我的解题过程',{exact:true}).fill('由二倍角公式得 2sin x cos x=sin x，整理为 sin x(2cos x−1)=0。\n因此 sin x=0 或 cos x=1/2。\n在 0≤x<2π 内，前者得 x=0 或 π；后者得 x=π/3 或 5π/3。\n四个值代回原方程均成立，故解集为 {0, π/3, π, 5π/3}。');
  await page.getByRole('button',{name:'提交本次尝试 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('path-submit').disabled && document.getElementById('path-status').textContent.trim().length>0,null,{timeout:600000});
  const revised=await page.locator('#path-feedback').innerText();const history=await page.locator('#path-records').innerText();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/14-学生修订与帮助条件.png',fullPage:true});
  return {stage:'hint, interactive activity and revised diagnostic',hintStatus,hint,revised,history};
}
