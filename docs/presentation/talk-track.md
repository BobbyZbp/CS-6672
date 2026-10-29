# GhostMap: the talk, slide by slide (English · 中文)

About twelve minutes with every slide, then questions (an eight-minute cut skips slides 7, 11–13, 15–16, 18, 21–22): what was done and why (the three directions tried first), the pipeline step by
step, what is new and what is still open; two backup slides for questions. The slides are
`artifacts/presentation/ghostmap-talk.pptx`, built by `node pipeline/ghostmap/package/talk_deck.js` from the same data
the demo page reads (`dist/assets/timemachine/scene.json` and the reports beside it) and the method's own constants
in `anchor/georegister.py` and `anchor/locate.py`; each slide's section below is also that slide's speaker notes. The
live demo is `http://127.0.0.1:8080/timemachine.html`.

全部讲完约十二分钟，之后答问（八分钟版跳过第 7、11–13、15–16、18、21–22 页）：先讲做了什么、为什么（最先试过的三个方向），再逐步讲流程，最后讲什么是新的、什么还没做完；另有两页备用。
幻灯片是 `artifacts/presentation/ghostmap-talk.pptx`，由 `node pipeline/ghostmap/package/talk_deck.js` 从演示页面用的同一份
数据和 `anchor/georegister.py`、`anchor/locate.py` 里的常量生成；下面每一页的内容同时就是那一页的演讲者备注。现场演示页面是
`http://127.0.0.1:8080/timemachine.html`。

**The story in one sentence / 一句话讲完：** COLMAP's frame is arbitrary; we fix its seven free numbers against the
public lidar, without GPS, and make it say when it can't. / COLMAP 的坐标系是随便定的；我们不用 GPS，用公开的 lidar
把那七个没定的数定下来，定不了的时候让它自己说清楚。

## Before the talk / 上台前（10 分钟）

1. Start the demo server / 启动演示服务器:
   `cd ~/CS6672 && PYTHONPATH=pipeline .venv/bin/python -m ghostmap.web.demo_server` (port 8080; it warms up for
   about 25 s, then places a photograph in 1–2 s / 端口 8080，预热约 25 秒，之后每张照片 1–2 秒). Without it, the
   offline bundle `artifacts/presentation/ghostmap-demo-*.zip` (`python3 serve.py`) shows everything except live
   placement / 没有它的话，离线包能演示除了现场放照片以外的一切.
2. Open the deck in PowerPoint (presenter view shows these notes) and one browser tab with hardware acceleration on
   (`chrome://gpu`: WebGL 2 hardware accelerated): `http://127.0.0.1:8080/timemachine.html#photo`. /
   用 PowerPoint 打开幻灯片（演讲者视图里能看到备注），浏览器开一个标签页并确认硬件加速。
3. Warm the demo: open chapters 4 and 5 once (the splats load), drop one photograph on chapter 11 (it should say
   "in 1–2 s"), go back to chapter 11's start. / 预热：点一下第 4、5 章让 splat 加载好，在第 11 章拖一张照片进去（应显示
   1–2 秒），再回到第 11 章开头。
4. Your own photographs: three to five phone photographs of McGraw Tower from Ho Plaza or Libe Slope, location on,
   on the desktop ready to drag. Photographs from the Arts Quad side are refused (the internet never photographed it
   from there). / 你自己的照片：在 Ho Plaza 或 Libe Slope 用手机拍 3–5 张钟楼，开定位，放在桌面上随时拖。从 Arts Quad
   那一侧拍的会被拒绝。
5. Fallbacks: the tour video `artifacts/presentation/ghostmap-tour.webm`; every slide has its own still. On a
   1280×720 projector the page shows its chapters as numbers; the arrow keys step through them. / 备用：tour 视频；
   每页幻灯片都有截图。1280×720 投影仪上页面章节只显示数字，方向键照常翻。

## Slide by slide / 逐页讲稿

### Slide 1 · GhostMap (0:00–0:15)

**Show / 操作:** the title slide. / 标题页。

**Say:** Hi, I'm [your name]. This is GhostMap, my COLMAP hacker project. In one sentence: COLMAP gives you a 3D
model in a frame that means nothing. I put it into the real world without GPS, and I make it say when it can't.

**讲:** 大家好，我是［名字］。这是 GhostMap，我的 COLMAP hacker project。一句话：COLMAP 给你的 3D 模型在一个没有意义的
坐标系里；我不用 GPS 把它放进真实世界，而且放不了的时候让它自己说出来。

### Slide 2 · What GhostMap does (0:15–0:55)

**Show / 操作:** the two pictures on the left, top to bottom, then the three points. / 左边两张图从上到下，再讲右边三点。

**Say:** What GhostMap does, in one picture. Top: what COLMAP gives you from 88 internet photographs of McGraw Tower,
a model in a frame of its own: no metres, no north, no up, no place on Earth. Bottom: the same model placed in metres
on the campus, with no GPS, from public lidar and map footprints, and with a certificate that says which cue fixed
which number. Three things it does. It places a reconstruction in the real world without GPS. It refuses when the
geometry can't: every one of the campus fragments was refused with a reason, and the three that GPS could check were
up to 845 metres off. And it places a new photograph in about two seconds, within a median 0.7 metres, and paints it
back onto the lidar city from where it was taken. How it got here, how it works, and what is still open: that is the
talk.

