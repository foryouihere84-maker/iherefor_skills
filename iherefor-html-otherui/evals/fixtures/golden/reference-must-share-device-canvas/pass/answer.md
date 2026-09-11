先把运行时读到的事实写进 runtime-device.json（402x874 点、scale 3），再用它渲染基准：

    node scripts/render_reference.mjs --input <page>/source --output <page>/reference --viewport-from <run>/runtime-device.json

这样得到的 reference.png 是 1206x2622，与设备截图同源：像素尺寸严格相等、坐标系一致，
且不允许用缩放派生图去凑尺寸。
