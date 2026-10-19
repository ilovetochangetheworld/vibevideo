# Canvas 引擎与工程

## 环境与来源

自带引擎来自 HeyChengC/vibe-knowledge-film（提交 `62d51508aad00003dc6209afa80c4b5dc540de59`）：https://github.com/HeyChengC/vibe-knowledge-film 。仅保留核心渲染代码与原许可 `assets/engine/LICENSE`，没有复制原片示例或第三方配乐；本 skill 的配音与混音脚本独立实现，默认不导入上游自动配乐。

需要 Python、ffmpeg/ffprobe、Google Chrome。Python 依赖在 `assets/requirements.txt`，用工作区虚拟环境安装。字体在首次渲染前运行 `assets/engine/get_fonts.py` 下载，已存在时复用；保留同目录 OFL 字体许可。导出的 skill 包不含字体缓存，换机器重新运行下载脚本。

工程包含 `index.html`、`film.js`、`storyboard.md`、`facts.md`、`cues.json`、`mix.json` 和 audio/renders/review。新建脚本只创建空骨架，画面按本片分镜新写。`render.py` 把此 skill 的 `assets/engine` 挂载为页面 `/engine/`，工程无需硬编码引擎安装路径。

## API 核心

每一帧由时间 `t` 决定，允许乱序 `seek(t)`；随机使用 `VK.rng(seed)`，不使用跨帧累计位置或 `Math.random()`。模拟预先算成时间表，再按 t 读取。

```js
(function () {
  const {ss,fade,lerp}=VK, K=VKit;
  const SUBS=[{a:.25,b:3.45,zh:'你停住了，隔壁却往前走。'}];
  VK.film({dur:36,theme:'night',bloom:.23,grain:.025,
    draw(fr,t){
      const a=fade(t,0,7,.4,.4);
      fr.g({a},()=>{
        // 本片自己的收银台、人物和动作。
        fr.text('你的队',450,190,{font:'sansm',size:34,color:'#F8D893'});
      });
      K.subs(fr,t,SUBS,'night');
    }
  });
})();
```

时间：`ss(t,a,b)` 平滑从0到1，`fade(t,a,b,fin,fout)` 进出包络，`lerp(a,b,k)` 插值。场景交叠慎用文字叠影，必要时先退后进。

图形：`fr.rect(x,y,w,h,{fill,color,r,w,a})`、`circle(cx,cy,r,opts)`、`ellipse`、`line`、`poly(points,opts)`、`path(svg,opts)`。文字 `fr.text(str,x,y,{font,size,color,align,track,a})` 默认中心对齐；`fr.measure` 可量字幕宽度。组变换 `fr.g({a,at:[x,y],s,rot},fn)`。

实心插画：`fr.look.under=(ctx,t)=>{...}` 使用原生 Canvas，避免大块实体参与辉光。叠多个场景时保留上一层 under 回调，避免互相覆盖。`fr.x` 是上层 Canvas context。中文字体 `serifr/serifm`、`sansr/sansm`，数字可用 `mono`；实体颜色与低辉光配合。

`K.subs` 的中文字数要能一行读完；C 字幕约 y=939，字号可通过 `K.SUB.night.size` 调整。英文可省略。不要添加无意义的实现术语或水印。

## 渲染与检查

```sh
python SKILL_ROOT/assets/engine/render.py PROJECT --serve
python SKILL_ROOT/assets/engine/render.py PROJECT --sheet 12
python SKILL_ROOT/assets/engine/render.py PROJECT --stills 3.1 18.8
python SKILL_ROOT/assets/engine/render.py PROJECT --motion 29.2 29.9 8
python SKILL_ROOT/assets/engine/render.py PROJECT --det
python SKILL_ROOT/assets/engine/render.py PROJECT --jobs 4
```

渲染得到 `renders/raw.mp4`，它是混音时优先使用的无声画面。样片可用 `--clip 0 30 head`。先抽帧，再渲全片，不反复为了小改动重渲整片；更换音乐只重新混音。

浏览器在字体初始化时卡住：确认字体齐全、Chrome 能启动、控制台是否有资源错误，最多重试失败片段一次。不要无休止开启更多浏览器。并行渲染失败时收集所有子进程退出状态，不遗留后台渲染。

`render.py --serve` 是本地预览，不包含发布动作。若端口已被本项目占用，复用现有服务；不要因为端口冲突关闭无关进程。最终交付用 MP4，不能用浏览器预览代替成片核验。

本 skill 对原渲染脚本做了局部修正：本地资源请求队列增至128，字体/页面初始化失败及时抛出诊断，并等待全部并行子进程退出，避免部分失败后遗留渲染。已用新建工程真实输出静帧和一秒H.264样片。