**讲:** 一张图讲清 GhostMap 做什么。上面：COLMAP 从 88 张钟楼的网络照片给你的东西，一个在自己坐标系里的模型，没有米、没有北、
没有上、不知道在地球上哪里。下面：同一个模型，不用 GPS，靠公开的 lidar 和地图轮廓放进了校园，以米为单位，还带一张证书，写明
哪条线索定了哪个数。它做三件事：不用 GPS 把重建放进真实世界；几何定不住的时候拒绝——校园的每个片段都被有理由地拒绝了，其中
三个能用 GPS 核对的偏了最多 845 米；新照片大约两秒放好，中位误差 0.7 米，再投影回 lidar 城市。它是怎么来的、怎么做的、还有
什么没做完，就是这次要讲的。

**Transition / 过渡:** It didn't start here. / 一开始不是这个。

### Slide 3 · Three things we tried first (0:55–1:45)

**Show / 操作:** the three columns, left to right. / 三列，从左到右。

**Say:** Before this project there were three. The first is where the name comes from: Boardman Hall, Cornell's old
law building, which stood where Olin Library is now; twenty public-domain postcards of it survive, so: bring it back.
I registered the old photographs through the buildings that still stand, and every view of Boardman came out as a
mirror image. All the modern photographs of the tower are taken from the south-west, the postcards from the
north-east, and the tower's four faces look alike; the poses fit to a few pixels, from the wrong side. The record
can't say where the building was. Second: one model of the whole Arts Quad. Eight of fourteen buildings got no camera
at all, and the whole collection, 339 photographs, came out as 29 separate pieces. People photograph landmarks, not
the walls between them. Third: a twenty-year time machine, Gates Hall rising from a parking lot. Not one licensed
photograph of any site exists from before its building went up. And all three needed the same thing I didn't have: a
model that knows where it is.

**讲:** 做这个项目之前，先试过三个方向。第一个是名字的来历：Boardman Hall，康奈尔以前的法学院楼，位置就是现在的 Olin
Library，留下二十张公有领域的明信片，那就把它重建出来。我用还在的建筑给老照片定位，结果每一张 Boardman 都是镜像：现代照片
全是从西南边拍钟楼，明信片从东北边拍，钟楼四面又长得一样；位姿误差只有几个像素，但站在了错的一侧。照片本身说不出这栋楼在哪。
第二个：把整个 Arts Quad 建成一个模型。十四栋楼里八栋一个相机都没有；整个照片集 339 张一起重建，碎成 29 块——大家拍的是地标，
不是地标之间的墙。第三个：二十年的时光机，看 Gates Hall 从停车场里长出来。可是每个工地在楼盖起来之前，一张授权照片都没有。
而这三个方向都需要同一样我没有的东西：一个知道自己在哪里的模型。

**Transition / 过渡:** So what does COLMAP actually give you? / 那 COLMAP 到底给了你什么？

### Slide 4 · Seven free numbers, and why GPS can't fix them here (1:45–2:30)

**Show / 操作:** the floating model and the seven dots, then the GPS numbers on the right. / 漂着的模型和七个点，然后是
右边的 GPS 数字。

**Say:** This is what COLMAP gives you: 88 licensed photographs of the tower and the library, 32 photographers, 5,901
points. It looks right, but structure from motion recovers a scene only up to a similarity: one scale, three rotations,
three translations, and COLMAP fixes those seven numbers arbitrarily. COLMAP's own fix is the model aligner: give it
camera positions, usually GPS, and it solves them. That's the right tool when you have GPS. Here, 63 of the 88 are
Flickr web copies with no metadata at all, and the rest carry exactly one tag, which points to downtown Ithaca, 1.7
kilometres away. A similarity needs three good, well-spread positions per fragment. And where GPS does exist, at Gates
Hall with six tags, a GPS fit puts a held-out camera 11 metres off, and a wrong tag never announces itself.

**讲:** 这是 COLMAP 给你的：88 张钟楼和图书馆的授权照片，32 位摄影者，5,901 个点。看起来没问题，但 SfM 只能把场景恢复到一个
相似变换：1 个尺度、3 个旋转、3 个平移，这 7 个数 COLMAP 是随便定的。COLMAP 自己的办法是 model aligner：给它相机位置，通常是
GPS，它就能解出来。有 GPS 的时候这是对的工具。但这里 88 张里有 63 张是 Flickr 的网页版，元数据全没了；剩下的只有 1 个 GPS
标签，指向 Ithaca 市中心，偏了 1.7 公里。拟合相似变换每个片段至少要 3 个靠谱、分散的位置。而有 GPS 的地方——Gates Hall 那个有
6 个标签的片段——GPS 拟合把留出的相机放偏了 11 米，而且标签错了没有任何东西会告诉你。

### Slide 5 · The world already has a 3D model (2:30–2:55)

**Show / 操作:** the lidar campus. / lidar 校园。

**Say:** But the United States already has a 3D model of itself: USGS airborne lidar, public domain, in metres,
covering most of the country. Add OpenStreetMap's footprints and the state's aerial flights. So the question became:
can public measurements fix the seven numbers instead of GPS, and can the method say when they can't?

**讲:** 但美国本来就有一个自己的 3D 模型：USGS 的机载 lidar，公共领域，以米为单位，覆盖美国大部分地区。再加上
OpenStreetMap 的建筑轮廓和州里的航拍。所以问题变成了：能不能不用 GPS，用公开测量把这 7 个数定下来？定不了的时候，方法能不能
自己说出来？

