# OCR 单字审核入口

双击 start_ocr_review.bat，选择 artifacts/ocr_user_results_v1/results.json。

1. 下拉框切换图片，左侧选择单字候选。
2. 右侧显示该字附近原图，橙框为建议裁切范围。可拖动重画矩形，检查笔画完整且不包含邻字。
3. 修正顶部字符，点击“确认当前字和框”。未点击确认的候选不会进入工程；已确认的字可撤销或重新确认。
4. 点击“保存字体工程”，选择目录并输入字体名称。多张图片中确认的字归入一个工程，保留原图和审核记录。

保存生成 font_project.json、各页裁切工程及 ocr_review.json。可用下列命令生成一份候选字体：

```powershell
python font_project.py export "已保存工程/font_project.json" "一个尚不存在的导出目录"
```

候选字体随后可用原有 start_stroke_editor.bat 打开纠正。也可在 start_font_project.bat 中选择审核导出的各个 reviewed_XXX/page.json 合并并进入纠正器。

限制：本入口读取原始 OCR 结果，尚不导入网页的文字修改 JSON，Session save/restore is now supported; save before closing.重复字符需要先撤销旧确认。当前图像显示局部上下文，拖框超出原图会拒绝确认。只支持 V5 可导出的单个 BMP 字符。不会自动把分数较高的字标成已确认。

测试：审核后的两张合成图片可保存、加载并合并导出“一、十”；重复字符、多字符绑定及越界裁切被拒绝且不损坏已确认记录。用户 19 张原图全部通过哈希及读取校验，未替用户确认任何字符。桌面交互尚未实测，真实字形效果和奎享兼容性仍需审核后验证。


## Session persistence update

Save Review Progress stores confirmed characters and crop boxes in a JSON session. Open the same results.json and use Restore Review Progress to continue. Unconfirmed text/rectangle changes are not saved. Restore validates the exact results file hash and candidate provenance; invalid input does not replace current confirmations.

Generate and Correct Font saves a multi-image project, generates candidate.gfont, and opens the existing stroke editor. If generation fails, the saved project remains available. This does not imply driver verification.

Tests cover session roundtrip, wrong batch, duplicate entries, altered provenance and negative indices. Desktop button interactions have not been manually verified.
