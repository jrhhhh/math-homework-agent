"""Native visual themes: persistent PowerPoint Layout surfaces plus editable content.

This is independently implemented, without importing PPT Master's source or assets.
The classic Markdown grammar and teacher-note contract remain unchanged.
"""
import json
from copy import deepcopy
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

THEMES = {"scholar-red", "ink-teal"}
ROLES = {"封面": "Cover", "标题": "Explore", "两栏": "Compare", "重点": "Takeaway",
         "例题": "Practice", "纯图": "Visual", "流程": "Sequence", "阐述": "Notes"}
ROLE_LABEL = {"标题": "探究与推理", "两栏": "对照与辨析", "重点": "核心结论",
              "例题": "问题与练习", "纯图": "观察与解释", "流程": "过程与联系", "阐述": "教学设计"}


def load(name):
    if name not in THEMES:
        raise ValueError(f"不支持的视觉主题：{name}")
    return json.loads((Path(__file__).resolve().parents[1] / "assets/themes" / f"{name}.json").read_text(encoding="utf-8"))


def shape(slide, x, y, w, h, fill, *, line=None, kind=MSO_SHAPE.RECTANGLE, name="theme.surface"):
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.name = name
    sh.shadow.inherit = False
    for effect in sh._element.xpath("./p:style/a:effectRef"):
        effect.set("idx", "0")
    if fill:
        sh.fill.solid(); sh.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = RGBColor.from_string(line); sh.line.width = Pt(1.2)
    else:
        sh.line.fill.background()
    return sh


def line(slide, x1, y1, x2, y2, color, width=1.2):
    sh = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    sh.name = "theme.rule"
    for effect in sh._element.xpath("./p:style/a:effectRef"):
        effect.set("idx", "0")
    sh.line.color.rgb = RGBColor.from_string(color); sh.line.width = Pt(width)
    return sh


def _surfaces(slide, role, c):
    """Layout-level geometry, not screenshots or repeated slide-local pictures."""
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string(c["deep"] if role in {"Cover", "Takeaway"} else c["paper"])
    if role == "Cover":
        shape(slide, 8.6, 0, 4.733333, 7.5, c["accent"])
        # An editable circular construction motif for a mathematics classroom.
        shape(slide, 9.04, 2.05, 3.6, 3.6, None, line=c["soft"], kind=MSO_SHAPE.OVAL)
        line(slide, 8.85, 3.85, 12.85, 3.85, c["soft"])
        line(slide, 10.84, 1.85, 10.84, 5.85, c["soft"])
        line(slide, 10.84, 3.85, 12.27, 2.76, c["white"], 2)
        shape(slide, 12.21, 2.70, .12, .12, c["white"], kind=MSO_SHAPE.OVAL)
        shape(slide, .85, 1.5, 1.1, .065, c["white"])
    elif role == "Takeaway":
        shape(slide, .82, 1.5, .06, 4.95, c["soft"])
        line(slide, 1.18, 6.08, 12.35, 6.08, c["accent"])
    else:
        shape(slide, 0, 0, .18, 7.5, c["accent"])
        line(slide, .86, 1.37, 12.48, 1.37, c["rule"])
        if role == "Compare":
            shape(slide, .88, 1.7, 5.646666, 4.25, c["white"])
            shape(slide, 6.806666, 1.7, 5.646666, 4.25, c["white"])
            shape(slide, .88, 1.7, 5.646666, .06, c["accent"])
            shape(slide, 6.806666, 1.7, 5.646666, .06, c["secondary"])
        elif role == "Practice":
            shape(slide, .88, 1.72, 11.5, 2.3, c["soft"])
            shape(slide, .88, 4.24, 11.5, 2.41, c["white"])
            line(slide, 1.18, 4.83, 12.08, 4.83, c["rule"], .5)
            line(slide, 1.18, 5.42, 12.08, 5.42, c["rule"], .5)
        elif role in {"Visual", "Sequence"}:
            shape(slide, .88, 1.72, 11.5, 4.22, c["white"])