**Transition / 过渡:** Here is the whole pipeline. / 下面是完整的流程。

### Slide 6 · The pipeline (2:55–3:25)

**Show / 操作:** the grey lane, the green lane, then the orange one and the three uses. / 先灰色，再绿色，然后橙色和下面
的三个用途。

**Say:** Grey is COLMAP: licensed photographs, hloc features and matches, pycolmap's incremental mapper; out comes a
fragment in its own frame. Green is the public world: the lidar crop turned into two rasters, the surface and the bare
ground, in UTM metres; the footprints turned into walls and roof edges. Orange is what I wrote: cues that score a
placement against the world, a search over the seven numbers, a certificate, and the placement applied with pycolmap's
Reconstruction.transform. Everything after that lives in metres: new photographs, splats checked by the lidar, the
time chapters.

**讲:** 灰色是 COLMAP：授权照片，hloc 提特征和匹配，pycolmap 增量建图，出来一个在自己坐标系里的片段。绿色是公开的世界：
lidar 裁出来做成两张栅格——表面和裸地，UTM 米制；建筑轮廓变成墙和屋檐。橙色是我写的：拿线索给一个摆法打分，在 7 个数上搜索，
写一张证书，最后用 pycolmap 的 Reconstruction.transform 把变换应用上去。之后的一切都在米制里：新照片、被 lidar 检查的 splat、
时间章节。

### Slide 7 · Step 1 · the two inputs (3:25–3:50)

**Show / 操作:** left the fragment, right the world. / 左边片段，右边世界。

**Say:** The two inputs. The fragment: 88 licensed photographs; NetVLAD picks the pairs, SuperPoint and LightGlue
match them, pycolmap maps: 88 cameras and 5,901 points, with the facade normals and the photographers' positions the
cues will read. The world: a 640-metre lidar box at half-metre cells, split into a surface raster and a bare-ground
raster, and 1,078 OpenStreetMap footprints raised from the lidar ground to the lidar roof. That raised city is also
what the page draws.

**讲:** 两个输入。片段：88 张授权照片，NetVLAD 选配对，SuperPoint 和 LightGlue 匹配，pycolmap 建图，得到 88 个相机、5,901 个
点，还有后面线索要读的立面法向和摄影者位置。世界：640 米见方的 lidar，半米一格，分成表面栅格和裸地栅格；1,078 个 OpenStreetMap
建筑轮廓，从 lidar 地面抬到 lidar 屋顶。这个抬起来的城市也就是网页画的那个。

### Slide 8 · Step 2 · each cue fixes some of the seven numbers (3:50–4:20)

**Show / 操作:** the cue table, row by row. / 线索表，逐行。

**Say:** No single cue fixes everything, so each one fixes part. Facade normals give the two tilts: walls are
vertical. The photographers' heights fine-tune them: people stand 1.6 metres above the lidar ground, give or take 30
centimetres. Footprint walls fix the heading and the position; precision is scored over every wall in the box and
recall over the named building, so a fragment can't shrink onto one wall line. Lidar roof edges, the tower top and
pairs of parallel walls each fix the scale, independently of each other. And free space, after Kaminsky 2009: the line
of sight from a camera to its point can't pass through a building.

**讲:** 没有哪条线索能定所有的数，所以每条定一部分。立面法向定两个倾斜：墙是竖直的。摄影者的高度再微调：人站在 lidar 地面
上方 1.6 米，上下 30 厘米。建筑轮廓的墙定朝向和位置——精确率算整个范围内所有的墙，召回率只算这栋楼的墙，这样片段不能缩到
一条墙线上。lidar 屋檐、塔顶、成对的平行墙各自独立地定尺度。还有自由空间，按 Kaminsky 2009 的做法：相机到它的点的视线不能
穿过建筑。

### Slide 9 · Step 3 · the search (4:20–4:50)

**Show / 操作:** the six steps. / 六步。

**Say:** The search keeps everything it looks at. The vertical comes from the facade normals first. If a tower is in
the box and the photographs name it, its axis pins the position. Then a grid: heading every 3 degrees, scale from a
third to three times a prior from the facade's height; in each cell the position descends along the wall distance
field. The best cells, at least 5 degrees apart, are refined jointly, then a half-degree scan around the winner. Last,
levelling: a robust plane through the photographers' heights proposes a residual tilt, and fits with the vertical
turned by a third, two thirds and all of it compete with the facade vertical on the joint objective. Every cue's score
is stored per cell, so any cue's profile over scale or heading can be read off afterwards.

**讲:** 搜索把看过的东西都留着。竖直方向先从立面法向来。范围里有塔、而且照片点了它的名，塔轴就钉住位置。然后是网格：朝向每
3 度一格，尺度从立面高度给的先验的三分之一到三倍；每个格子里位置沿着墙的距离场下降。最好的几个格子（至少相差 5 度）联合精化，
再在赢家附近做半度一格的扫描。最后是调平：用摄影者的高度拟合一个稳健平面，提出剩余的倾斜；把竖直方向转三分之一、三分之二、
全部的几个拟合，和立面竖直方向在联合目标上竞争。每条线索的分数按格子都存下来，所以任何线索在尺度或朝向上的剖面事后都能
直接读出来。

