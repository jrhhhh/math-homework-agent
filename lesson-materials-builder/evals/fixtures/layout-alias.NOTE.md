# layout-alias.md —— 这个夹具抓到的缺陷（已修）

**夹具意图**：`[分步]` 是废弃别名，应改名 `[流程]` **并提示**。

**修复前的实测**：

| 计划断言 | 修复前 | 修复后 |
|---|---|---|
| 渲染成功 | ✓ | ✓ |
| 落到 `[流程]` | ✓（P2 渲染成单页流程） | ✓ |
| 出现改名告警 | ✗ **一条都没有** | ✓ 报出了 |

## 为什么当初不会报

死代码。构建循环里先把 `page.layout` **就地**改写成 `流程`：

```python
page.layout = LAYOUT_ALIAS.get(page.layout, page.layout)   # 改完了
renderer = RENDERERS.get(page.layout, render_generic)
```

而 `validate(pages, meta)` 是在**这个循环跑完之后**才调用的，它判的却是：

```python
if p.layout in LAYOUT_ALIAS:      # 到手的已经是 [流程]，恒为假
```

到 `validate` 手里时原名已经没了，条件永远不成立。

## 后果

`SKILL.md` 与 `references/slides-spec.md` 都写着「`[分步]` 仍能渲染，但会被改名成
`[流程]` 并**提示**」。实际是**静默改名** —— 按文档的预期去等一条提示，永远等不到。

## 修法

改名前先把来源记下来：

```python
page.layout_origin = page.layout if page.layout in LAYOUT_ALIAS else None
page.layout = LAYOUT_ALIAS.get(page.layout, page.layout)
```

`validate` 判 `getattr(p, "layout_origin", None)`。`getattr` 兜底 `None`，
让没走过构建循环的调用方（测试直接构造 `pages`）也不炸。

**对照**：不含 `[分步]` 的 `mutation-base.md` 仍 0 告警，没有被误伤。

## 附带发现：多行 HTML 注释不是注释

起初把上面这段说明直接写在 `layout-alias.md` 的 `<!-- ... -->` 里，解析器按行处理，
整段被当成要点渲染进了 P2，还触发三条「可能是一整句话被塞进一条要点」告警。
**夹具若要写说明，放在旁挂文件里**（就是本文件），别放进被渲染的 `.md`。

顺带验出字形检查是有效的：注释里的 `✓`(U+2713) / `✗`(U+2717) 被报
「「华文中宋」没有 … 的字形」。
