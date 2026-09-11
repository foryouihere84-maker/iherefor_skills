# evals/fixtures/assets

`resource-semantic-naming` 用例的工作区素材：三张模拟 Lanhu 导出的图片，让 Agent 有真实
文件可测（像素尺寸、sha256），而不是只能对文件名作断言。

| 文件 | 尺寸 | 用途（用例里告诉 Agent 的场景） |
| --- | --- | --- |
| `img_0.png` | 786×600 | 顶部主视觉拼图 |
| `img_1.png` | 66×66 | 右上角关闭图标 |
| `img_2.png` | 786×400 | 底部订阅卡片背景 |

尺寸刻意三者各不相同：整页统一按 2x/3x 假设会在 scale 推导上出错，而 skill 要求逐个由
「PNG 像素 ÷ HTML CSS 尺寸」推导。图为纯色加对角线，只为让文件真实可读，不含视觉信息。

重新生成（尺寸/配色改动时用）：

```python
from PIL import Image, ImageDraw
for name, size, color in [("img_0.png", (786, 600), (58, 92, 168)),
                          ("img_1.png", (66, 66), (32, 32, 32)),
                          ("img_2.png", (786, 400), (238, 240, 248))]:
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(255, 255, 255), width=2)
    draw.line([(0, 0), (size[0], size[1])], fill=(255, 255, 255), width=2)
    image.save(f"evals/fixtures/assets/{name}", optimize=True)
```