### Slide 10 · Step 4 · the certificate (4:50–5:25)

**Show / 操作:** the list on the left, then the placed fragment and its numbers; optionally demo chapter 2 for the snap. /
先左边的清单，再右边放好的片段和数字；可以切到演示第 2 章看吸附。

**Say:** The certificate is what the search writes down. Bands: how far each number can move before the objective
drops by a tenth of its range. The runner-up: the best heading more than 20 degrees away must score under 80 percent of
the winner. An ablation: remove each cue, refit, see how far the optimum moves. The cues' own scale profiles: if the
walls alone and the roof edges fix scales more than 25 percent apart, the verdict is "cues disagree". Two structural
rules: a roof-edge score under 0.25 with no landmark means no facade was seen, and more than one photographer in ten
inside a building is a refusal. On the tower fragment it reads usable: the scale fixed three independent ways within
3.9 percent, the runner-up heading at 72 percent, levelled by 3.7 degrees, and 83 percent of COLMAP's own points within
2.5 metres of a lidar surface.

**讲:** 证书就是搜索写下来的东西。区间：每个数能动多远，目标函数才掉它量程的十分之一。第二名：离最优 20 度以外的最好朝向，
分数必须低于赢家的 80%。消融：每次去掉一条线索重新拟合，看最优解挪了多远。各线索自己的尺度剖面：只用墙和只用屋檐定出的尺度差
超过 25%，结论就是"线索矛盾"。两条结构规则：屋檐分数低于 0.25 又没有地标，就是没看到立面；超过十分之一的摄影者在建筑里面，
就拒绝。钟楼片段的证书是"可用"：尺度由三种独立方式定出，相差 3.9% 以内；第二好的朝向 72%；调平 3.7 度；COLMAP 自己的点 83%
落在 lidar 表面 2.5 米内。

### Slide 11 · The certificate's numbers, explained (5:25–5:55)

**Show / 操作:** the table, row by row. / 表格，逐行。

**Say:** Each number on the certificate means something physical. Plus or minus 3.9 percent: the tower top fixes the
scale to about two metres over the tower's height, and the walls alone and four roof edges land inside that band, so
three independent measurements give the same 17.8 metres per COLMAP unit. 72 percent: the best heading more than 20
degrees away scores 72 percent of the winner; the rule is under 80, and a square tower alone would give about 95. 3.7
degrees: the photographers' heights proposed a 5.5-degree tilt and two thirds of it won on the joint objective; 18 of
the 88 photographers end up at eye height, the rest are far away and poorly placed along their rays. 83 percent of
COLMAP's own points lie within 2.5 metres of a lidar surface, 43 percent within a metre of a wall. And the cue scores at
the optimum say who did the work: the tower 1.0, free space 0.85, the walls 0.25.

**讲:** 证书上每个数都对应一件物理上的事。±3.9%：塔顶把尺度定到塔高上下约 2 米，只用墙和四条屋檐定出的尺度都落在这个区间里，
所以三个独立测量给出同一个 17.8 米每 COLMAP 单位。72%：离最优 20 度以外的最好朝向只有赢家 72% 的分数；规则是低于 80%，而
单独一座方塔会给出约 95%。3.7 度：摄影者的高度提出 5.5 度的倾斜，三分之二在联合目标上胜出；88 位摄影者里 18 位最后站在视线高度，
其余的离得远、沿视线方向放得不准。COLMAP 自己的点 83% 落在 lidar 表面 2.5 米内，43% 在墙 1 米内。最优解处各线索的分数说明
是谁在干活：塔 1.0，自由空间 0.85，墙 0.25。

### Slide 12 · How the scale is read: every cue's own profile (5:55–6:25)

**Show / 操作:** the curves, then the ablation table. / 曲线，然后右边的消融表。

**Say:** Here is why "three independent ways" is not a figure of speech. The objective over scale, each cue on its
own: the walls alone, the roof edges alone, the tower alone and the photographers' heights alone all peak at the same
scale. On the right, the ablation: take one cue away and refit. Removing the tower moves the optimum about a metre and
0.7 degrees; removing anything else moves it under 30 centimetres. The tower does the work, the walls and roof edges
confirm it, and the certificate says exactly that.

**讲:** 这就是为什么"三种独立方式"不是一句修辞。目标函数在尺度上的曲线，每条线索单独画：只用墙、只用屋檐、只用塔、只用摄影者
高度，峰都在同一个尺度上。右边是消融：每次去掉一条线索重新拟合。去掉塔，最优解挪了约 1 米、0.7 度；去掉别的，挪动不到 30 厘米。
塔在干活，墙和屋檐在确认，证书写的就是这个。

### Slide 13 · Watch it snap (6:25–6:45)

**Show / 操作:** click the clip (or demo chapter 2). / 点视频（或切到演示第 2 章）。

**Say:** The fragment floating in COLMAP's frame, then the placement applied: it lands among the lidar buildings and the
certificate appears. Nothing about the model changed; only the seven numbers.

**讲:** 片段漂在 COLMAP 的坐标系里，然后把变换应用上去：它落到 lidar 建筑之间，证书出现。模型本身没有变，变的只是那七个数。

### Slide 14 · When it refuses, and why (6:45–7:20)

**Show / 操作:** the table, then the four layouts on the right. / 表格，然后右边四种布局。