def install(prs, spec):
    """Create real p:sldLayout parts under the existing master; keep classic layouts."""
    # Fresh default/bundled files have >= 8 layouts. Reserve the last eight, so
    # the existing first layout stays usable by external code.
    from lxml import etree
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    for master in prs.slide_masters:
        for relationship in master.part.rels.values():
            if not relationship.reltype.endswith("/theme"):
                continue
            part = relationship.target_part
            root = etree.fromstring(part.blob)
            root.set("name", spec["name"])
            colors = spec["colors"]
            mapping = {"dk1":"ink", "lt1":"white", "dk2":"deep", "lt2":"paper",
                       "accent1":"accent", "accent2":"secondary", "accent3":"muted",
                       "accent4":"soft", "accent5":"rule", "accent6":"deep",
                       "hlink":"accent", "folHlink":"secondary"}
            for key, token in mapping.items():
                element = root.find("a:themeElements/a:clrScheme/a:"+key, ns)
                if element is not None:
                    for child in list(element): element.remove(child)
                    child = etree.SubElement(element, "{"+ns["a"]+"}srgbClr")
                    child.set("val", colors[token])
            for kind, face in (("majorFont", spec["title_font"]), ("minorFont", spec["body_font"])):
                group = root.find("a:themeElements/a:fontScheme/a:"+kind, ns)
                if group is not None:
                    for family in ("latin", "ea"):
                        element = group.find("a:"+family, ns)
                        if element is not None: element.set("typeface", face)
                    for element in group.findall("a:font", ns):
                        if element.get("script") == "Hans": element.set("typeface", face)
            part._blob = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    available = list(prs.slide_layouts)[-8:]
    if len(available) < 8:
        raise ValueError("视觉主题需要至少8个可配置的 PowerPoint 版式。")
    result = {}
    for (label, role), layout in zip(ROLES.items(), available):
        layout.name = spec["layout_prefix"] + "." + role
        tree = layout._element.spTree
        for el in list(tree):
            if el.tag.split('}')[-1] not in {"nvGrpSpPr", "grpSpPr"}:
                tree.remove(el)
        # Draw with python-pptx, then transfer native DrawingML to the Layout.
        scratch = prs.slides.add_slide(layout)
        _surfaces(scratch, role, spec["colors"])
        bg = scratch._element.cSld.find('{http://schemas.openxmlformats.org/presentationml/2006/main}bg')
        old = layout._element.cSld.find('{http://schemas.openxmlformats.org/presentationml/2006/main}bg')
        if old is not None: layout._element.cSld.remove(old)
        layout._element.cSld.insert(0, deepcopy(bg))
        for sh in scratch.shapes:
            tree.append(deepcopy(sh._element))
        sid = prs.slides._sldIdLst[-1]
        prs.part.drop_rel(sid.rId); prs.slides._sldIdLst.remove(sid)
        result[label] = layout
    prs.core_properties.keywords = "math-lesson-theme:" + spec["id"]
    return result


def text(slide, api, x, y, w, h, values, size, color, spec, *, bold=False, title=False, center=False):
    tf = api.textbox(slide, x, y, w, h)
    for i, value in enumerate(values):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = Pt(size * 1.35); p.space_after = Pt(9)
        if center: p.alignment = PP_ALIGN.CENTER
        api.add_rich(p, value, size, color, bold_all=bold,
                     face=spec["title_font"] if title else spec["body_font"])
    return tf


def _height(api, values, w, size):
    return api.text_height([(0, v) for v in values], w, size, size, 9, 1.35)



def picture(api, slide, path, x, y, max_w, max_h, h=None, w=None, center_v=True):
    """Crop only empty outer margins, preserving every mathematical label."""
    if not (h or w):
        try:
            from PIL import Image
            with Image.open(path) as im:
                animated = getattr(im, "is_animated", False)
                width, height = im.size
            ink = api.ink_box(path) if not animated else None
            if ink:
                iw, ih, cx, cy = ink
                pad = .04 * max(iw, ih)
                left, top = max(0, cx-iw/2-pad), max(0, cy-ih/2-pad)
                right, bottom = min(1, cx+iw/2+pad), min(1, cy+ih/2+pad)
                ratio = (right-left)*width/((bottom-top)*height)
                dw = min(max_w, max_h*ratio); dh = dw/ratio
                return api.add_image(slide,path,x,y,max_w,max_h,dh,dw,center_v=center_v,
                                     crop=(left,top,1-right,1-bottom))
        except (OSError, ValueError):
            pass
    return api.add_image(slide,path,x,y,max_w,max_h,h,w,center_v=center_v)


def _question(slide, page, api, spec):
    if not page.question: return
    c = spec["colors"]
    dark = page.layout == "重点"
    height = max(.72, _height(api, [page.question], 9.9, 24) + .2)
    top = 6.96 - height
    shape(slide, .88, top, 11.5, height, c["soft"] if not dark else c["accent"])
    text(slide, api, 1.08, top+.18, 1.1, .36, ["思考"], 18, c["accent"] if not dark else c["white"], spec, bold=True)
    text(slide, api, 2.18, top+.1, 9.9, height-.16, [page.question], 24, c["ink"] if not dark else c["white"], spec)


