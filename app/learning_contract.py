"""Teaching structure contract shared by prompts, validation and the learner view."""
import json
from pathlib import Path

CONSTRAINTS=json.loads((Path(__file__).resolve().parents[1]/'learning-task-designer/constraints.json').read_text())


def check_item(item):
    for key in CONSTRAINTS['required_item_fields']:
        if not isinstance(item.get(key),str) or not item[key].strip():raise ValueError(f'每题需要 {key}，使目标与验收对应。')
    if item.get('interactive_template','none') not in CONSTRAINTS['activity_templates']:
        raise ValueError('交互活动只能选择提供的数学模板。')


def scenes(item):
    definitions = [
        {'id':'attempt','title':'先自己试一试','type':'practice','objective':item['objective'],'success_criteria':item['success_criteria']},
        {'id':'explain','title':'需要时借一点帮助','type':'guidance','content':item.get('guidance') or '回看原题条件，说明每一步的依据；需要时请求一个提示。'},
        {'id':'interactive','title':'动手观察与解释','type':'interactive','template':item.get('interactive_template','none')},
        {'id':'independent_check','title':'换一道题独立复核','type':'assessment','requires_new_task':True},
    ]
    by_id={scene['id']:scene for scene in definitions}
    return [by_id[key] for key in CONSTRAINTS['scene_order']]
