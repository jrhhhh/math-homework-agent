async (page) => {
  const outline=await page.locator('#lesson-outline').inputValue();if(!outline)return {stage:'lesson source',error:'未取得可确认的大纲'};
  await page.locator('#lesson-clarifications').fill('本次是合成教学演示：对象为高一，45 分钟，先复习二倍角公式，再针对漏解开展教师提示、学生修订、分支检验与新题练习；不假定班级人数或学生已有表现。教材具体页码未提供，不编造页码。迁移题由教师课后另行布置，本次课件不展示迁移题或答案。数学结论以教师已提供的原题、因式分解与四个解为准。');
  await page.getByRole('button',{name:'确认大纲 →',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('lesson-source-button').disabled && document.getElementById('lesson-status').textContent.trim().length>0,null,{timeout:300000});
  const status=await page.locator('#lesson-status').innerText();const source=await page.locator('#lesson-source').inputValue();
  await page.screenshot({path:'delivery/教学流程实测-20261027/screenshots/10-确认大纲与课件源码.png',fullPage:true});
  return {stage:'real-model lesson source',status,source};
}
