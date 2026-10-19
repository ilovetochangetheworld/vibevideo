---
name: vibe-knowledge-video
description: 制作或修改 Vibe 知识大赏风格的代码科普视频，完成事实核查、文案分镜、Canvas 动画、可选云扬解说、单一 BGM 混音和 MP4 交付。适用于知识机制的可视化讲解；不负责短剧、人物口型或平台发布。
---

# Vibe 知识大赏

把知识中的因果过程演出来，交付可修改工程与 MP4。用户提供的选题、参考片、配乐和反馈优先；已有项目先读其分镜和时间线，避免推倒重做。

## 任务入口

- **新片**：读 [讲解与画面](references/story-and-visuals.md)，一起设计文案和分镜。没有指定长度时，先做约 30 秒可审阅样片，长片后续扩展。
- **改配音或 BGM**：先读 [音频制作](references/audio.md)，列出实际音轨来源。画面不变时复用已渲染视频，只重新混音。
- **实现与渲染**：读 [引擎操作](references/engine.md)。本 skill 自带 Canvas 引擎，不依赖另一份 skill 或原项目目录。

## 核心约定

1. 文案里的物体和动作，在画面中认得出、确实发生。先展示可理解的例子，再给术语和结论；一镜主要改变一件事。不要让发光点、泛用图表或文字卡片代替全部讲解。
2. 年份、数字、实验和因果主张查来源；假设、手工情境、模拟与实测分清。统计结论写明条件，不把“至少另一队更快”讲成“你最慢”。
3. 先写 `storyboard.md` 和 `facts.md`，再写画面。用户已授权直接试做时，做完可审阅样片，不额外设置逐步确认。
4. 未指定时采用 16:9、1920×1080、30fps、深色背景与克制辉光；横竖屏和外观按用户意图调整。画面默认留出下方约 20% 给字幕。不要为强塞文案缩小字号。
5. 新建项目默认可用云扬男声 `zh-CN-YunyangNeural`；无旁白也是有效选择。选定后先合成逐句音频，按真实时长安排时间线，不能剪掉尾字。
6. **背景只使用一个明确指定的 BGM。默认保持固定增益，不因人声出现突然压低或恢复。** 通过较低的音乐电平、清楚的人声和必要的均衡取得平衡。仅在用户要求时启用人声避让。
7. 引擎原配的 `score.wav` 可能包含持续底音、气流、和弦，不是纯音效。已有视频自带的声音也不能直接与新 BGM 一起保留。明确映射视频轨与新混音轨，只有确认独立的事件音才可列入 `effects`。
8. 片头与片尾可淡入淡出；章节音乐变化跟随乐句或用户要求，不能让每句解说都改变 BGM 音量。不把第三方歌曲或用户音频打包进本 skill。

## 可执行流程

将 `SKILL_ROOT` 解析为本文件所在的绝对目录，命令使用该绝对路径。工程建在用户工作区。

```sh
python SKILL_ROOT/scripts/new_project.py PROJECT --title '片名' --duration 36
python SKILL_ROOT/scripts/tts.py PROJECT/cues.json --out PROJECT/audio/voice --duration 36
python SKILL_ROOT/assets/engine/render.py PROJECT --sheet 12
python SKILL_ROOT/assets/engine/render.py PROJECT --det
python SKILL_ROOT/assets/engine/render.py PROJECT --jobs 4
python SKILL_ROOT/scripts/mix_audio.py PROJECT/mix.json
```

`cues.json` 与 `mix.json` 格式见 [音频制作](references/audio.md)。TTS 使用在线 Edge 服务；语速、音调可调，不声称支持 Azure 的任意情绪 style。字幕与实际发音对齐；英文字幕可选，不能挤占主体。

## 交付前检查

- 查看整片拼图、关键帧原尺寸与实际转场；发现的问题修改后重截同一时刻。确定性检查保证乱序 seek 相同。
- 用耳机试听最终混音的开场、有人声段、片名增强处和结尾；检查是否叠了第二首音乐、旧底音、音量抽吸、截字或遮蔽。工具无法播放或未实际听过时如实说明，测响度不能代替听感。
- 用 `ffprobe` 核对时长、帧数、尺寸与音视频轨；解码最终 MP4。混音脚本会保存来源、固定增益、单 BGM 数量和响度报告。
- 明确交付最终 MP4、源码、文案分镜、事实出处和配乐来源；A/B 对比保持同一画面、同一段人声及相近整体响度。视频保持当前聊天的约定语言。
- 默认只在本地生成。平台上传、发布属于另一个任务。