**Say:** The more useful half is the refusals. The whole campus at once: 339 photographs, 29 fragments, seven big
enough to try. All seven are refused, each with its reason: no facade seen, cameras inside buildings, cues disagree,
scale undetermined. Three carried enough GPS to check; they would have been 845, 64 and 325 metres off, and all three
were refused. Why these reasons? Geometry, measured on a synthetic hall with a known answer: one facade can't fix its
scale, you can't tell a small building up close from a big one far away; two parallel facades fix the scale but slide
along the walls; a corner or three facades pin everything, within 1 percent and a tenth of a degree.

**讲:** 更有用的一半是拒绝。整个校园一次重建：339 张照片，29 个片段，7 个够大可以试。7 个全被拒绝，每个有原因：没看到立面、
相机在建筑里、线索矛盾、尺度定不下来。其中 3 个有足够的 GPS 可以核对，硬放会偏 845、64、325 米——这 3 个全都被拒绝了。为什么是
这些原因？几何。在一个答案已知的合成建筑上测：一面墙定不了尺度，近处的小楼和远处的大楼看起来一样；两面平行墙定了尺度但会沿墙
滑动；一个墙角或三面墙把一切定住，尺度误差 1% 以内，朝向 0.1 度。

### Slide 15 · The synthetic hall, all sixteen cases (7:20–7:50)

**Show / 操作:** the chart, then the right-hand reading. / 图表，然后右边的解读。

**Say:** The full synthetic sweep. With exact lidar roof edges, every placement is within 3 percent in scale and the
verdicts are right. Give the lidar a 3-metre roof-edge error and the corner comes out 23 percent too large while the
certificate still says usable: nothing else in a corner fragment measures scale, so there is no second opinion. Where
the walls do measure it, parallel walls or three facades, the same error is caught as "cues disagree". That is the
known hole, and measuring it is on the plan.

**讲:** 完整的合成实验。lidar 屋檐准确时，每个放置的尺度误差都在 3% 以内，结论也都对。给 lidar 一个 3 米的屋檐误差，墙角那个
片段尺度大了 23%，证书却仍然说可用：墙角片段里没有别的东西测尺度，所以没有第二意见。而在墙本身能测尺度的情况——平行墙或三面
墙——同样的误差会被抓成"线索矛盾"。这是已知的漏洞，量化它在计划里。

### Slide 16 · The same building through two fragments (7:50–8:15)

**Show / 操作:** the table, then the reading below. / 表格，然后下面的解读。

**Say:** A check that needs no ground truth: the same building reconstructed in two fragments, each placed on its own.
McGraw Tower agrees within about a metre against every campus fragment, because the landmark pins it. Uris Library is
about 23 metres apart between the certified fragment and the campus fragments whose heading the certificate refused.
Refused frames disagree by tens of metres; nothing certified disagrees.

**讲:** 一个不需要真值的检验：同一栋楼在两个片段里各自重建、各自放置。钟楼对每个校园片段都在约 1 米内一致，因为地标把它钉住了。
Uris 图书馆在认证片段和那些朝向被拒绝的校园片段之间差了约 23 米。被拒绝的坐标系相差几十米；被认证的没有一个不一致。

### Slide 17 · Step 5 · a photograph it has never seen (8:15–8:55)

**Show / 操作:** the five steps, the two pictures, the four numbers; then demo chapter 11: a long-lens photograph in
the tray (the dashed line), then "paint the 88 photographs back". / 五步、两张图、四个数字；再切到演示第 11 章：点一张长焦
照片（看虚线），然后点"paint the 88 photographs back"。

**Say:** Back to the photograph from the start. COLMAP can register a new image, but into its own frame; here the
reference is the placed fragment, so the same registration lands on the map. NetVLAD finds the ten most similar of the
88; SuperPoint and LightGlue match them; pycolmap's RANSAC solves the pose from the EXIF focal length and four guesses,
then refines the focal length free; most inliers wins, at least 40. A long lens trades focal length against distance,
so the poses from the other guesses that keep 70 percent of the inliers form a segment: longer than 25 metres, and the
direction is placed but the distance is left open. Then the photograph is painted onto the lidar city from that pose,
with a depth test. Tested by taking each photograph out and placing it again: 53 placed, median 0.7 metres; 21 with the
distance open; 2 refused, and both would have been 115 metres wrong; and all 120 street photographs from the Arts Quad
side refused, because nobody online photographed the tower from there.

**讲:** 回到开头那张照片。COLMAP 能注册新照片，但只能进它自己的坐标系；这里的参考是放好的片段，所以同样的注册直接落在地图上。
NetVLAD 从 88 张里找最像的 10 张；SuperPoint 和 LightGlue 匹配；pycolmap 的 RANSAC 从 EXIF 焦距和 4 个猜测出发求位姿，再把焦距
放开精化，内点最多的赢，至少 40 个。长焦会拿焦距换距离，所以其他猜测里保留 70% 内点的位姿连成一段：超过 25 米，就只定方向、
距离留白。然后照片带深度测试投影到 lidar 城市上。检验方法是把每张照片拿出来重新放：53 张放好，中位 0.7 米；21 张距离留白；2 张
拒绝，硬放会偏 115 米；从 Arts Quad 那边拍的 120 张街景全部被拒，因为网上没人从那边拍过钟楼。

### Slide 18 · Placing a photograph, live (8:55–9:20)