def render(slide, page, meta, api, spec):
    c = spec["colors"]; warns = []
    role = page.layout
    vals = [v for _, v in page.bullets]
    end = 6.96 - max(.72, _height(api, [page.question], 9.9, 24)+.2) - .22 if page.question else 6.65
    if role == "封面":
        text(slide, api, .9, .65, 7, .5, [meta.get("course_label", "高中数学 · 课堂研习")], 20, c["soft"], spec)
        n = len(page.title)
        size = 50 if n <= 14 else 42
        text(slide, api, .88, 2.05, 7.25, 2.1, [page.title], size, c["white"], spec, title=True)
        sub = ([meta["subtitle"]] if meta.get("subtitle") and meta["subtitle"] not in vals else []) + vals
        text(slide, api, .92, 5.0, 6.95, 1.45, sub, 22, c["soft"], spec)
        return None
    dark = role == "重点"
    text(slide, api, .9, .3, 11.4, .34, [ROLE_LABEL.get(role, "课堂研习")], 16,
         c["soft"] if dark else c["accent"], spec, bold=True)
    text(slide, api, .88, .72, 11.6, .64, [page.title], 34,
         c["white"] if dark else c["ink"], spec, title=True)
    answer_y = emph_y = None
    answer_h = 0
    if page.answers:
        answer_h = _height(api, page.answers, 10.6, 24)
        answer_y = end - answer_h
        end = answer_y - .18
    if page.emph:
        emph_y = end - .65
        end = emph_y - .22
    y, h = 1.9, end - 1.9
    if h < .65:
        warns.append("答案或强调内容过长，挤占主要教学区，请拆页")
    if role == "两栏":
        end = min(end, 5.85)
        h = end - y
        if vals:
            ch = _height(api, vals, 10.9, 24)
            text(slide, api, 1.13, y, 10.9, ch, vals, 24, c["ink"], spec)
            y += ch + .22; h = end - y
        cols = [(page.left, page.left_img, 1.18), (page.right, page.right_img, 7.106666)]
        heights = [_height(api, [t for _, t in items], 5.046666, 26) for items, _, _ in cols]
        for (items, img, x), need in zip(cols, heights):
            v = [t for _, t in items]
            if need > h: warns.append(f"两栏内容估算超高 {need:.2f}in > {h:.2f}in，请拆页")
            text(slide, api, x, y+.08, 5.046666, min(h, need+.05), v, 26, c["ink"], spec)
            if img:
                iy = y + max(heights) + .18; ih = end - iy
                if ih < 1.5: warns.append("两栏配图过小，请将图文拆页")
                _, warning = picture(api, slide, img[0], x, iy, 5.046666, max(.4, ih), img[1], img[2], center_v=True)
                if warning: warns.append(warning)
    elif role == "例题":
        need = _height(api, vals, 10.9, 27)
        if need > 1.95: warns.append("例题题干超出主题任务区，请拆分或缩短非必要文字")
        text(slide, api, 1.17, 1.92, 10.9, max(1.9, need), vals, 27, c["ink"], spec)
        if page.images:
            img=page.images[0]
            _, warning=picture(api, slide,img[0],8.0,4.3,4.05,1.5,img[1],img[2],center_v=True)
            if warning: warns.append(warning)
    elif role == "重点":
        need = _height(api, vals, 10.6, 30)
        text(slide, api, 1.2, 2.0+max(0,(h-need)/2), 10.6, max(need,.5), vals, 30, c["white"], spec)
    elif role == "流程" and page.steps:
        old_title = api.add_title
        api.add_title = lambda *args, **kwargs: None
        try:
            return api.render_flow(slide, page, meta)
        finally:
            api.add_title = old_title
    elif role == "流程" and vals:
        if len(vals) > 4:
            warns.append("文字流程超过4步，请拆页")
        count = len(vals)
        width = (10.9 - .35 * (count-1)) / count
        for i, value in enumerate(vals):
            x = 1.18 + i * (width + .35)
            text(slide,api,x,2.48,width,.42,[str(i+1).zfill(2)],20,c["accent"],spec,bold=True)
            shape(slide,x,3.12,width,1.38,c["soft"],line=c["rule"])
            text(slide,api,x+.14,3.35,width-.28,1.0,[value],24,c["ink"],spec)
            if i < count-1:
                shape(slide,x+width+.08,3.67,.18,.25,c["accent"],kind=MSO_SHAPE.CHEVRON)
    elif page.images:
        img=page.images[0]
        if role == "纯图":
            _, warning=picture(api, slide,img[0],1.1,1.9,11.133333,end-1.9,img[1],img[2],center_v=True)
        else:
            need=_height(api,vals,5.4,27)
            text(slide, api, 1.18, y+max(0,(h-need)/2), 5.4, max(need,.5), vals, 27,c["ink"],spec)
            shape(slide,7.1,1.8,5.3,end-1.8,c["white"])
            _, warning=picture(api, slide,img[0],7.276666,2.0,4.95,end-2.1,img[1],img[2],center_v=True)
        if warning: warns.append(warning)
    else:
        # Native editorial list: mathematical statements occupy the page field.
        if vals:
            need=_height(api,vals,10.6,29)
            top=y+max(0,(h-need)/2)
            shape(slide,.92,top,.045,max(.42,need),c["accent"])
            text(slide,api,1.25,top,10.6,max(need,.5),vals,29,c["ink"],spec)
            if need > h: warns.append("正文估算超高，请拆页")
    if page.answers:
        if role == "例题" and answer_y < 4.2:
            warns.append("例题答案超过书写区容量，请用后页讲解")
        text(slide,api,1.2,answer_y,10.6,answer_h,page.answers,24,
             c["white"] if dark else c["ink"],spec)
        slide.shapes[-1].name = api.ANSWER_BLOCK
    if page.emph:
        shape(slide,1.18,emph_y,10.9,.04,c["accent"] if not dark else c["soft"])
        text(slide,api,1.2,emph_y+.12,10.8,.55,[page.emph],26,
             c["white"] if dark else c["accent"],spec,bold=True)
    _question(slide,page,api,spec)
    return "；".join(warns) if warns else None
