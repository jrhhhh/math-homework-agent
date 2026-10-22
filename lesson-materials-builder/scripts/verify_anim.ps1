<#
.SYNOPSIS
  让演示软件自己把课件读回来，核对「单击显现」动画确实挂上了。

.DESCRIPTION
  这个脚本只干一件 Python 干不了的事：让演示软件本体告诉我它读到了什么。

  为什么非要有这一步 —— build_pptx.py 往 pptx 里注入的 <p:timing> 是手写的 XML。
  写错了它有两条反应，**两条都不会让 build 报错**：

    1. 弹「需要修复」，可能顺手把动画删掉；
    2. 安静地忽略那段时序 —— 文件正常打开，动画没了。

  第 2 条最要命：产出看着完全正常，只是解答不再点击显现、直接摊在屏幕上，
  而上课的人要到讲台上才发现。build_pptx.py 的结构校验对这两种都无能为力，
  因为 XML 本身是良构的。只有演示软件自己读一遍才能证伪。

  退出码：0 = 所有应答的演示软件都核对通过；1 = 有任何一条不符。

.PARAMETER Pptx
  要核对的 .pptx。必须是 build_pptx.py 刚产出的那一份。

.PARAMETER Expect
  期望的单击效果总数。取 build_pptx.py 输出里的「单击显现 N 页」那个 N。
  不给就只报数不判定总数（但按页核对照做）。

.PARAMETER OutDir
  可选。给了就把每页的渲染图导出来看看 —— 脚本判不了「好不好看」，
  但那张图是排版错位的直接证据。注意导出的是**点击后**的样子。

.EXAMPLE
  python scripts/build_pptx.py 课件.md -o 课件.pptx
  #   ✓ 课件.pptx
  #     12 个页面块 → 12 张幻灯片
  #     单击显现 4 页（解答块）
  powershell -NoProfile -File scripts/verify_anim.ps1 -Pptx 课件.pptx -Expect 4

.NOTES
  -ExecutionPolicy Bypass 在这台机器上会被策略拒掉，所以调用形式是
  `powershell -NoProfile -File ...`，不带 Bypass。

  ## 「PowerPoint」可能不是 PowerPoint

  装了 WPS 的机器上，`New-Object -ComObject PowerPoint.Application` 拿到的是
  **WPS**：WPS 把 HKLM:\SOFTWARE\Classes 下 PowerPoint.Application / .14 / .16
  三个 ProgID 全改写成 `wpp.exe /Automation`（本机实测 LocalServer32 =
  `D:\WPS edu\WPS Office\...\wpp.exe /Automation`）。而 WPS 还会对外自称
  Name='Microsoft PowerPoint'、Version='14.0'，**按名字判断会被骗过去**。

  自己启动真 PowerPoint 也绕不开：真身的注册被压在 ClickToRun 的虚拟子键
  （`HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\...
  \CLSID\{91493441-5A91-11CF-8700-00AA0060263B}\LocalServer32`）里，外部客户端
  解析不到；只能 `Start-Process POWERPNT.EXE /automation` 再从运行对象表取。
  但 `GetActiveObject('PowerPoint.Application')` 是按**名字**取的，只要有 WPS
  的自动化实例活着，取回来的就是 WPS —— 本机实测：刚 Start-Process 完
  POWERPNT.EXE，紧接着 GetActiveObject 拿到的仍是 `Path=D:\WPS edu\...`。

  所以本脚本不猜、也不假装：
  - 两条路都试，**按 Path 报关**（Path 里有没有 WPS / Microsoft Office）
  - 每个读回来的对象都打一行 `path:`，结论归属哪个软件一眼可见
  - 真 PowerPoint 没拿到时明说「结论只代表 WPS」，而不是让 VERIFY-OK 盖过去

  这不是洁癖：两个 COM 服务器读出来的效果数**不保证一致**，而用户拿哪个放
  课件并不知道。只报一个会漏，报错了名字更糟。
#>
param(
  [Parameter(Mandatory=$true)][string]$Pptx,
  [int]$Expect = -1,
  [string]$OutDir = ''
)

$ErrorActionPreference = 'Stop'
# 不改的话，管道/重定向出去的中文按 OEM 码页编码，读回来是一串乱码 ——
# 判定行（VERIFY-OK / FAIL）是 ASCII 不受影响，但"为什么失败"的解释会瞎掉，
# 而那几句正是这个脚本存在的理由。
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

if (-not (Test-Path $Pptx)) { Write-Output ("FILE-NOT-FOUND: {0}" -f $Pptx); exit 1 }
$Pptx = (Resolve-Path $Pptx).Path