**Show / 操作:** click the clip, or do it live on chapter 11 with your own phone photograph. / 点视频，或者在第 11 章用自己
的手机照片现场做。

**Say:** A photograph from the tray, placed in about two seconds without GPS; the camera moves to where the photographer
stood and the photograph is painted onto the city; then all 88 photographs painted back from their own poses.

**讲:** 托盘里的一张照片，不用 GPS 大约两秒放好；镜头移到摄影者站的位置，照片投影到城市上；然后 88 张照片各自从自己的位姿
投影回去。

### Slide 19 · Tested by taking each photograph out (9:20–9:50)

**Show / 操作:** the chart, then the four numbers with their meaning. / 图表，然后四个数字和它们的意思。

**Say:** The test: each of the 88 photographs taken out of the reconstruction and placed again from scratch, scored on
the 76 whose reference pose is itself trustworthy. 0.7 metres: half the placements land within a footstep of where the
reconstruction had them; the 90th percentile is 5.6 metres. 3.3 metres from the line: for the 21 long-lens shots the
direction is right and only the distance is open, and the true spot lies about three metres from the stated line. 115
metres: what a wrong acceptance would have cost, and both were refused. And 120 of 120: a whole side of the tower that
nobody online photographed, refused as a block rather than placed somewhere plausible.

**讲:** 检验：88 张照片每张拿出重建、从头再放，在 76 张参考位姿本身可信的照片上打分。0.7 米：一半的放置落在离重建位姿一步之内；
90 分位 5.6 米。离线 3.3 米：21 张长焦照片方向对、只有距离留白，真实位置离给出的那条线约 3 米。115 米：错误接受的代价，而这两张
都被拒绝了。120 张全拒：钟楼没人从网上拍过的那一整侧，被整体拒绝，而不是放到一个看似合理的地方。

### Slide 20 · What a world frame buys you (9:50–10:15)

