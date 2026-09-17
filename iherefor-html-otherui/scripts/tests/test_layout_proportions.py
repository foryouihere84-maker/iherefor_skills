#!/usr/bin/env python3
"""回归：尺寸按闭合方式声明、位置相对直接父视图。

这条契约有两个可执行的部分，两边都要有「必须过 / 必须挂」：

1. ``layout_proportions.py`` 把事实表里的几何转成**闭合契约规格**。两轴八类：
   ``fixed`` / ``intrinsic`` / ``bounded`` / ``pinned`` / ``proportional`` / ``equal`` /
   ``centered`` / ``aspect-ratio``（尺寸轴 ``fixed`` / ``intrinsic`` / ``bounded`` /
   ``aspect-ratio``，关系轴 ``pinned`` / ``proportional`` / ``equal`` / ``centered``）；
   位置基准是**直接父视图**，父容器本身就是整屏画布时才是 ``root``。**``fixed`` 不是默认值**
   —— 它是「固定性本身是设计意图」的特例
   （图标、装饰、边框、明确固定高度的视觉控件）。生成端判不出这一层，所以它产出的每条
   ``fixed`` 都带 ``why``（推据）与 ``needsReview``，由 Agent 逐条复核。
2. ``check_layout_proportions.py`` 拿那份规格去核源码，**计划层与源码层都要判**。
   源码侧除了比例原语，还要逐类核对 ``intrinsic``（不得写等值常量）、``bounded``
   （必须有 >=/<= 原语）、``equal``、``aspect-ratio`` —— 否则「计划说 intrinsic、
   代码写死 widthAnchor」这个新契约要拦的头号问题就成了没人查的口头约定。
   **这个测试的核心是变异探针**：先把一份合规源码判为通过，只把其中一条比例换成它的
   设备推导值，再要求它被判为违规。没有这一步，测试只是「脚本跑得动」，而不是
   「脚本认得错」。

测试里每一条断言都对应一个**已经踩过的误判**，注释写在断言旁边：

* 视觉常量（图标 24、头像 48）必须判 ``fixed`` 并给出 why，不能因为「它随父容器排布」
  就判成比例；反过来，按钮宽度、卡片高度、文字区宽度也**不能**默认判成 fixed；
* 「贴父边」不是「比例」：左右各 16pt 要写约束闭合，写成 ``parent.width * 0.9186``
  在探针设备上同样对得上，换台设备就给不出 16；
* 纵向不照搬横向：24pt 图标装在 68pt 卡片里「上 16 下 28」，那个 28 是
  ``68 − 16 − 24`` 算出来的，不是设计稿写的内边距；
* 页面外框（``.page``）在 402pt 视口上量出 393pt 宽，那 9pt 残留是**源产物按画布
  尺寸写死**的副产物；照 9 写右边距就是凭空造出来的错；
* 小数点说明值是量出来的：``53.921875`` 与整数 54 只差 0.078，容差稍松就会被
  读成「设计稿写了 54」而判成 ``fixed``；
* 禁止清单**只收** ``proportional``：把 fixed 的字面量与 pinned 的内边距列进去，
  等于让「照设计稿做」被判违规 —— 那是契约没改完的形态，最难排查；
* 孤立的大偏移（33..64pt 且没有兄弟复用）既可能是内边距也可能是布局位置，
  降级为比例 + 提示，把判断权交回给 Agent，而不是替人拍板。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_SCRIPT = ROOT / "scripts" / "layout_proportions.py"
CHECK_SCRIPT = ROOT / "scripts" / "check_layout_proportions.py"

VIEWPORT = {"width": 402.0, "height": 874.0, "devicePixelRatio": 3.0,
            "scrollX": 0.0, "scrollY": 0.0}

# 禁止清单用锚点名（Region.leading），关系用轴名（Region.x）。
ANCHOR_AXIS = {"centerX": "x", "leading": "x", "width": "width",
               "centerY": "y", "top": "y", "height": "height"}


def element(index, eid, parent, rect, **extra):
    """按渲染器的真实字段造一个元素。

    ``rectInReference == rect * devicePixelRatio`` 是渲染器在设备视口上渲染的产物，
    也是 ``layout_proportions.py`` 用来判定坐标空间的唯一依据 —— 所以 fixture 必须
    如实构造这条恒等式，不能为了省事随手写个数。

    ``parentIndex`` 是 schemaVersion 3 起的事实表字段：最近可见祖先的下标，
    ``None`` 表示直接父视图就是整屏画布。**它必须落在父元素的 rect 之内** ——
    ``rect`` 是绝对坐标，不是父子局部坐标，写错会让父子的相对关系整个反过来。
    """
    dpr = VIEWPORT["devicePixelRatio"]
    payload = {
        "index": index, "id": eid, "className": eid, "tag": "div",
        "rect": rect,
        "rectInReference": {k: v * dpr for k, v in rect.items()},
        "parentIndex": parent,
        "parentHops": 0 if parent is None else 1,
        "ownText": "", "ownsText": False, "text": "", "src": None, "assets": None,
    }
    payload.update(extra)
    return payload


def page_facts(elements, schema=3):
    return {"schemaVersion": schema, "title": "fixture",
            "url": "file:///fixture/index.html",
            "viewport": dict(VIEWPORT), "elements": elements}


def box(x, y, width, height):
    return {"x": x, "y": y, "width": width, "height": height}


def standard_facts():
    """一台 402x874 设备上的 17 个元素，每个都钉住一条判据。

    括号里是它要证明的事；父链是 ``Screen > {NavBar, Card, Avatar, Button, Slot}``
    与 ``Card > {Icon, Label, CardTitle, NoteA, NoteB, Tag, Field, NoteWrap}``、
    ``Slot > Knob``。
    """
    return page_facts([
        # 页面外框：393x852 摆在 402x874 视口上（面积 95.3%），残留的 9/22 不是边距。
        element(0, "Screen", None, box(0, 0, 393, 852), text="Settings Continue"),
        # 整屏宽的表头，高 64 是设计稿给的封闭值。
        element(1, "NavBar", 0, box(0, 0, 393, 64), text="Settings"),
        # 卡片：左右各留 16pt（贴边闭合），高 68 是固定设计值，纵向位置随父容器。
        element(2, "Card", 0, box(16, 120, 361, 68)),
        # 24pt 图标装在 68pt 卡片里：上 16 下 28 —— 28 是 68−16−24 的副产品。
        element(3, "Icon", 2, box(32, 136, 24, 24), src="icon.png"),
        # 一行文字：高度由字体撑开，宽度也是（232pt 贴合文字）。
        element(4, "Label", 2, box(32, 148, 232, 16), ownText="Continue",
                ownsText=True, text="Continue"),
        # 头像 48x48：媒体元素但尺寸是设计值，不因「是图片」就判待复核。
        element(5, "Avatar", 0, box(16, 300, 48, 48), src="avatar.png"),
        # 与父视图居中：居中必须判 centered，而不是「两条比例凑出相等」。
        element(6, "CardTitle", 2, box(138.5, 136, 116, 16), ownText="Free trial",
                ownsText=True, text="Free trial"),
        # 左右各 37.5pt：半整数是设计值（37.5），且被兄弟复用（NoteB 也是 37.5）。
        element(7, "NoteA", 2, box(53.5, 136, 286, 12), ownText="a",
                ownsText=True, text="a"),
        element(8, "NoteB", 2, box(53.5, 152, 286, 12), ownText="b",
                ownsText=True, text="b"),
        # 宽 53.921875：小数尾巴说明它是量出来的，设计稿不会写这个数。
        element(9, "Tag", 2, box(200, 136, 53.921875, 16), ownText="New",
                ownsText=True, text="New"),
        # 左右内边距不等（23 / 32）：比例化最容易出错的形态，两边都要各自闭合。
        element(10, "Field", 2, box(39, 152, 306, 12)),
        # 全宽按钮：左右各 16pt，高由文字撑开。
        element(11, "Button", 0, box(16, 700, 361, 44), ownText="Continue",
                ownsText=True, text="Continue"),
        # 60x60 的槽，自身是固定尺寸；它的子元素给出「孤立大偏移」的情形。
        element(12, "Slot", 0, box(0, 400, 60, 60)),
        # 距父视图左侧 40pt 且没有兄弟共享 ⇒ 降级比例 + 提示，而不是替人拍板。
        element(13, "Knob", 12, box(40, 425, 12, 12)),
        # 挂在左边的装饰条（溢出父容器）：自身比例会跑出 [0,1]。
        element(14, "Rail", 0, box(-100, 240, 200, 20)),
        # 它的**设备坐标**恰好落在原点上（局部偏移 100pt，父视图原点 −100）：
        # 这条比例关系的设备推导值是 0，而 0 在任何设备上都成立，不构成证据 ——
        # 必须进 skippedForbidden，而不是禁止清单。
        element(15, "Dot", 14, box(0, 245, 20, 10)),
        # 自己没有文本、子树里有文本的短盒子（实测 text-wrapper_19 就是这种形态）：
        # ownsText=False、ownText=""，高度 16 完全由字体撑开。判据必须看 text 而不只看
        # ownText —— 只看 ownText 会把它判成 proportional，于是「字体撑开的量」被当成
        # 容器比例，16 这个标准边距还会跟着撞进禁止清单。
        element(16, "NoteWrap", 2, box(53.5, 168, 286, 16),
                text="Free trial enabled / Cancle anytime"),
    ])


def legacy_facts():
    """没有 ``parentIndex`` 的旧事实表：必须退回整屏画布**并如实告警**。"""
    elements = standard_facts()["elements"]
    for item in elements:
        item.pop("parentIndex")
        item.pop("parentHops")
    return page_facts(elements, schema=2)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


def run_plan(tmp, facts_path, *extra, output_name="plan.json", expect=0):
    out = tmp / output_name
    proc = run(PLAN_SCRIPT, "--page-facts", str(facts_path),
               "--output", str(out), "--quiet", *extra)
    if proc.returncode != expect:
        raise AssertionError(f"layout_proportions 退出码 {proc.returncode}！= {expect}\n"
                             f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    if expect != 0:
        return None
    return json.loads(out.read_text())


def run_check(tmp, plan_path, source, *extra, output_name="check.json"):
    args = [str(CHECK_SCRIPT), "--plan", str(plan_path)]
    if source is not None:
        args += ["--source", str(source)]
    out = tmp / output_name
    proc = run(*args, "--output", str(out), *extra)
    data = json.loads(out.read_text()) if out.is_file() else None
    return proc, data


def relations_of(plan, region_name):
    for region in plan["layoutProportions"]["regions"]:
        if region["region"] == region_name:
            return {rel["id"]: rel for rel in region["relations"]}
    raise AssertionError(f"计划里没有区域 {region_name}")


ANCHOR_NAME = {"x": {"leading": "leadingAnchor", "trailing": "trailingAnchor"},
               "y": {"leading": "topAnchor", "trailing": "bottomAnchor"},
               # 尺寸轴的 pinned 同样是「两侧各自闭合」，锚点名与位置轴一致。
               "width": {"leading": "leadingAnchor", "trailing": "trailingAnchor"},
               "height": {"leading": "topAnchor", "trailing": "bottomAnchor"}}


def compliant_source(plan):
    """按计划生成一份「合规」的 Objective-C 源码：每一类都按它自己的写法表达。

    这是实现侧应有的样子 —— 没有一条约束是从「探针设备上的绝对值」抄来的：

    * ``proportional`` → ``multiplier``；
    * ``pinned`` → ``constraintEqualTo:<父视图锚点> constant:<内边距>``；
    * ``fixed`` → ``constraintEqualToConstant:<设计值>``；
    * ``centered`` → 对齐父视图中心锚点；
    * ``intrinsic`` → 不加尺寸约束（注释说明 Why）。
    """
    lines = ["// 由 layoutProportions 生成：尺寸写设计常量、位置相对直接父视图",
             "static void buildLayout(UIView *root) {",
             "  [root layoutIfNeeded];"]
    for region in plan["layoutProportions"]["regions"]:
        name = region["region"]
        for rel in region["relations"]:
            base = rel.get("of") or "root"
            kind, axis = rel["kind"], rel["axis"]
            if kind == "proportional":
                if axis == "width":
                    body = (f"[[self {name}] widthAnchor constraintEqualTo:"
                            f"{base}.widthAnchor multiplier:{rel['ratio']}];")
                elif axis == "height":
                    body = (f"[[self {name}] heightAnchor constraintEqualTo:"
                            f"{base}.heightAnchor multiplier:{rel['ratio']}];")
                elif axis == "x":
                    body = (f"[[self {name}] leadingAnchor constraintEqualTo:"
                            f"{base}.leadingAnchor multiplier:{rel['ratio']}];")
                else:
                    body = (f"[[self {name}] topAnchor constraintEqualTo:"
                            f"{base}.topAnchor multiplier:{rel['ratio']}];")
                lines.append(f"  {body}  // {rel['id']}")
            elif kind == "pinned":
                for edge in rel.get("edges") or [rel.get("edge")]:
                    anchor = ANCHOR_NAME[axis][edge]
                    inset = (rel.get("insets") or {}).get(edge, rel.get("inset", 0.0))
                    lines.append(f"  [[self {name}] {anchor} constraintEqualTo:"
                                 f"{base}.{anchor} constant:{inset:g}];  // {rel['id']}")
            elif kind == "fixed":
                dim = "widthAnchor" if axis == "width" else "heightAnchor"
                lines.append(f"  [[self {name}] {dim} constraintEqualToConstant:"
                             f"{rel['value']:g}];  // {rel['id']}")
            elif kind == "centered":
                side = "X" if axis == "x" else "Y"
                lines.append(f"  [[self {name}] center{side}Anchor constraintEqualTo:"
                             f"{base}.center{side}Anchor];  // {rel['id']}")
            else:
                lines.append(f"  // {rel['id']} 内容撑开，不加尺寸约束：{rel.get('why', '')}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def relation_line(source, relation_id):
    """合规源码里某个关系对应的行（返回 行号, 行文本）。

    必须在**变异之前**取行号：变异后那一行的内容变了，按内容去 index 只会找到
    ``fixed`` 关系生成的 ``constraintEqualToConstant``，报出来的位置是错的
    —— 旧版就踩过这个坑（变异行的定位落到了另一条 fixed 行上）。
    """
    for number, line in enumerate(source.splitlines(), start=1):
        if line.rstrip().endswith(f"// {relation_id}"):
            return number, line
    raise AssertionError(f"合规源码里找不到关系 {relation_id} 对应的行")


def mutation_target(plan):
    """挑一条可以无歧义变异的比例关系：返回值大于 48pt 的禁止项。

    必须同时满足「锚点指向一条 proportional 关系」且「``ratioInstead`` 就是那条关系的
    ``ratio``」：否则合规源码里根本没有对应的 ``multiplier:<值>``，变异会静默不生效，
    探针就成了空探针。中心锚点（``centerY``）的 ``ratioInstead`` 是**中心**比例，
    与关系里的 ``top`` 比例不同，所以会被这个条件筛掉。
    """
    props = plan["layoutProportions"]
    ratio_by_relation = {rel["id"]: rel.get("ratio")
                         for region in props["regions"] for rel in region["relations"]}
    for item in props["forbiddenLiterals"]:
        if abs(item["deviceDerivedPt"]) <= 48:
            continue
        region_name, _, anchor = item["relation"].rpartition(".")
        axis = ANCHOR_AXIS.get(anchor)
        if axis is None:
            continue
        if ratio_by_relation.get(f"{region_name}.{axis}") == item["ratioInstead"]:
            return item, f"{region_name}.{axis}"
    raise AssertionError("计划里没有可用于变异的大数值关系，测试前提不成立")


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        facts_path = write_json(tmp / "reference" / "page-facts.json", standard_facts())

        # ---------------------------------------------------------------- 计划推导
        plan = run_plan(tmp, facts_path)
        props = plan["layoutProportions"]
        diag = plan["diagnostics"]
        regions = {r["region"]: r for r in props["regions"]}

        # 用例 1：坐标空间必须由 rectInReference == rect*dpr 自动判定；
        # 模型的字段名必须说明它到底是哪一套口径。
        check(diag["rectSpace"] == "device",
              f"用例1：rect 坐标空间判定为 {diag['rectSpace']}，应为 device")
        check(props["basisSize"] == {"width": 402.0, "height": 874.0},
              f"用例1：基准应为探针视口 402x874，得到 {props['basisSize']}")
        # 模型名从 v3 的 "fixed-size-parent-relative-position" 改为闭合契约的
        # "closure-declared-parent-relative-position"：旧名把「尺寸固定」写进口径里，
        # 而新契约下尺寸是**声明闭合方式**，fixed 只是其中一种（非默认）。
        check(props["model"] == "closure-declared-parent-relative-position",
              f"用例1：模型名应写明「尺寸按闭合方式声明 + 位置相对父视图」，得到 {props['model']}")
        check(diag["schemaVersion"] >= 4,
              f"用例1：闭合契约起 schemaVersion 应为 4，得到 {diag['schemaVersion']}"
              "（v3 的 fixed 是「尺寸是常量」的老结论，不能与 v4 混读）")
        check(props["axisPolicy"] == "per-axis" and props["basis"] == "viewport",
              f"用例1：逐轴口径与基准字段不对：{props['axisPolicy']}/{props['basis']}")
        check(diag["hierarchyAvailable"] is True,
              "用例1：事实表带 parentIndex，层级应判为可用")

        # 用例 2：区域必须带父视图身份，位置基准是**直接父视图**而不是整页。
        for region in props["regions"]:
            missing = [k for k in ("region", "index", "parentIndex", "parent", "basis",
                                   "kindSource", "ratios", "relations", "nativeIdiom")
                       if k not in region]
            if missing:
                check(False, f"用例2：{region.get('region')} 缺字段 {missing}")
                break
        icon = regions["Icon"]
        check(icon["parent"] == "Card" and icon["parentIndex"] == 2
              and icon["basis"] == "parent",
              f"用例2：Icon 的基准应是直接父视图 Card，得到 "
              f"{icon['parent']}/{icon['basis']}")
        check(regions["Screen"]["parent"] == "root"
              and regions["Screen"]["basis"] == "viewport",
              f"用例2：挂在整屏画布下的元素基准才是 viewport/root，得到 "
              f"{regions['Screen']['parent']}/{regions['Screen']['basis']}")
        for rel in icon["relations"]:
            if rel["of"] != "Card" or rel["ofIndex"] != 2:
                check(False, f"用例2：{rel['id']} 的 of 应指向 Card(2)，得到 "
                             f"{rel['of']}/{rel['ofIndex']}")
                break
        knob_x = relations_of(plan, "Knob")["Knob.x"]
        check(knob_x["of"] == "Slot" and knob_x["ofIndex"] == 12,
              f"用例2：Knob 的基准应是它的直接父视图 Slot，得到 {knob_x['of']}")
        # 区域必须同时给出「边缘」与「中心」两套比例。实现侧两种锚点都会用到
        # （leading/top 与 centerX/centerY），只给中心比例会让「按左边缘对齐」
        # 这个最常见的写法没有可用的比例。
        expected_ratio_keys = {"xRatio", "yRatio", "centerXRatio", "centerYRatio",
                               "widthRatio", "heightRatio"}
        for region in props["regions"]:
            if set(region["ratios"]) != expected_ratio_keys:
                check(False, f"用例2：{region['region']} 的 ratios 缺键："
                             f"{sorted(region['ratios'])}")
                break

        # 用例 3：控件尺寸是**常量**（设计稿给的封闭值），写成字面量。
        for region_name, axis, expected in (("Icon", "width", 24), ("Icon", "height", 24),
                                            ("Avatar", "height", 48), ("NavBar", "height", 64),
                                            ("Card", "height", 68),
                                            ("CardTitle", "width", 116)):
            rel = relations_of(plan, region_name)[f"{region_name}.{axis}"]
            if rel["kind"] != "fixed" or rel.get("value") != expected:
                check(False, f"用例3：{region_name}.{axis} 应为 fixed({expected})，得到 "
                             f"{rel['kind']}({rel.get('value')})")
        check(all("ratio" not in rel for region in props["regions"]
                  for rel in region["relations"] if rel["kind"] == "fixed"),
              "用例3：fixed 关系不得带比例系数（那是「既写死又缩放」的自相矛盾）")

        # 用例 4：贴父边是**约束闭合**，不是比例。左右各 16pt 必须各自成边；
        # 左右不等（23/32）也要能表达 —— 那正是比例化最容易出错的形态。
        # 注意 Card.x 是**第一层子视图**（直接父 = Screen/page），位置按页面比例重排
        # （见用例 4b），所以这里只验仍属**第二层**的 Field/NoteA 保持 pinned 闭合。
        card = relations_of(plan, "Card")
        check(card["Card.width"]["kind"] == "pinned"
              and card["Card.width"].get("insets") == {"leading": 16.0, "trailing": 16.0},
              f"用例4：Card.width 应为两侧各 16pt 的 pinned，得到 {card['Card.width']}")
        field_width = relations_of(plan, "Field")["Field.x"]
        check(field_width["kind"] == "pinned" and field_width.get("inset") == 23.0,
              f"用例4：Field.x 应为 pinned(23)，得到 {field_width}")
        note = relations_of(plan, "NoteA")["NoteA.width"]
        check(note["kind"] == "pinned" and note.get("inset") == 37.5,
              f"用例4：NoteA.width 的两侧 37.5pt 应合并成 pinned(37.5)，得到 {note}")
        check(all("ratio" not in rel for region in props["regions"]
                  for rel in region["relations"] if rel["kind"] == "pinned"),
              "用例4：pinned 关系不得带比例系数 —— 贴父边的正确写法是约束闭合")

        # 用例 4c：生成端产出的 fixed 一律是**候选** —— 必须带 why 说明推据、带 needsReview
        # 提示复核。闭合契约下 fixed 只留给视觉常量，而按钮宽度/卡片高度/文字区宽度
        # 都得由内容或边界闭合，生成端判不出来，所以它只能给候选、不能给结论。
        fixed_rels = [(region["region"], rel)
                      for region in props["regions"] for rel in region["relations"]
                      if rel.get("kind") == "fixed"]
        check(fixed_rels, "用例4c：这份事实表里应当有被判为 fixed 的控件量级尺寸")
        for region_name, rel in fixed_rels:
            check(bool((rel.get("why") or "").strip()),
                  f"用例4c：{rel['id']} 判为 fixed 必须带 why（推据），得到 {rel.get('why')!r}")
            check(rel.get("needsReview") is True,
                  f"用例4c：{rel['id']} 判为 fixed 必须标记 needsReview，"
                  "否则「生成端默认给 fixed」就等于把旧契约的默认值捡回来了")

        # 用例 4b：第一层子视图只强制**水平**比例。纵向必须回到普通 Auto Layout
        # 分类，不能把页面高度比例当默认响应式策略。
        first_level = ["NavBar", "Card", "Avatar", "Button", "Slot", "Rail"]
        for name in first_level:
            rel = relations_of(plan, name)
            x_rel = rel[f"{name}.x"]
            y_rel = rel[f"{name}.y"]
            check(x_rel["kind"] == "proportional" and x_rel.get("forced") == "first-level",
                  f"用例4b：{name}.x 是第一层，位置应强制 proportional，得到 {x_rel}")
            check(y_rel.get("forced") != "first-level",
                  f"用例4b：{name}.y 不应强制 first-level proportional，得到 {y_rel}")
        # 第一层的**尺寸**独立判定：以 NavBar 高 64 为例，它是控件量级的候选 fixed，
        # 也就是「待 Agent 确认的视觉常量」—— 不是「组件尺寸恒等于设计稿」。
        nav_height = relations_of(plan, "NavBar")["NavBar.height"]
        check(nav_height["kind"] == "fixed" and nav_height.get("value") == 64
              and nav_height.get("needsReview") is True,
              f"用例4b：第一层尺寸是独立判定的候选（fixed 候选必须带 needsReview），"
              f"得到 {nav_height}")
        # 第二层（Card 的子元素 Icon/Label）位置**不**被强制比例 —— 相对关系固定。
        icon_rel = relations_of(plan, "Icon")
        check(icon_rel["Icon.x"]["of"] == "Card"
              and "forced" not in icon_rel["Icon.x"],
              f"用例4b：第二层的相对关系必须固定，Icon.x 不应被强制比例，得到 "
              f"{icon_rel['Icon.x']}")

        # 用例 5：纵向不照搬横向。24pt 图标装在 68pt 卡片里「上 16 下 28」，
        # 那个 28 是 68−16−24 的副产品；高度该判 fixed(24) 而不是 pinned。
        icon_rel = relations_of(plan, "Icon")
        check(icon_rel["Icon.height"]["kind"] == "fixed"
              and icon_rel["Icon.height"].get("value") == 24,
              f"用例5：图标高度应判 fixed(24)，得到 {icon_rel['Icon.height']}")
        check(icon_rel["Icon.y"]["kind"] == "pinned"
              and icon_rel["Icon.y"].get("inset") == 16.0,
              f"用例5：图标的上偏移 16pt 是真内边距，应判 pinned，得到 {icon_rel['Icon.y']}")
        card_height = relations_of(plan, "Card")["Card.height"]
        check(all(rel["kind"] != "pinned" for rel in
                  (card_height, relations_of(plan, "Label")["Label.height"])),
              "用例5：卡片高度与文字块高度都不该判 pinned（纵向偏移不是设计内边距）")

        # 用例 6：页面外框按**铺满**处理。393x852 摆在 402x874 视口上量出 9/22pt 残留，
        # 那是源产物按画布尺寸写死的副产物；照 9 写右边距就是凭空造出来的错。
        screen = regions["Screen"]
        check(all(rel["kind"] == "pinned" for rel in screen["relations"]),
              f"用例6：页面外框四轴都应按贴边/铺满处理，得到 "
              f"{[(r['id'], r['kind']) for r in screen['relations']]}")
        screen_width = next(r for r in screen["relations"] if r["id"] == "Screen.width")
        check(screen_width.get("fullBleed") is True
              and screen_width.get("insets") == {"leading": 0.0, "trailing": 0.0},
              f"用例6：页面外框宽度应标 fullBleed 且内边距为 0，得到 {screen_width}")

        # 用例 7：与父视图居中要判 centered，不能拿两条比例凑相等。
        title_x = relations_of(plan, "CardTitle")["CardTitle.x"]
        check(title_x["kind"] == "centered",
              f"用例7：CardTitle.x 应判 centered，得到 {title_x['kind']}")
        check(all("ratio" not in rel for region in props["regions"]
                  for rel in region["relations"] if rel["kind"] == "centered"),
              "用例7：centered 关系不得带比例系数")

        # 用例 8：文字撑开的尺寸判 intrinsic，**并且必须写明 why**。
        for region_name, axis in (("Label", "height"), ("Label", "width"),
                                  ("Tag", "height"), ("NoteA", "height"),
                                  ("NoteWrap", "height")):
            rel = relations_of(plan, region_name)[f"{region_name}.{axis}"]
            if rel["kind"] != "intrinsic" or not (rel.get("why") or "").strip():
                check(False, f"用例8：{region_name}.{axis} 应判 intrinsic 且写明 why，"
                             f"得到 {rel['kind']}/{rel.get('why')!r}")
        # NoteWrap 是「自己没有文本、子树里有文本」的那一类：判据必须看 ``text``
        # 而不只看 ``ownText``，否则它 16pt 的高度会被当成容器比例或固定设计值 ——
        # 前者把字体撑开的量比例化，后者在字号/父容器一变就散架。
        wrap_rel = relations_of(plan, "NoteWrap")["NoteWrap.height"]
        check(wrap_rel["kind"] == "intrinsic" and "文字块" in (wrap_rel.get("why") or ""),
              f"用例8：没有 ownText 但子树含文本的短盒子应判文字块 intrinsic，得到 "
              f"{wrap_rel['kind']}/{wrap_rel.get('why')!r}")
        check(any(h["region"] == "NoteWrap" and "ownsText" in h["hint"]
                  for h in diag.get("reviewHints") or []),
              "用例8：推断成文字块时必须有 reviewHint 说明理由，把判断权交回给 Agent")

        # 用例 9：小数点说明值是量出来的。53.921875 距整数 54 只差 0.078 ——
        # 容差稍松就会被读成「设计稿写了 54」而判成 fixed。
        tag_width = relations_of(plan, "Tag")["Tag.width"]
        check(tag_width["kind"] == "intrinsic",
              f"用例9：53.921875pt 宽的贴合文字行应判 intrinsic，得到 "
              f"{tag_width['kind']}({tag_width.get('value')})")

        # 用例 10：孤立的大偏移（40pt，没有兄弟共享）降级为比例**并给出提示**，
        # 而不是凭量级替人拍板。
        check(knob_x["kind"] == "proportional",
              f"用例10：孤立的 40pt 左偏移应降级为比例，得到 {knob_x['kind']}")
        knob_hints = [h for h in diag.get("reviewHints") or [] if h["region"] == "Knob"]
        check(knob_hints,
              "用例10：降级判定的元素必须有 reviewHint，把判断权交回给 Agent")
        check(any("40" in h["hint"] for h in knob_hints),
              f"用例10：提示里应写出被降级的那个偏移量，得到 {knob_hints}")

        # 用例 11：禁止清单**只收 proportional**，且绝对值与比例必须**同量纲、各自闭合**。
        #
        # 后半条是修过的一个真错：早期把左/上边缘的绝对值配给了**中心**比例
        # （``Card.top`` 120pt 配上 ``centerYRatio``），开发者照做会把元素整体下移
        # 半个高度 —— 这条「指导」本身就是错的。所以中心锚点必须配中心比例，
        # 边缘锚点必须配边缘比例，两者不能混。
        RATIO_FIELD_FOR_ANCHOR = {"leading": "xRatio", "centerX": "centerXRatio",
                                  "top": "yRatio", "centerY": "centerYRatio",
                                  "width": "widthRatio", "height": "heightRatio"}
        EDGE_RATIO_FIELD = {"top": "yRatio", "leading": "xRatio"}
        CENTER_RATIO_FIELD = {"top": "centerYRatio", "leading": "centerXRatio"}
        region_ratios = {r["region"]: r["ratios"] for r in props["regions"]}
        kind_by_relation = {rel["id"]: rel["kind"] for region in props["regions"]
                            for rel in region["relations"]}
        targets, mismatched, wrong_kind, cross_wired = [], [], [], []
        for item in props["forbiddenLiterals"]:
            region_name, _, anchor = item["relation"].rpartition(".")
            axis = ANCHOR_AXIS.get(anchor)
            if axis is None:
                targets.append(item)
                continue
            relation_id = f"{region_name}.{axis}"
            if kind_by_relation.get(relation_id) != "proportional":
                wrong_kind.append((item["relation"], kind_by_relation.get(relation_id)))
                continue
            ratios = region_ratios.get(region_name) or {}
            expected = ratios.get(RATIO_FIELD_FOR_ANCHOR[anchor])
            if expected is None or abs(item["ratioInstead"] - expected) > 1e-5:
                mismatched.append((item["relation"], item["ratioInstead"], expected))
            if anchor in EDGE_RATIO_FIELD and abs(
                    item["ratioInstead"] - ratios.get(CENTER_RATIO_FIELD[anchor], -1)) <= 1e-5:
                cross_wired.append(item["relation"])
        check(not targets, f"用例11：禁止清单出现无法与关系对上的锚点：{targets[:2]}")
        check(not wrong_kind,
              f"用例11：禁止清单指向了非 proportional 的关系（应当直接写字面量）："
              f"{wrong_kind[:3]}")
        check(not mismatched,
              f"用例11：ratioInstead 与它自己那个量的比例对不上（绝对值与比例必须同量纲）："
              f"{mismatched[:3]}")
        check(not cross_wired,
              f"用例11：边缘锚点配上了中心比例 —— 照做会让元素整体偏移半个尺寸："
              f"{cross_wired[:3]}")
        check(props["forbiddenLiterals"],
              "用例11：计划里应当有禁止项（这个 fixture 有若干 proportional 位置关系）")

        # 用例 12：禁止项里的绝对值必须是**设备空间**的绝对坐标 —— 那才是真正会被
        # 误写进代码的数字 —— 而且必须配**同量纲**的比例。
        #
        # 这里**穷举**核对每一个禁止项，而不是挑几个名字看一眼。挑着看会漏掉整整一类：
        # 把 ``centerX`` 的绝对值配成边缘值时，只有中心锚点会错，而它偏偏不在
        # 「眼熟的那几个」里 —— 照那条错指导做，元素会整体左移半个宽度。
        rect_by_region = {e["className"]: e["rect"] for e in standard_facts()["elements"]}
        by_relation = {item["relation"]: item for item in props["forbiddenLiterals"]}
        DEVICE_VALUE = {
            "leading": lambda r: r["x"],
            "centerX": lambda r: r["x"] + r["width"] / 2,
            "top": lambda r: r["y"],
            "centerY": lambda r: r["y"] + r["height"] / 2,
            "width": lambda r: r["width"],
            "height": lambda r: r["height"],
        }
        for item in props["forbiddenLiterals"]:
            region_name, _, anchor = item["relation"].rpartition(".")
            rect = rect_by_region.get(region_name)
            if rect is None or anchor not in DEVICE_VALUE:
                check(False, f"用例12：禁止项 {item['relation']} 对不到 fixture 里的元素")
                continue
            expected = DEVICE_VALUE[anchor](rect)
            if abs(item["deviceDerivedPt"] - expected) > 0.05:
                check(False, f"用例12：{item['relation']} 的设备推导值应为 {expected:g}pt"
                             f"（设备空间的绝对坐标），得到 {item['deviceDerivedPt']}")

        # 用例 13：设计常量候选要汇总可复核的「允许写的字面量」；
        # 0 不入列（0 在任何设备上都成立，列进去是噪音）。
        insets = props["designConstantCandidates"]["pinnedInsets"]
        check(37.5 in insets and 23.0 in insets and 32.0 in insets and 16.0 in insets,
              f"用例13：贴边内边距（含半整数 37.5）应汇总进设计常量候选，得到 {insets}")
        check(0 not in insets, f"用例13：0 不应进设计常量候选，得到 {insets}")

        # 用例 14：接近原点的绝对值不构成证据（0 在任何设备上都成立）。
        check(not [f for f in props["forbiddenLiterals"] if abs(f["deviceDerivedPt"]) < 1],
              "用例14：禁止清单里不应有 |pt| < 1 的条目")
        check(diag["skippedForbiddenCount"] > 0,
              "用例14：贴在原点/父边上的关系应被记入 skippedForbidden 而不是禁止清单")

        # 用例 15：没有层级字段的旧事实表 —— 退回整屏画布**并如实告警**，
        # 而不是默默当作「父就是画布」（那正是要修的错）。
        legacy = run_plan(tmp, write_json(tmp / "legacy.json", legacy_facts()),
                          output_name="legacy-plan.json")
        check(legacy["diagnostics"]["hierarchyAvailable"] is False,
              "用例15：旧事实表应判为没有层级信息")
        check(any("parentIndex" in w for w in legacy["diagnostics"]["warnings"]),
              f"用例15：缺层级时必须告警并说明后果，得到 "
              f"{legacy['diagnostics']['warnings']}")
        legacy_relations = [rel for region in legacy["layoutProportions"]["regions"]
                            for rel in region["relations"]]
        check(all(rel["of"] == "root" for rel in legacy_relations),
              "用例15：没有层级时所有关系都应退回整屏画布基准")
        check(all(region["basis"] == "viewport"
                  for region in legacy["layoutProportions"]["regions"]),
              "用例15：没有层级时所有区域的 basis 都应是 viewport")

        # ------------------------------------------------------- 校验器：阳性对照
        source_dir = tmp / "src-pass"
        source_dir.mkdir()
        source = compliant_source(plan)
        (source_dir / "Layout.m").write_text(source)

        proc, data = run_check(tmp, tmp / "plan.json", source_dir)
        check(proc.returncode == 0 and data and data["status"] == "pass",
              f"用例16：合规源码应通过，得到退出码 {proc.returncode}，"
              f"违规 {data and data['violations']}")
        check(data and data["proportionalIdiomCount"] > 0,
              "用例16：合规源码里应识别出比例原语")
        check(data and data["pinnedIdiomCount"] > 0,
              "用例16：合规源码里应识别出贴边原语")
        check(data and data["relationKindCounts"]["fixed"] > 0
              and data["relationKindCounts"]["centered"] > 0
              and data["relationKindCounts"]["pinned"] > 0,
              f"用例16：结果应逐类报告关系计数（两轴八类），得到 {data and data['relationKindCounts']}")
        check(data and data["forbiddenLiteralCount"] == len(props["forbiddenLiterals"]),
              "用例16：结果里的禁止项条数应与计划一致")

        # 用例 17：--plan-only 复用同一套计划质量判定（run 校验器用它），
        # 它不该报「一个比例原语都没有」—— 那时根本没扫源码。
        proc, data = run_check(tmp, tmp / "plan.json", None, "--plan-only",
                               output_name="plan-only.json")
        check(proc.returncode == 0 and data and data["planOnly"] is True,
              f"用例17：合规计划在 --plan-only 下应通过，得到 {proc.returncode}："
              f"{data and data['violations']}")
        check(data and data["proportionalIdiomCount"] == 0 and data["sourceFiles"] == [],
              "用例17：--plan-only 不应扫源码")

        # --------------------------------------------------- 校验器：变异探针（核心）
        # 只改一处：把一条比例换成它的设备推导值。这必须被抓到 ——
        # 否则上面的「合规通过」只是脚本跑得动，不是脚本认得错。
        target, target_relation = mutation_target(plan)
        line_number, target_line = relation_line(source, target_relation)
        mutated_line = target_line.replace(
            f"multiplier:{target['ratioInstead']}",
            f"constraintEqualToConstant:{target['deviceDerivedPt']:g}")
        check(mutated_line != target_line,
              f"用例18：探针前提不成立 —— 第 {line_number} 行里找不到 "
              f"multiplier:{target['ratioInstead']}")
        mutated_source = source.replace(target_line, mutated_line, 1)
        check(mutated_source != source, "用例18：变异没有生效，探针无效")

        mutated_dir = tmp / "src-fail"
        mutated_dir.mkdir()
        (mutated_dir / "Layout.m").write_text(mutated_source)

        proc, data = run_check(tmp, tmp / "plan.json", mutated_dir, output_name="mutated.json")
        hits = [v for v in (data or {}).get("violations", [])
                if v["kind"] == "forbidden-literal-used"]
        check(proc.returncode == 1 and hits,
              f"用例18：把比例换成设备推导值 {target['deviceDerivedPt']:g}pt 未被拦下"
              f"（退出码 {proc.returncode}）")
        check(any(v.get("line") == line_number
                  and abs((v.get("literal") or 0) - target["deviceDerivedPt"]) < 0.05
                  for v in hits),
              f"用例18：违规应精确定位到第 {line_number} 行的 "
              f"{target['deviceDerivedPt']:g}，得到 "
              f"{[(v.get('line'), v.get('literal')) for v in hits[:3]]}")
        check(any(v.get("relation") == target["relation"] for v in hits),
              f"用例18：应指向关系 {target['relation']}（同一关系上也应给出应当用的比例），"
              f"得到 {[v.get('relation') for v in hits[:3]]}")
        check(any(v.get("expectedRatio") == target["ratioInstead"] for v in hits),
              "用例18：违规必须同时给出「应当使用的比例」")

        # 用例 19：整页都是绝对值（一个比例原语都没有）必须被指出，
        # 并且设备推导值要被抓到。
        absolute_dir = tmp / "src-absolute"
        absolute_dir.mkdir()
        (absolute_dir / "HardCoded.m").write_text(
            "UIView *hero = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 393, 472)];\n"
            "UIImageView *card = [[UIImageView alloc] initWithFrame:"
            "CGRectMake(16, 120, 361, 68)];\n"
            "UIButton *cta = [[UIButton alloc] initWithFrame:CGRectMake(16, 700, 361, 44)];\n")
        proc, data = run_check(tmp, tmp / "plan.json", absolute_dir,
                               output_name="absolute.json")
        kinds = {v["kind"] for v in (data or {}).get("violations", [])}
        check(proc.returncode == 1 and "no-proportional-idiom" in kinds,
              f"用例19：整页绝对值应被报 no-proportional-idiom，得到 {kinds}")
        check(any(abs((v.get("literal") or 0) - 700.0) < 0.05
                  for v in (data or {}).get("violations", [])),
              f"用例19：Button.top 的设备推导值 700 应被识别，得到 "
              f"{[(v.get('literal'), v.get('relation')) for v in (data or {}).get('violations', [])][:5]}")

        # ------------------------------------------------------ 降噪规则（防回退）
        #
        # 这一组要证明「注释里的数字不构成违规」。而 393/852/22 这类数字**根本不在禁止
        # 清单里** —— 就算把注释剥离整个关掉，它们也不会命中，那断言等于没写（变异探针
        # 抓到过这一点）。所以先从禁止清单里挑一条 >48pt 的**真实**设备推导值写进注释做
        # 对照：把注释当违规，等于让人去改注释，既没用又荒谬。
        big_items = [f for f in props["forbiddenLiterals"] if f["deviceDerivedPt"] > 48]
        check(big_items, "用例20：测试前提不成立 —— 禁止清单里应有一条 >48pt 的设备推导值")
        big_value = big_items[0]["deviceDerivedPt"] if big_items else 0.0

        noise_dir = tmp / "src-noise"
        noise_dir.mkdir()
        (noise_dir / "Noise.m").write_text(
            f"// 探针设备上是 {big_value:g}（402x874），换台设备即失效 —— 解释不是布局\n"
            f"/* 块注释里写 {big_value:g} 同样不该算 */\n"
            "// (393 x 852, index.css `.page`) 是设计稿画布，不是布局值\n"
            "// an iOS 26 scene; keep <some> 26pt margin\n"
            "UIColor *ink = [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 "
            "blue:22 / 255.0 alpha:1];\n"
            "layer.backgroundSize = @\"100% 100%\";\n"
            "[[self view] widthAnchor].constant = 353.51;\n")
        proc, data = run_check(tmp, tmp / "plan.json", noise_dir, output_name="noise.json")
        flagged = (data or {}).get("violations", [])
        check(not [v for v in flagged if v.get("literal") in (393.0, 852.0, 22.0)],
              f"用例20：注释/颜色通道/百分比里的数字被误报："
              f"{[(v.get('literal'), v.get('text', '')[:40]) for v in flagged][:3]}")
        check(not [v for v in flagged if v.get("literal") == big_value],
              f"用例20：注释里的设备推导值 {big_value:g} 被算成了违规 —— 注释是在解释，"
              f"不是在布局，得到 "
              f"{[(v.get('literal'), v.get('text', '')[:40]) for v in flagged][:3]}")
        # 393 与 852 出现在注释与颜色里，但 353.51 是真字面量且不在禁止清单里 ——
        # 于是这份文件应当「没有大数值违规」，只可能剩下缺少比例原语。
        check({v["kind"] for v in flagged} <= {"no-proportional-idiom"},
              f"用例20：噪声文件只应剩 no-proportional-idiom，得到 "
              f"{[v['kind'] for v in flagged]}")

        # 用例 21：小数值与设计常量无法区分 —— 待判，不计入违规。
        # 这一条是信噪比的关键：把 16/24/32/40 当违规会让报告被淹没。
        # Knob.leading 在探针设备上是 40pt，同时也可能只是某个设计常量。
        # 前提必须**显式**核对，不能直接下标取值：前提不成立时下标会 KeyError 掉栈，
        # 退出码非 0 于是被读成「断言有效」，而这里要守的那条断言一次都没执行 ——
        # 变异探针把这种情况单独判为无效。所以缺项也要走 check，留下可读的理由。
        knob_item = by_relation.get("Knob.leading")
        check(knob_item is not None,
              "用例21：测试前提不成立 —— 孤立的 40pt 左偏移应降级为比例并进入禁止清单")
        small_value = (knob_item or {}).get("deviceDerivedPt", 0.0)
        check(small_value <= 48,
              f"用例21：测试前提是取一条 ≤48pt 的禁止项，得到 {small_value}")
        small = tmp / "src-small"
        small.mkdir()
        (small / "Spacing.m").write_text(
            f"// 故意用 {small_value:g}pt：它同时是某条关系的设备推导值，也是常见设计常量\n"
            f"[[self knob] constraintEqualToConstant:{small_value:g}];\n"
            "[[self view] widthAnchor] multiplier:0.5;\n")
        proc, data = run_check(tmp, tmp / "plan.json", small, output_name="small.json")
        check(not [v for v in (data or {}).get("violations", [])
                   if v.get("literal") == small_value],
              f"用例21：{small_value:g}pt 与设计常量无法区分，不应计入违规")
        check(any(a["literal"] == small_value
                  for a in (data or {}).get("ambiguousLiterals", [])),
              f"用例21：{small_value:g}pt 应出现在 ambiguousLiterals 里待人工判断")

        # 用例 22：designConstants / --allow-values 是可复核的豁免
        allow_dir = tmp / "src-allow"
        allow_dir.mkdir()
        (allow_dir / "Allowed.m").write_text(
            f"[[self view] widthAnchor] constant:{big_value:g};\n"
            "[[self view] widthAnchor] multiplier:0.5;\n")
        proc, data = run_check(tmp, tmp / "plan.json", allow_dir, output_name="allow-1.json")
        check(any(v.get("literal") == big_value for v in (data or {}).get("violations", [])),
              f"用例22：未声明豁免时 {big_value:g} 应被记为违规（阳性前提）")

        allow_plan = json.loads((tmp / "plan.json").read_text())
        allow_plan["layoutProportions"]["designConstants"] = [big_value]
        allow_path = write_json(tmp / "plan-allow.json", allow_plan)
        proc, data = run_check(tmp, allow_path, allow_dir, output_name="allow-2.json")
        check(proc.returncode == 0,
              f"用例22：声明 designConstants 后应放行，退出码 {proc.returncode}")
        check(data and data["allowValues"] == [big_value],
              f"用例22：豁免值必须原样记入结果供复核，得到 {data and data['allowValues']}")

        # 用例 23：designConstants 只能是数字数组
        bad_plan = json.loads((tmp / "plan.json").read_text())
        bad_plan["layoutProportions"]["designConstants"] = ["standard 16pt margin"]
        bad_path = write_json(tmp / "plan-bad.json", bad_plan)
        proc, data = run_check(tmp, bad_path, allow_dir, output_name="allow-3.json")
        check(proc.returncode != 0 and any(
            v["kind"] == "bad-design-constants" for v in (data or {}).get("violations", [])),
              "用例23：designConstants 放字符串必须被拒（避免把说明文字当豁免）")

        # ------------------------------------------------ 计划自身的形状（硬伤层）
        # 计划是 Agent 写的，类别写错、贴边关系带上比例系数，都是回不去的硬伤，
        # 必须在源码之前拦住。每一类都要有「必须挂」。
        def plan_with(mutate, name):
            payload = json.loads((tmp / "plan.json").read_text())
            mutate(payload["layoutProportions"])
            return write_json(tmp / f"{name}.json", payload)

        def add_relation(props_json, region_name, relation):
            for region in props_json["regions"]:
                if region["region"] == region_name:
                    region["relations"].append(relation)
                    return
            raise AssertionError(f"计划里没有区域 {region_name}")

        def find_relation(props_json, relation_id):
            for region in props_json["regions"]:
                for rel in region["relations"]:
                    if rel["id"] == relation_id:
                        return rel
            raise AssertionError(f"计划里没有关系 {relation_id}")

        shape_cases = [
            ("unknown-relation-kind", "用例24a：非法 kind 必须被指出",
             lambda p: add_relation(p, "Card",
                                    {"id": "bad.kind", "kind": "absolute", "axis": "x",
                                     "of": "Screen", "ratio": 0.5})),
            ("intrinsic-missing-why", "用例24b：intrinsic 缺 why 必须被指出",
             lambda p: add_relation(p, "Label",
                                    {"id": "bad.why", "kind": "intrinsic", "axis": "width",
                                     "of": "Card"})),
            ("pinned-with-ratio", "用例24c：贴边关系带比例系数必须被指出",
             lambda p: find_relation(p, "Field.x").update({"ratio": 0.5})),
            ("fixed-missing-value", "用例24d：fixed 缺 value 必须被指出",
             lambda p: find_relation(p, "Icon.width").pop("value")),
            ("fixed-with-ratio", "用例24e：fixed 带比例系数必须被指出",
             lambda p: find_relation(p, "Icon.width").update({"ratio": 0.5})),
            ("fixed-missing-why", "用例24e2：fixed 缺 why 必须被指出",
             lambda p: find_relation(p, "Icon.width").pop("why")),
            ("proportional-missing-basis", "用例24f：比例关系缺基准必须被指出",
             lambda p: find_relation(p, "Card.y").pop("of")),
            ("centered-with-ratio", "用例24g：居中关系带比例系数必须被指出",
             lambda p: find_relation(p, "CardTitle.x").update({"multiplier": 0.5})),
            ("basis-mismatch", "用例24h：区域基准与父视图对不上必须被指出",
             lambda p: next(r for r in p["regions"]
                            if r["region"] == "Icon").update({"basis": "viewport"})),
            ("basis-mismatch", "用例24i：基准是父视图却写 of=root 必须被指出",
             lambda p: find_relation(p, "Icon.x").update({"of": "root"})),
            ("forbidden-targets-non-proportional",
             "用例24j：禁止清单指向 pinned 关系必须被指出",
             lambda p: p["forbiddenLiterals"].append(
                 {"relation": "Field.leading", "deviceDerivedPt": 23.0,
                  "ratioInstead": 0.063712})),
            ("forbidden-missing-ratio", "用例24k：禁止项缺 ratioInstead 必须被指出",
             lambda p: p["forbiddenLiterals"].append(
                 {"relation": "Card.top", "deviceDerivedPt": 120.0})),
            ("forbidden-unknown-anchor", "用例24l：禁止项锚点不认识必须被指出",
             lambda p: p["forbiddenLiterals"].append(
                 {"relation": "Card.left", "deviceDerivedPt": 16.0, "ratioInstead": 0.04})),
        ]
        for kind, message, mutate in shape_cases:
            path = plan_with(mutate, f"shape-{kind}-{message[-4:]}")
            proc, data = run_check(tmp, path, source_dir,
                                   output_name=f"shape-{abs(hash(message)) % 9999}.json")
            found = {v["kind"] for v in (data or {}).get("violations", [])}
            check(proc.returncode != 0 and kind in found,
                  f"{message}，得到 {sorted(found)}")

        # 用例 25：计划里没有 layoutProportions 必须被指出
        empty_path = write_json(tmp / "plan-empty.json", {"schemaVersion": 1})
        proc, data = run_check(tmp, empty_path, source_dir, output_name="empty.json")
        check(proc.returncode == 1 and any(
            v["kind"] == "missing-layout-proportions"
            for v in (data or {}).get("violations", [])),
              "用例25：计划缺 layoutProportions 必须被指出")

        # 用例 26：校验器自己对「接近原点的绝对值」也要防一手。
        # 计划侧已经过滤，但如果计划是手写/旧版的，校验器不能因此把每个 0 都报成违规。
        raw_plan = json.loads((tmp / "plan.json").read_text())
        raw_plan["layoutProportions"]["forbiddenLiterals"].append(
            {"relation": "ghost.centerX", "deviceDerivedPt": 0.0,
             "why": "手工塞进来的原点值", "ratioInstead": 0.5})
        raw_path = write_json(tmp / "plan-rawzero.json", raw_plan)
        zero_dir = tmp / "src-zero"
        zero_dir.mkdir()
        (zero_dir / "Zeros.m").write_text(
            "[[self view] widthAnchor] multiplier:0.5;\n"
            "view.frame = CGRectMake(0, 0, 0, 0);\n"
            "self.alpha = 0;\n")
        proc, data = run_check(tmp, raw_path, zero_dir, output_name="zero.json")
        check(proc.returncode == 0,
              f"用例26：计划里带 0 值禁止项时不应把每个 0 都报成违规，得到退出码 "
              f"{proc.returncode}：{data and data.get('violations')}")
        check(data and data["ignoredForbiddenCount"] == 1,
              "用例26：接近原点的禁止项应被记入 ignoredForbiddenCount 并给出告警")
        check(data and any("接近原点" in w for w in data["warnings"]),
              "用例26：忽略原点值必须留下告警，不能静默")
        # 光看退出码不够：0 会被「小数值待判」兜住，所以还要断言它连待判清单都不进。
        # 否则每个 0 都会以 ambiguousLiteral 的形式堆进报告，噪音照样成立。
        check(data and not [a for a in data["ambiguousLiterals"]
                            if a["relation"] == "ghost.centerX" or a["literal"] == 0],
              f"用例26：0 值禁止项不应产生待判噪音，得到 "
              f"{data and [(a['literal'], a['relation']) for a in data['ambiguousLiterals'][:3]]}")

        # 用例 26.5：**闭合契约在源码侧的判据**。
        # 旧契约改成新契约后最大的漏洞是「计划说 intrinsic、代码写死宽高」这一条在源码侧
        # 完全没有判据 —— 声明只活在计划里，实现层没人查。这里逐个把四类漏洞钉死，
        # 同时要求「正确写法一个都不许误报」（>= 边界、比例约束、优先级原语都要放行）。
        closure_root = tmp / "closure"
        closure_root.mkdir()

        def closure_case(name, relations, source):
            d = closure_root / name
            d.mkdir()
            payload = {"layoutProportions": {
                "model": "closure-declared-parent-relative-position",
                "regions": [{"region": "card", "index": 1, "parentIndex": 0,
                             "parent": "page", "basis": "parent",
                             "relations": relations}]}}
            plan_path = write_json(d / "plan.json", payload)
            (d / "Card.m").write_text(source)
            proc, data = run_check(d, plan_path, d, output_name=f"{name}.json")
            return proc, data, {v["kind"] for v in (data or {}).get("violations", [])}

        # 26.5a：声明 intrinsic，源码却写 == 常量 —— 这是旧契约的直接残留，必须违规。
        proc, data, found = closure_case(
            "intrinsic-constant",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "intrinsic", "minimum": 68.0, "why": "含文本，随动态字体增高"}],
            "[_card.heightAnchor constraintEqualToConstant:68];\n")
        check(proc.returncode == 1 and "intrinsic-axis-pinned-to-constant" in found,
              f"用例26.5a：计划声明 intrinsic、源码写死高度必须被判违规，得到 {sorted(found)}")

        # 26.5b：`>=` 是 bounded 的正确写法，绝不能和 == 一起被误报。
        proc, data, found = closure_case(
            "bounded-ok",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "bounded", "min": 44.0, "why": "触控下限"}],
            "[_card.heightAnchor constraintGreaterThanOrEqualToConstant:44];\n")
        check(proc.returncode == 0,
              f"用例26.5b：bounded 用 >= 表达是正确写法，不得误报，得到退出码 "
              f"{proc.returncode}：{data and data.get('violations')}")

        # 26.5c：声明 bounded 却整份源码一个边界原语都没有 —— 边界根本没实现。
        proc, data, found = closure_case(
            "bounded-missing",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "bounded", "min": 44.0, "why": "触控下限"}],
            "[_card.heightAnchor constraintEqualToConstant:44];\n")
        check("bounded-axis-missing-limit" in found,
              f"用例26.5c：声明 bounded 却没有任何 >=/<= 原语必须被指出，得到 {sorted(found)}")

        # 26.5d：声明 aspect-ratio 却没有任何比例约束原语。
        proc, data, found = closure_case(
            "aspect-missing",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "aspect-ratio", "ratio": 1.7778}],
            "card.frame = CGRectMake(0, 0, 393, 221);\n")
        check("aspect-ratio-idiom-missing" in found,
              f"用例26.5d：声明 aspect-ratio 却没有比例约束必须被指出，得到 {sorted(found)}")

        # 26.5e：注释里的 `constraintEqualToConstant` 是在解释，不许当违规。
        proc, data, found = closure_case(
            "intrinsic-comment",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "intrinsic", "why": "含文本"}],
            "// 以前是 [_card.heightAnchor constraintEqualToConstant:68]\n"
            "[_card.heightAnchor constraintGreaterThanOrEqualToConstant:68];\n")
        check("intrinsic-axis-pinned-to-constant" not in found,
              f"用例26.5e：注释里的等值约束不得误报，得到 {sorted(found)}")

        # 26.5f：区域名在源码里找不到时不得静默 —— 那意味着「声明」与「实现」对不上。
        proc, data, found = closure_case(
            "unlocatable",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "intrinsic", "why": "含文本"}],
            "self.view.backgroundColor = [UIColor whiteColor];\n")
        check(proc.returncode == 0 and any("区域名" in w for w in (data or {}).get("warnings", [])),
              "用例26.5f：计划区域名在源码里找不到必须留告警，不能静默通过")

        # 26.5g–26.5j：**「定位不到」与「没实现」是两件事**，不能混成一条判据。
        #
        # 前一版的 §2/§3 拿「这一行是否**同时**提到区域名和原语」直接当判据，于是
        # 「区域名没命中」被读成「这个区域没有边界原语」：源码按习惯写成
        # `offersContainer.heightAnchor constraintGreaterThanOrEqualToConstant:44`
        # （**正确实现**）而计划 region 叫 `offers` 时，会被判 bounded-axis-missing-limit、
        # 退出码 1 —— 闸门拦下了正确代码，而同一次运行的告警里还写着「区域名一个都没出现」，
        # 自相矛盾。对外的代价是「按本仓契约写对了却过不了门」。
        #
        # 所以这四条一起钉死：**命名不一致 ⇒ 不判违规、但必须留告警并写明没判**；
        # **定位到了却没有 ⇒ 照旧判违规**（否则「别处一条 >= 就能糊过去」这个洞又开了）。

        # 26.5g：本区域名在源码里定位不到（边界被写在了别的区域）—— 这是命名不一致，
        # 不是「没实现」，不得判硬违规。
        proc, data, found = closure_case(
            "unlocatable-bounded",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "bounded", "min": 44.0, "why": "触控下限"}],
            "[footer.heightAnchor constraintGreaterThanOrEqualToConstant:44];\n")
        check(proc.returncode == 0 and "bounded-axis-missing-limit" not in found,
              f"用例26.5g：区域名定位不到时不得读成「没实现边界」，得到退出码 "
              f"{proc.returncode}：{sorted(found)}")
        check(any("区域名" in w and "没有判定" in w for w in (data or {}).get("warnings", [])),
              "用例26.5g：定位不到必须逐条点名并写明这几条没判，不能静默跳过")

        # 26.5h：区域**定位到了**（`card` 出现在别处），但边界原语在别的区域 ——
        # 这才是真的「用别处一条 >= 伪装」，必须判违规。
        # 注意 26.5c 证明不了这一条：它整份源码一个 >= 都没有，因此同时会命中 §1，
        # 从结果集里读不出 §2 到底在不在判。（本用例的源码里没有 == 常量约束，
        # 所以 found 只会是 §2 的那一条 —— 隔离是干净的。）
        proc, data, found = closure_case(
            "cross-region-bounded",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "bounded", "min": 44.0, "why": "触控下限"}],
            "card.backgroundColor = [UIColor whiteColor];\n"
            "[footer.heightAnchor constraintGreaterThanOrEqualToConstant:44];\n")
        check("bounded-axis-missing-limit" in found,
              f"用例26.5h：边界原语写在别的区域必须判违规，得到 {sorted(found)}")

        # 26.5i：aspect-ratio 在**本区域**的正确写法。既有用例只测过「缺」（26.5d），
        # 没测过「写对了不得误报」—— 少了这一半，误报就会一路绿着放出去。
        proc, data, found = closure_case(
            "aspect-ok",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "aspect-ratio", "ratio": 1.7778}],
            "card.heightAnchor constraintEqualToAnchor:card.widthAnchor multiplier:0.5625;\n")
        check(proc.returncode == 0 and "aspect-ratio-idiom-missing" not in found,
              f"用例26.5i：本区域有比例约束是正确写法，不得报缺失，得到退出码 "
              f"{proc.returncode}：{sorted(found)}")

        # 26.5j：比例原语写在别的区域，本区域只有一句无关代码 —— 必须判违规。
        proc, data, found = closure_case(
            "cross-region-aspect",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "aspect-ratio", "ratio": 1.7778}],
            "card.backgroundColor = [UIColor whiteColor];\n"
            "icon.widthAnchor constraintEqualToAnchor:icon.heightAnchor multiplier:1;\n")
        check("aspect-ratio-idiom-missing" in found,
              f"用例26.5j：比例原语写在别的区域必须判违规，得到 {sorted(found)}")

        # 26.5k：aspect-ratio 的区域名定位不到 —— 与 26.5g 同款，不得判硬违规。
        # 这条是 §3 定位守卫的**唯一**红点：少了它，「定位不到 ⇒ 没实现」的回归
        # 在 aspect-ratio 一侧没有任何用例会变红（26.5i/26.5j 的区域都定位得到）。
        proc, data, found = closure_case(
            "unlocatable-aspect",
            [{"id": "card.height", "axis": "height", "of": "page", "ofIndex": 0,
              "kind": "aspect-ratio", "ratio": 1.7778}],
            "icon.widthAnchor constraintEqualToAnchor:icon.heightAnchor multiplier:1;\n")
        check(proc.returncode == 0 and "aspect-ratio-idiom-missing" not in found,
              f"用例26.5k：区域名定位不到时不得读成「没实现比例」，得到退出码 "
              f"{proc.returncode}：{sorted(found)}")

        # ---------------------------------------------------------------- 退出码
        proc = run(CHECK_SCRIPT, "--plan", str(tmp / "nope.json"), "--source", str(source_dir))
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例27：计划文件缺失应干净退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        empty_src = tmp / "src-empty"
        empty_src.mkdir()
        proc = run(CHECK_SCRIPT, "--plan", str(tmp / "plan.json"), "--source", str(empty_src))
        check(proc.returncode == 2, f"用例27：源码目录为空应退出 2，得到 {proc.returncode}")

        proc = run(PLAN_SCRIPT, "--page-facts", str(tmp / "nope.json"))
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例27：事实表缺失应干净退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        empty_elements = write_json(tmp / "empty-facts.json",
                                    {"elements": [], "viewport": VIEWPORT})
        proc = run(PLAN_SCRIPT, "--page-facts", str(empty_elements))
        check(proc.returncode == 2, f"用例27：事实表无 elements 应退出 2，得到 {proc.returncode}")

        # 用例 28：判不出坐标空间时**拒绝继续**，绝不猜。
        # 猜错就会把 scale 乘两遍，正是这条红线要防的系统性偏移。
        broken = standard_facts()
        for item in broken["elements"]:
            item["rectInReference"] = {k: v / 2 for k, v in item["rectInReference"].items()}
        broken_path = write_json(tmp / "broken-facts.json", broken)
        proc = run(PLAN_SCRIPT, "--page-facts", str(broken_path), "--output",
                   str(tmp / "broken.json"))
        check(proc.returncode == 2 and "坐标空间" in proc.stderr,
              f"用例28：坐标空间判不出来时应退出 2 并说明，得到 {proc.returncode}："
              f"{proc.stderr[:200]}")
        check(not (tmp / "broken.json").is_file(),
              "用例28：判不出来时不得写出计划文件（避免下游把它当成有效证据）")

    for problem in problems:
        print(problem)
    if problems:
        print("布局约束契约未满足")
        return 1
    print("布局约束契约：坐标空间由证据判定、尺寸判 fixed/intrinsic、贴边判 pinned 不带系数、"
          "位置基准是直接父视图、外框铺满、文字块 intrinsic 有 why、孤立大偏移降级并提示、"
          "禁止清单只收 proportional、合规源码通过、把比例换成设备推导值被精确拦下、"
          "注释/颜色/百分比不误报、小数值待判、豁免可复核、计划硬伤先于源码拦住、"
          "源码侧闭合契约逐类核对（intrinsic 写死宽高/bounded 无边界/aspect-ratio 无比例/"
          "定位不到只告警不误判）、"
          "fixed 必须带 why 且生成端只给候选、用法错误干净退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