# 效果类型 1 = msoAnimEffectAppear（进入/显现）。这是最老的效果，正是本技能
# 唯一使用的那一种 —— 读回别的值说明挂错了效果。
$EFFECT_APPEAR = 1
# 触发方式 1 = msoAnimTriggerOnPageClick（单击时）。2 是"与上一动画同时"，
# 那会变成自动播放，讨论还没开始答案就出来了。
$TRIGGER_ON_CLICK = 1
# Exit = False（0）= 进入效果。这正是"点击前不显示"的语义本身：进入效果在
# 被触发之前，形状就是不画的。挂成退出效果的话，点一下消失的才是解答。
$NOT_AN_EXIT = 0

# --------------------------------------------------------------------------
# 找到演示软件本体（而不是"名字叫 PowerPoint 的那个东西"）
# --------------------------------------------------------------------------

function Get-PptExe {
  # 真 PowerPoint 的 LocalServer32。这条键在 ClickToRun 的虚拟 hive 下，
  # 是外部客户端唯一能拿到 POWERPNT.EXE 路径的地方。
  $key = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\Classes\CLSID\{91493441-5A91-11CF-8700-00AA0060263B}\LocalServer32'
  if (Test-Path $key) {
    $cmd = (Get-ItemProperty $key -ErrorAction SilentlyContinue).'(default)'
    if ($cmd) {
      $exe = ($cmd -replace '(?i)\s*/AUTOMATION\s*$', '').Trim('"').Trim()
      if (Test-Path $exe) { return $exe }
    }
  }
  foreach ($p in @("$env:ProgramFiles\Microsoft Office\root\Office16\POWERPNT.EXE",
                   "${env:ProgramFiles(x86)}\Microsoft Office\root\Office16\POWERPNT.EXE",
                   "$env:ProgramFiles\Microsoft Office\Office16\POWERPNT.EXE",
                   "${env:ProgramFiles(x86)}\Microsoft Office\Office16\POWERPNT.EXE")) {
    if (Test-Path $p) { return $p }
  }
  return $null
}