**Show / 操作:** the two panels; optionally demo chapter 5 (the fly-through, tick "paint each Gaussian by the lidar's
verdict"). / 两个面板；可以切到演示第 5 章看 fly-through，勾选按 lidar 判定上色。

**Say:** Once the model is in metres, the lidar becomes a referee. I trained Gaussian splats from the same
photographs. A plain splat puts 41 percent of its Gaussians under the bare ground. Add one rule from the lidar,
measured free space is empty, and 88 percent sit on lidar surfaces, under 5 percent underground, and held-out
photographs render no worse. And because everything shares one frame, time comes for free: six aerial flights from
2002 to 2023 on the same terrain. Here's Gates Hall rising from a parking lot.

**讲:** 模型一旦以米为单位，lidar 就成了裁判。我用同样的照片训练 Gaussian splat。普通的 splat 有 41% 的高斯埋在地面以下。加上
lidar 的一条规则——测出来是空的地方就该是空的——88% 落在 lidar 表面上，地下的不到 5%，而且留出的照片渲染得不比原来差。因为
所有东西都在同一个坐标系里，时间也就顺带有了：2002 到 2023 年的六次航拍铺在同一块地形上。这是 Gates Hall 从停车场里长出来。

### Slide 21 · Held-out photographs, rendered by both splats (10:15–10:45)

**Show / 操作:** the two rows. / 两行图。

**Say:** Two photographs never used in training, rendered by each splat from the pose the placement gave them; the
numbers are PSNR against the photograph. They look alike: the lidar rule costs no image quality. The difference is
where the paint is, which the next clip shows.

**讲:** 两张训练时没用过的照片，由两个 splat 各自从放置给出的位姿渲染；数字是对照片的 PSNR。看起来差不多：lidar 规则不损失画质。
区别在于颜料画在了哪里，下一个视频看。

### Slide 22 · Between the photographers (10:45–11:15)

**Show / 操作:** click the clip (or demo chapter 5 with "paint each Gaussian by the lidar's verdict"). / 点视频（或演示第 5
章勾选按 lidar 判定上色）。

**Say:** A camera path no photographer took; left the plain splat, right the lidar-taught one, every Gaussian painted by
the lidar's verdict: red is paint in air the lidar measured empty, purple is under the ground. The numbers: on lidar
surfaces 41 to 88 percent of the Gaussians; under the ground 41 to 5; in empty air 18 to 8; and along this path 20
percent of the plain splat's pixels are paint the lidar refutes, against 4. Held-out photographs render no worse. One
rule in training did this: opacity times metres into measured-empty space.

**讲:** 一条没有摄影者走过的路径；左边普通 splat，右边 lidar 教过的，每个高斯按 lidar 的判定上色：红是 lidar 测到为空的空气里的
颜料，紫是地面以下。数字：落在 lidar 表面上的高斯从 41% 到 88%；地下从 41% 到 5%；空气里从 18% 到 8%；沿这条路径，普通 splat
有 20% 的像素是 lidar 否定的颜料，教过的是 4%。留出照片的渲染不比原来差。做到这些的只是训练里的一条规则：不透明度乘以伸进
测空区域的米数。

### Slide 23 · What is new here, honestly (11:15–11:40)

**Show / 操作:** the table, then the claim box. / 表格，然后下面的主张。

**Say:** What is new here, honestly. Aligning reconstructions to maps goes back to Kaminsky and colleagues in 2009;
Wang, Wilson and Snavely did it from geotags in 2013; ground photographs to airborne lidar was done in 2019 with GPS
initialisation; detecting degenerate registrations is a robotics literature of its own; and lidar-constrained splats
exist. None of them does this combination: sparse internet fragments without any GPS, against public lidar and
footprints, with a per-number diagnosis that refuses. That is the claim, and it is a method-and-system claim. What I
have not shown yet is that it beats a fair baseline, or that the diagnosis cuts wrong acceptances.

**讲:** 诚实地说什么是新的。把重建对到地图上，2009 年 Kaminsky 等人就做过；Wang、Wilson 和 Snavely 2013 年用地理标签做；
地面照片对机载 lidar 2019 年有人做过，但用 GPS 初始化；判断配准哪些方向退化，是机器人领域一整条文献；lidar 约束的 splat 也有。
没有哪个做的是这个组合：互联网稀疏片段、完全没有 GPS、对着公开 lidar 和轮廓、按每个数诊断并且会拒绝。这是我的主张，是方法加
系统的主张。还没证明的是：它比一个公平的基线好，以及诊断真的减少了错误接受。

### Slide 24 · Still working on (11:40–12:05)

**Show / 操作:** the four rows: gap, work, hoped end. / 四行：缺口、要做的、希望的终点。

**Say:** So this is the work still open, and I'd like to continue it as the final project. Independent truth: my own
phone photographs with GPS, and held-out geotags that no fit ever reads. Baselines: footprint-only alignment, a
Kaminsky-style edge-and-free-space fit, scale-aware point-cloud registration, and my own method without its diagnosis.
Reliability: acceptance coverage against false acceptances, keeping the case where a 3-metre roof-edge error passed
with the scale 23 percent off. And a second campus, anywhere USGS lidar covers. The end I hope for: a method that places
what can be placed and refuses what can't, measured on two campuses, written up as a workshop paper.

**讲:** 这就是还开着的工作，我想作为 final project 继续做。独立真值：我自己带 GPS 的手机照片，以及任何拟合都不读的留出地理
标签。基线：只用轮廓对齐、Kaminsky 式的边缘加自由空间、带尺度的点云配准，以及去掉诊断的我自己的方法。可靠性：接受覆盖率对
错误接受率，并保留那个 3 米屋檐误差让尺度错 23% 却通过的反例。再加第二个校园，只要有 USGS lidar 的地方都行。希望的终点：一个
能放的放好、不能放的拒绝的方法，在两个校园上测过，写成一篇 workshop 论文。

### Slide 25 · COLMAP's frame is arbitrary. The world's isn't. (12:05–12:15)

**Show / 操作:** the closing slide; leave the demo open for questions. / 结束页；演示页面开着答问。

**Say:** COLMAP's frame is arbitrary; the world's isn't. With public data only and no GPS, a reconstruction can be
placed, and it can say when it can't. Thank you. The demo stays open for questions.

**讲:** COLMAP 的坐标系是随便定的，真实世界的不是。只用公开数据、不用 GPS，重建可以被放进世界，放不了的时候它也会说。
谢谢大家，演示开着，欢迎提问。

### Slide 26 · Backup: the synthetic hall

**Show / 操作:** for questions on the refusal reasons. / 有人问拒绝原因时用。

**Say:** A synthetic hall with a known answer, seen from above; cameras in black, the facades they see in colour. One
facade leaves the scale free; two parallel facades leave the position free along them; a corner or three facades fix
everything within 1 percent in scale and a tenth of a degree in heading. The certificate reads exactly this off a real
fragment.

**讲:** 一个答案已知的合成建筑，从上往下看；相机是黑点，看到的立面是彩色。一面墙尺度自由；两面平行墙沿墙的位置自由；一个墙角或
三面墙全部定住，尺度 1% 以内、朝向 0.1 度。证书在真实片段上读的就是这个。

## Likely questions / 可能的提问

- **How accurate is the placement? / 放得有多准？** EN: There is no independent ground truth for the certified
  fragment yet. The evidence is that three independent cues fix its scale within ±3.9 %, that 83 % of COLMAP's points
  land within 2.5 m of a lidar surface, and that a photograph taken out and placed again lands a median 0.7 m from where
  the reconstruction had it. Phone photographs with GPS are the next check. / 中文：这个片段还没有独立的真值。证据是：三条
  独立线索定出的尺度在 ±3.9% 内一致；COLMAP 的点 83% 落在 lidar 表面 2.5 米内；照片拿出来再放回去，中位误差 0.7 米。下一步用
  带 GPS 的手机照片检验。
- **Why not just use GPS? / 为什么不直接用 GPS？** EN: COLMAP's model aligner does exactly that when the positions
  exist. A third of the Commons photographs carry a tag (129 of 393), but this fragment has one, 1.7 km off, and 63
  Flickr copies with no metadata (Flickr may hold a location for some; I did not ask it). A GPS fit needs three good
  tags per fragment and is metres off (about 11 m at Gates Hall); one Commons tag in the collection is 4,200 km off.
  Where GPS exists it is used only as held-out truth. / 中文：有相机位置的时候 COLMAP 的 model aligner 就是干这个的。三分之一
  的 Commons 照片带 GPS，但这个片段只有 1 个，还偏 1.7 公里，另有 63 张 Flickr 网页版没有元数据（Flickr 上也许有位置，我没去
  查）。GPS 拟合每个片段要 3 个靠谱的点，而且会差几米（Gates Hall 约 11 米）；集合里还有一个标签偏了 4,200 公里。有 GPS 的
  地方，我只拿它当留出的真值。
- **Has nobody done this before? / 以前没人做过吗？** EN: Pieces of it, yes: Kaminsky et al. (CVPR workshops 2009)
  aligned SfM to overhead images with edges and free space; Wang, Wilson and Snavely (3DV 2013) refined geotag
  placement; Zhang et al. (2019) aligned ground SfM to airborne lidar with GPS initialisation; degeneracy detection for
  scan registration is its own literature; lidar-constrained splats exist. The combination, sparse internet fragments
  with no GPS at all, public lidar and footprints, a per-number diagnosis that refuses, I have not found. That is a
  method-and-system claim, not yet a demonstrated advantage over a baseline. / 中文：零件都有人做过：Kaminsky 等人 2009 年
  用边缘和自由空间把 SfM 对齐到航拍图；Wang 等人 2013 年改进地理标签放置；Zhang 等人 2019 年把地面 SfM 对到机载 lidar 但用 GPS
  初始化；配准退化检测是一整条文献；lidar 约束的 splat 也有。这个组合——完全没有 GPS 的互联网稀疏片段、公开 lidar 和轮廓、
  按每个数诊断并会拒绝——我没有找到。这是方法加系统的主张，还不是对基线的优势。
- **What does COLMAP do, and what did you write? / 哪些是 COLMAP 做的，哪些是你写的？** EN: COLMAP (pycolmap) does the
  mapping, the transform, the RANSAC pose solver and the undistortion. I wrote the cue-based aligner and its
  certificate, the world-frame registration of new photographs with its three verdicts, the lidar scoring and the
  lidar rule for the splats, and the page. / 中文：建图、变换、RANSAC 位姿求解和去畸变是 COLMAP（pycolmap）做的。我写的是
  基于线索的对齐和证书、新照片注册进世界坐标和三种结论、splat 的 lidar 打分和 lidar 规则，以及这个网页。
- **Why not just get more photographs? / 为什么不多找点照片？** EN: I did: from 77 to 339 Commons photographs, 178
  Flickr photographs of the tower through Openverse, and a Mapillary probe. More photographs of the tower from Libe
  Slope do not connect the Arts Quad side; all 120 Mapillary photographs from that side are refused. / 中文：找了：从 77
  张到 339 张，再加 Openverse 上 178 张钟楼的 Flickr 照片，还试了 Mapillary。从 Libe Slope 多拍几张钟楼连不上 Arts Quad
  那一侧；那一侧的 120 张 Mapillary 全部被拒。
- **Is the lidar a fair referee for walls? / lidar 对墙面公平吗？** EN: Airborne lidar sees roofs and ground densely and
  walls thinly, so the free-space test allows 2.5 m horizontally and the scores on walls are conservative; COLMAP's own
  points (83 % on surfaces) are the noise floor. / 中文：机载 lidar 屋顶和地面测得密，墙面稀，所以自由空间测试允许水平 2.5 米
  的误差，墙面上的分数偏保守；COLMAP 自己的点（83% 在表面上）就是噪声底线。
- **The lidar is from 2020; what about change? / lidar 是 2020 年的，变化怎么办？** EN: The lidar rule is applied only
  to buildings that stood throughout (the tower and the library); the time chapters use documented dates and aerial
  flights. / 中文：lidar 规则只用在一直存在的建筑上（钟楼和图书馆）；时间相关的章节用的是有记录的日期和航拍。
- **Does it work elsewhere? / 别的地方能用吗？** EN: Anywhere USGS 3DEP lidar and OpenStreetMap footprints exist, which
  is most of the United States; it has only been run on Cornell so far, and a second campus is on the plan. / 中文：只要
  有 USGS 3DEP lidar 和 OpenStreetMap 建筑轮廓的地方都可以，也就是美国大部分地区；目前只在康奈尔跑过，第二个校园在计划里。
- **Is this research or a project? / 这是研究还是项目？** EN: A project that ran into a research question: when can
  public data fix a reconstruction's frame, and when can't it. One certified fragment and no baseline yet, so it is not
  a paper; the plan slide is what it would take. / 中文：是一个项目，做的过程中碰到了一个研究问题：公开数据什么时候能定住
  重建的坐标系，什么时候不能。目前只有一个认证的片段、没有基线，还不是论文；计划那一页就是要补的东西。

## If something breaks / 出问题时

- The splat does not appear: the browser is not using the GPU (`chrome://gpu`); stay on the slides, every slide has
  its still. / splat 不显示：浏览器没用 GPU；留在幻灯片上讲，每页都有截图。
- Dropping a photograph says "needs the demo server": the page is served by a plain file server; start the demo
  server (step 1). / 拖照片提示"needs the demo server"：页面是普通文件服务器开的，按第 1 步启动演示服务器。
- A dropped photograph is refused: say why (the certificate's reason is on the card) and click the Ho Plaza
  photograph in the tray instead; a refusal is part of the story. / 拖进去的照片被拒绝：念出卡片上的原因，然后改点托盘里
  Ho Plaza 那张；被拒绝本身就是故事的一部分。
- The page is blank: the server is not running, or the port is taken (`python3 serve.py 8090` in the bundle). /
  页面空白：服务器没开或端口被占（在离线包里用 `python3 serve.py 8090`）。
