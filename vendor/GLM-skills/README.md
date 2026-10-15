# vendored: zai-org/GLM-skills（GLM-OCR 部分）

本目录是上游 [zai-org/GLM-skills](https://github.com/zai-org/GLM-skills) 的**未修改副本**，只取与本项目相关的两个技能。

| 项 | 值 |
|---|---|
| 上游仓库 | https://github.com/zai-org/GLM-skills |
| 取用版本 | `main` @ `2ecd31c37e75671a4767342ba3a68a84c8f1b848` |
| 同步日期 | 2026-10-15 |
| 上游许可 | Apache License 2.0，原文见本目录 [LICENSE](LICENSE) |
| 本仓库是否改动 | **否**。上游更新时整目录重新同步，不在本地改 |

## 包含什么

| 目录 | 用途 |
|---|---|
| `glmocr-handwriting/` | 手写体识别（正文、批注、标签） |
| `glmocr-formula/` | 数学公式识别，输出 LaTeX |

两者结构相同：一份 `SKILL.md` + 同一个 `scripts/glm_ocr_cli.py`（两份字节一致）。脚本把本地图片/PDF 编码成 data URI，POST 到固定端点 `https://open.bigmodel.cn/api/paas/v4/layout_parsing`，返回 `text`（Markdown）与 `layout_details`。

## 怎么用

需要 `ZHIPU_API_KEY` 环境变量，从 https://bigmodel.cn/usercenter/proj-mgmt/apikeys 申请：

```bash
export ZHIPU_API_KEY="你的密钥"
"D:/Program Files/anaconda3/python.exe" glmocr-handwriting/scripts/glm_ocr_cli.py \
  --file 草稿.jpg --output out.json --pretty
```

脚本依赖 `requests`（本机 anaconda 已具备）。退出码：0 成功 / 1 识别失败 / 5 写文件失败。

## 与三个技能的关系

**它们不是本项目的第四个技能，是上游输入层。** 详见根目录 [AGENTS.md](../../AGENTS.md) 的「手写草稿的前置转写」一节。要点：

- 只解决「照片 → 文字」，不参与诊断、不产出草稿卡、不进 `handoff → solution-refiner` 链路。
- 上传即外发：学生草稿照片会送到第三方云 API，**先确认这么做合适**。
- 转写质量不受本项目任何脚本保护，读错一个数字就是一条凭空指控学生的「错误」。
