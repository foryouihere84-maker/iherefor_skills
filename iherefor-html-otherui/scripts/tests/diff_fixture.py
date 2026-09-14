#!/usr/bin/env python3
"""比较器三分法（结构 / 纹理 / 填充）的合成真值样本生成器。

**为什么需要合成样本。** ``compare_reference.py`` 的核心主张是「阈值只加在结构差异
与填充差异上，纹理差异（栅格化、抗锯齿）不参与放行判定」。这个主张没法用真实事故
样本验证 —— 真实样本只告诉你「这一张该 fail」，不告诉你「一张只有纹理差异的图不该
fail」。所以这里手工构造三类**只含单一差异成因**的图对，让比较器必须把它们分到三个
不同的桶里，且只有该 fail 的那几类真的 fail。

**样本怎么造。** 所有图走同一套 4 倍超采样渲染，保证边缘是抗锯齿软边而不是硬边
（硬边图会让所有差异都落在强边上，样本就没有区分力了）。

* ``geometry``：整屏内容平移 3px。参考图里有边的地方，实机图里那条边跑到了容差
  之外 —— 两张边缘图在该处必然只有一张亮，所以差异落在 ``structural``。
* ``fill``：把一张卡片的填充色改掉（245 → 210，delta 35），形状/位置/尺寸全不变。
  差异落在纯色平坦区，两张图都没有边 —— 落在 ``fill``。
* ``ink``：把文字颜色改亮（32 → 60）。笔画内部是平坦区，两张图都没边 —— 也落在
  ``fill``。文字颜色写错是**真缺陷**，必须能被抓到，所以它不属于纹理差异。
* ``texture``：同一套几何、同一套颜色，只把栅格化相位挪半个像素（0.5px）。平坦区
  完全同色，只有软边上的抗锯齿像素值不同；两张边缘图在同一位置都亮 —— 落在
  ``texture``，且必须判 pass。

**注意 ``texture`` 样本不是「改颜色」也不是「改字重」。** 改颜色是填充缺陷，改字重
是几何缺陷 —— 两者都该 fail。把这类样本标成 pass 会让回归测试奖励「把真缺陷放过」。
真正只该放过的，是几何与配色都一致、只有栅格化方式不同的那种差异。

用法：``python3 scripts/tests/diff_fixture.py [输出目录]`` 会把样本写盘便于人工翻看；
不传目录时只作为模块被测试导入。

依赖 Pillow（与比较器一致）。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# 画布取 300x600（按 scale 2 即 150x300pt），够小以便快速跑，够大以便网格区域划分有意义。
WIDTH = 300
HEIGHT = 600
SUPERSAMPLE = 4  # 4 倍超采样后降采样，得到抗锯齿软边

BACKGROUND = (255, 255, 255, 255)
INK = (32, 33, 36, 255)          # 正文文字色
INK_WRONG = (60, 64, 67, 255)    # 文字颜色写错：比 INK 亮，delta 28 > threshold
CARD = (245, 245, 245, 255)      # 卡片填充
CARD_WRONG = (210, 210, 210, 255)  # 卡片填充写错：delta 35 > threshold
CARD_BORDER = (224, 224, 224, 255)
ACCENT = (26, 115, 232, 255)
ACCENT_LABEL = (255, 255, 255, 255)
POSITIVE = (52, 168, 83, 255)

# 文字用细长条模拟：一屏里有标题、段落、按钮标签、页脚，
# 这样差异像素不会集中在一处，网格区域统计才有意义。
TITLE_BARS = [(24, 40, 180, 12)]
PARAGRAPH_BARS = [
    (40, 150, 210, 7),
    (40, 166, 190, 7),
    (40, 182, 150, 7),
    (40, 224, 200, 7),
    (40, 240, 120, 7),
]
LABEL_BARS = [(52, 430, 74, 9)]
FOOTER_BARS = [(96, 548, 108, 6)]


def _spec(**overrides):
    """一份渲染参数。默认值 = 基准图；改哪一项就是哪一类差异。"""
    spec = {
        'text_color': INK,
        'card_color': CARD,
        'offset': (0, 0),        # 整屏平移（像素），模拟几何错位
        'phase': 0.0,            # 栅格化相位（像素，只走子像素），模拟抗锯齿差异
    }
    spec.update(overrides)
    return spec


def _bar(draw, box, color):
    """画一根「文字条」（坐标已在超采样空间）。"""
    x, y, w, h = box
    draw.rectangle([x, y, x + w, y + h], fill=color)


def render(spec):
    """按 ``spec`` 渲染一张 RGBA 图。

    先在 ``SUPERSAMPLE`` 倍画布上画，再用 LANCZOS 降采样 —— 这样所有边缘都是
    抗锯齿软边，梯度分布与真实截图一致。
    """
    size = (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE)
    image = Image.new('RGBA', size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    scale = SUPERSAMPLE
    text_color = spec['text_color']

    def box(b):
        return [b[0] * scale, b[1] * scale, (b[0] + b[2]) * scale, (b[1] + b[3]) * scale]

    def bar(b):
        _bar(draw, [v * scale for v in b], text_color)

    # 顶部强调色标题栏
    draw.rectangle(box((0, 0, WIDTH, 96)), fill=ACCENT)
    for b in TITLE_BARS:
        _bar(draw, [v * scale for v in b], ACCENT_LABEL)

    # 卡片（形状与位置在填充样本里保持不变，只有填充色变）
    draw.rounded_rectangle(box((20, 120, 260, 268)),
                           radius=10 * scale, fill=spec['card_color'],
                           outline=CARD_BORDER, width=1 * scale)
    for b in PARAGRAPH_BARS[:3]:
        bar(b)

    # 卡片下方的一段独立文案
    for b in PARAGRAPH_BARS[3:]:
        bar(b)

    # 主按钮
    draw.rounded_rectangle(box((32, 410, 236, 460)),
                           radius=12 * scale, fill=POSITIVE)
    for b in LABEL_BARS:
        _bar(draw, [v * scale for v in b], ACCENT_LABEL)

    # 页脚
    for b in FOOTER_BARS:
        bar(b)

    image = image.resize((WIDTH, HEIGHT), Image.LANCZOS)

    dx, dy = spec['offset']
    phase = spec['phase']
    # 相位走超采样网格的整数格，保证「只挪子像素」而不是改变内容位置。
    shift_x = int(round(dx * scale + phase * scale))
    shift_y = int(round(dy * scale))
    if shift_x or shift_y:
        # 注意画布尺寸：这里已经降采样回 (WIDTH, HEIGHT)，不能再填超采样尺寸。
        shifted = Image.new('RGBA', (WIDTH, HEIGHT), BACKGROUND)
        shifted.paste(image, (shift_x, shift_y))
        image = shifted
    return image


def reference_image():
    return render(_spec())


def geometry_image(offset=(0, 3)):
    """几何差异：内容整体平移，形状与配色都不变。"""
    return render(_spec(offset=offset))


def fill_image(card_color=CARD_WRONG):
    """填充差异：只改卡片填充色，形状与位置不变。"""
    return render(_spec(card_color=card_color))


def ink_image(text_color=INK_WRONG):
    """填充差异（文字色）：笔画内部是平坦区，落在 fill 桶。"""
    return render(_spec(text_color=text_color))


def texture_image(phase=0.5):
    """纹理差异：几何与配色全同，只挪半个像素的栅格化相位。"""
    return render(_spec(phase=phase))


def cases():
    """返回 ``{名字: (reference, actual, 期望判定, 期望桶)}``。"""
    reference = reference_image()
    return {
        'geometry': (reference, geometry_image(), 'fail', 'structural'),
        'fill': (reference, fill_image(), 'fail', 'fill'),
        'ink': (reference, ink_image(), 'fail', 'fill'),
        'texture': (reference, texture_image(), 'pass', 'texture'),
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        for name, (_ref, _act, expected, bucket) in cases().items():
            print(f'  {name}: 期望判定 {expected}，差异应落在 {bucket} 桶')
        return 0
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, (ref, act, expected, bucket) in cases().items():
        ref.save(out / f'{name}-reference.png')
        act.save(out / f'{name}-actual.png')
        print(f'写入 {out}/{name}-{{reference,actual}}.png'
              f'（期望判定 {expected}，差异落在 {bucket}）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
