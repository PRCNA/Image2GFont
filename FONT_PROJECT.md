# 多图片字体工程

双击 `start_font_project.bat`，选择已用 `start_page_import.bat` 裁切并绑定字符的 `page.json` 文件，输入字体名称和存放目录。程序复制原图与裁切信息，生成一份合并的 `generated/candidate.gfont`，随后打开已有轨迹纠正器。

每个字体工程包含多张图片，每张图片包含多个已绑定字符的矩形区域。原图复制为只读文件并校验 SHA256。不同页面的同一字符暂不允许同时加入：会报错而非覆盖，也尚未实现同字多字形选择。

当前输入是人工裁切工程，不是 OCR results.json 或修改记录。OCR 单字框尚未经过完整笔画边界审核，不能把它们直接批量转成已确认裁切框。此次没有替用户确认任何 OCR 字符。

命令行也可保存、重新打开并追加其他目录中的页面：

```powershell
python font_project.py create artifacts/my_font --name MyFont
python font_project.py add artifacts/my_font/font_project.json path/to/page.json
python font_project.py add artifacts/my_font/font_project.json another/path/page.json
python font_project.py export artifacts/my_font/font_project.json artifacts/my_export
```

工程及导出目录必须是新目录。添加失败时此前成功加入的页面会保留，便于修正后继续；生成失败时可能保留中间页面输出，应换新目录重试。导出的每页报告保留原图哈希、裁切矩形和字符绑定；最终 report.json 明确标记 candidate 和 driver_verified=false。原有独立页面工程不被改写。

验证：两张合成笔画图片合并为含“一、十”的一份 GFont，并重新读取检查字符集合、轨迹非空和字体名称；重复字符、原图篡改、目录越界和空工程拒绝测试通过。真实 OCR 图片的自动合并及奎享驱动实测未完成。启动向导仅作语法检查，尚未通过桌面交互实测。