function Get-RealPowerPoint {
  $exe = Get-PptExe
  if (-not $exe) { return $null }
  try {
    Start-Process -FilePath $exe -ArgumentList '/automation' -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 6
    # 名字对不上的可能性是真实存在的 —— 取回来到底是谁，交给 Test-App 按 Path 判。
    return [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application')
  } catch {
    return $null
  }
}

function Get-AppPath($app) {
  try { return [string]$app.Path } catch { return '' }
}

function Get-AppKind($app) {
  $p = Get-AppPath $app
  if ($p -match '(?i)WPS') { return 'WPS Presentation' }
  if ($p -match '(?i)Microsoft Office') { return 'Microsoft PowerPoint' }
  return 'unknown'
}

function Test-AppUsable($app) {
  # 残留的自动化连接会拿到一个"看着是对象、其实调不动"的东西：属性全空、
  # Presentations 是 null，一路哑到 Presentations.Open 才炸，报错还是
  # "不能对 Null 值表达式调用方法"这种指不到病灶的话。所以拿到手先探一下。
  if ($null -eq $app) { return $false }
  try { if ($null -eq $app.Presentations) { return $false } } catch { return $false }
  try { [void]$app.Version } catch { }
  return $true
}

$apps = @()
$seen = @{}

function Add-App($app, $how) {
  if ($null -eq $app) { Write-Output ("   {0}：没拿到" -f $how); return }
  if (-not (Test-AppUsable $app)) {
    Write-Output ("   {0}：拿回来的是个不可用的自动化连接 —— 多半是同名的残留进程" -f $how)
    try { $app.Quit() } catch { }
    return
  }
  $k = Get-AppKind $app
  $p = Get-AppPath $app
  if ($seen.ContainsKey($p)) {
    Write-Output ("   {0}：{1}（已在列，不重复读）" -f $how, $k)
    try { $app.Quit() } catch { }
    return
  }
  Write-Output ("   {0}：{1}" -f $how, $k)
  $script:seen[$p] = $true
  $script:apps += $app
}

# 两条路都走。真身在前，但**不假设它真的拿到了真身** —— 有 WPS 的自动化实例
# 活着时这条也返回 WPS（见文件头）。ProgID 那条在 WPS 机器上必然返回 WPS。
Add-App (Get-RealPowerPoint) '真身路线'
try { Add-App (New-Object -ComObject PowerPoint.Application) 'ProgID 路线' } catch { }

if ($apps.Count -eq 0) {
  Write-Output 'NO-DEMO-APP: 找不到任何可驱动的演示软件（PowerPoint / WPS 都没有）'
  exit 1
}

# 身份要在 Quit 之前记下来 —— 退出之后再问 Path 就问不出来了（返回空，
# 于是所有软件都成了 unknown，最后那行结论正好把自己要说的事说错）。
$kinds = @($apps | ForEach-Object { Get-AppKind $_ })

if (-not ($kinds -contains 'Microsoft PowerPoint')) {
  Write-Output '注：没读到真 PowerPoint，只读到 WPS —— WPS 把 PowerPoint.Application'
  Write-Output '    这个名字占在运行对象表里，自己启动 POWERPNT.EXE 也照样取回 WPS。'
  Write-Output '    下面的结论只代表 WPS；要用 PowerPoint 放映，先关掉 WPS 窗口再跑一遍。'
  Write-Output ''
}

# --------------------------------------------------------------------------
# 逐个读回
# --------------------------------------------------------------------------

$failed = $false
$first = $true
$ai = 0

foreach ($app in $apps) {
  $name = '?'; $ver = '?'
  try { $name = [string]$app.Name } catch { }
  try { $ver = [string]$app.Version } catch { }

  # 报关要报 Path 和 Kind，不能报 Name —— WPS 自称 'Microsoft PowerPoint' '14.0'。
  Write-Output ("== {0}  （自称 {1} {2}）" -f $kinds[$ai], $name, $ver)
  Write-Output ("   path: {0}" -f (Get-AppPath $app))

  $bad = @()
  $total = 0
  $pres = $null
  try {
    # ReadOnly=$true, Untitled=$false, WithWindow=$false —— 只读不改。
    $pres = $app.Presentations.Open($Pptx, $true, $false, $false)

    foreach ($s in $pres.Slides) {
      $seq = $s.TimeLine.MainSequence
      $n = $seq.Count
      if ($n -eq 0) { continue }
      $total += $n

      if ($n -gt 1) {
        $bad += ("P{0}: {1} effects on one slide (expected at most 1)" -f $s.SlideIndex, $n)
      }
      for ($i = 1; $i -le $n; $i++) {
        $e = $seq.Item($i)
        $sname = ''
        try { $sname = [string]$e.Shape.Name } catch { }
        $trig = -1
        try { $trig = [int]$e.Timing.TriggerType } catch { }
        $isExit = -1
        try { $isExit = [int]$e.Exit } catch { }

        # 目标必须正好是解答块。挂错了形状（比如挂到题干上）在演示软件里看着
        # 也是"有动画"，但点一下消失的是题干 —— 这条断言就是拦这个的。
        if ($sname -notlike 'answer-block*') {
          $bad += ("P{0}: effect targets '{1}', not the answer block" -f $s.SlideIndex, $sname)
        }
        if ($e.EffectType -ne $EFFECT_APPEAR) {
          $bad += ("P{0}: EffectType={1}, expected {2} (Appear)" -f `
            $s.SlideIndex, $e.EffectType, $EFFECT_APPEAR)
        }
        if ($trig -ne $TRIGGER_ON_CLICK) {
          $bad += ("P{0}: TriggerType={1}, expected {2} (on click)" -f `
            $s.SlideIndex, $trig, $TRIGGER_ON_CLICK)
        }
        if ($isExit -ne $NOT_AN_EXIT) {
          $bad += ("P{0}: Exit={1} -- this is an EXIT effect, the block would vanish on click" -f `
            $s.SlideIndex, $isExit)
        }
        Write-Output ("  ok  P{0}: Appear on '{1}' (click, entrance)" -f $s.SlideIndex, $sname)
      }
    }

    if ($Expect -ge 0 -and $total -ne $Expect) {
      $bad += ("effect total = {0}, but build reported {1}" -f $total, $Expect)
    }

    if ($OutDir -ne '' -and $first) {
      if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
      # 导出的图是**点击后**的样子 —— 实测（作者样本里被动画藏起来的那张表格，
      # 导出图里是显示的，PowerPoint 与 WPS 都如此）。所以它只能用来查排版，
      # 不能用来查"藏没藏住"。「藏没藏住」要真放映一遍再看。
      foreach ($s in $pres.Slides) {
        $f = Join-Path $OutDir ("slide{0:D2}.png" -f $s.SlideIndex)
        $s.Export($f, "PNG", 1600, 900)
      }
      Write-Output ("   rendered {0} slides -> {1}" -f $pres.Slides.Count, $OutDir)
    }

    try { $pres.Close() } catch { }
  } catch {
    $bad += ("COM-FAIL: {0}" -f $_.Exception.Message)
    Write-Output '   打不开或读不动 —— 这本身就算不合格。'
  }

  Write-Output ("   click reveal effects: {0}" -f $total)
  if ($bad.Count -gt 0) {
    $failed = $true
    Write-Output ("   FAIL ({0})" -f $bad.Count)
    foreach ($b in $bad) { Write-Output ("     ! {0}" -f $b) }
  } else {
    Write-Output '   OK'
  }
  $first = $false
  $ai++
}

foreach ($app in $apps) { try { $app.Quit() } catch { } }

if ($failed) { Write-Output ''; Write-Output 'VERIFY-FAIL'; exit 1 }
Write-Output ''
Write-Output ("VERIFY-OK（{0} 个演示软件各读回一遍：{1}）" -f `
  $apps.Count, ($kinds -join ' + '))
exit 0
