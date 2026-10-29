# GhostMap: the talk, slide by slide (English · 中文)

About eleven minutes, then questions. The slides are `artifacts/presentation/ghostmap-talk.pptx`, built by
`node pipeline/ghostmap/package/talk_deck.js` from the same data the demo page reads
(`dist/assets/timemachine/scene.json` and the reports beside it); each slide's section below is also that slide's
speaker notes. The live demo is `http://127.0.0.1:8080/timemachine.html`.

讲稿约十一分钟，之后答问。幻灯片是 `artifacts/presentation/ghostmap-talk.pptx`，由
`node pipeline/ghostmap/package/talk_deck.js` 从演示页面用的同一份数据生成；下面每一页的内容同时就是那一页的演讲者备注。
现场演示页面是 `http://127.0.0.1:8080/timemachine.html`。

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

### Slide 1 · GhostMap (0:00–0:30)

**Show / 操作:** the title slide. / 标题页。

**Say:** Hi, I'm [your name]. This is GhostMap, my COLMAP hacker project. In one sentence: COLMAP gives you a 3D
model in a coordinate frame that means nothing. I put it into the real world, without GPS, and I make it say when it
can't.

**讲:** 大家好，我是［名字］。这是 GhostMap，我的 COLMAP hacker project。一句话：COLMAP 给你的 3D 模型在一个没有意义的
坐标系里；我不用 GPS 把它放进真实世界，而且放不了的时候让它自己说出来。

### Slide 2 · Where was this photograph taken? (0:30–1:30)

**Show / 操作:** the photograph; then switch to the demo, chapter 11. Drop one of your own phone photographs (or click
the Ho Plaza photograph in the tray), click "stand where the photographer stood", drag the slider to "city" and
back. / 先放这张照片；切到演示第 11 章，拖进一张你自己的手机照片（或点托盘里 Ho Plaza 那张），点"stand where the
photographer stood"，把滑块拖到"city"再拖回来。

**Say:** Here's a photograph of McGraw Tower. Suppose it has no GPS, like most photographs on the internet once
they've been copied around. [drop it] About two seconds later it's on the campus: this is where the photographer
stood, this is the way they faced. Now I stand where they stood. The photograph is painted onto a 3D model of
Cornell from that exact spot: inside the white frame is the photograph, the dimmed part around it is the model.
[drag to "city"] Take the photograph away: the tower is still exactly there. The rest of this talk is how that
works, and when it doesn't.

**讲:** 这是一张钟楼的照片。假设它没有 GPS——网上的照片转几手之后大多都没有。［拖进去］大约两秒，它就落在了校园上：这是
摄影者站的位置，这是他朝的方向。现在我站到他的位置上。照片从这个点被投影到康奈尔的 3D 模型上：白框里是照片，外面调暗的
是模型。［拖到"city"］把照片拿掉，钟楼还在原来的位置。接下来讲它是怎么做到的，以及什么时候做不到。

**Transition / 过渡:** Let's start where every COLMAP project starts. / 我们从每个 COLMAP 项目的起点开始。

### Slide 3 · What COLMAP gives you (1:30–2:30)

**Show / 操作:** the floating model (optionally demo chapter 1, and rotate it). / 漂着的模型（可以切到演示第 1 章转一转）。

**Say:** 88 licensed photographs of McGraw Tower and Uris Library, from Wikimedia Commons and Flickr, by 32
photographers; the dated ones span 2003 to 2025. SuperPoint and LightGlue features, pycolmap's incremental mapper: 88 cameras and 5,901
points. It looks right, but it floats. Structure from motion only recovers a scene up to a similarity transform: one
scale, three rotations, three translations. COLMAP fixes those seven numbers arbitrarily. So the model has no metres,
no north, no up, and no idea where on Earth it is.

**讲:** 88 张有授权的钟楼和 Uris 图书馆的照片，来自 Wikimedia Commons 和 Flickr，32 位摄影者，有日期的从 2003 年到 2025 年。用
SuperPoint 和 LightGlue 提特征，pycolmap 增量建图：88 个相机，5,901 个点。看起来没问题，但它是漂着的。SfM 只能把场景恢复到
一个相似变换为止：1 个尺度、3 个旋转、3 个平移。这 7 个数 COLMAP 是随便定的。所以这个模型没有米、没有北、没有上，也不知道
自己在地球上哪里。

### Slide 4 · Why not just use GPS? (2:30–3:30)

**Show / 操作:** the three numbers. / 三个数字。

**Say:** COLMAP's own answer is the model aligner: give it the camera positions, usually GPS, and it solves for the
seven numbers. So look at the GPS we actually have. Across the collection about a third of the Commons photographs
carry a tag, 129 of 393. But in this fragment, 63 of the 88 are Flickr web copies that arrive with no metadata at
all, and the rest carry exactly one GPS tag. It points to downtown Ithaca, 1.7 kilometres from where the photograph
was taken. A similarity needs at least three good, well-spread tags per fragment, and phone GPS is off by metres to
tens of metres: at Gates Hall, the one fragment with six tags, a GPS fit puts a held-out camera about 11 metres off.
And when GPS is wrong, nothing tells you.

**讲:** COLMAP 自己的办法是 model aligner：给它相机位置，通常就是 GPS，它就能解出这 7 个数。那看看我们实际有多少 GPS。整个
照片集里大约三分之一的 Commons 照片带 GPS，393 张里 129 张。但在这个片段里，88 张中有 63 张是 Flickr 的网页版，元数据早就
没了；剩下的只有 1 个 GPS 标签，指向 Ithaca 市中心，离真正的拍摄位置 1.7 公里。拟合相似变换每个片段至少要 3 个靠谱、分散的
点，而手机 GPS 常差几米到几十米：Gates Hall 那个有 6 个 GPS 的片段，用 GPS 拟合，留出的相机偏了约 11 米。而且 GPS 错了，
没有任何东西会告诉你。

### Slide 5 · The world already has a 3D model (3:30–4:15)

**Show / 操作:** the lidar campus. / lidar 校园。

**Say:** But the United States already has a 3D model of itself: USGS airborne lidar, public domain, in metres,
covering most of the country. Add OpenStreetMap's building footprints and the state's aerial photographs. So the
question is: can we fix COLMAP's seven free numbers against this public measurement instead of GPS? And when the
evidence isn't enough, can it say so instead of guessing?

**讲:** 但美国本来就有一个自己的 3D 模型：USGS 的机载 lidar，公共领域，以米为单位，覆盖美国大部分地区。再加上
OpenStreetMap 的建筑轮廓和纽约州的航拍。所以问题是：能不能不用 GPS，而是用这份公开测量把 COLMAP 的 7 个数定下来？证据不够的
时候，能不能直接说"不够"，而不是瞎猜？

### Slide 6 · Where it plugs into COLMAP (4:15–5:00)

**Show / 操作:** the pipeline; point at the grey COLMAP steps, then the coloured ones. / 流程图：先指灰色的 COLMAP 步骤，
再指彩色的。

**Say:** Here's where this sits in the COLMAP pipeline. Grey is COLMAP: features and matches through hloc, incremental
mapping, and then the step that needs GPS. I replace that step: a similarity from public cues, with a certificate,
applied with pycolmap's Reconstruction.transform. Two more COLMAP steps get the same treatment. Registering a new
image: COLMAP registers it into its own frame, I register it into the world. And undistortion for Gaussian splats,
whose output can now be checked against the lidar.

**讲:** 这是它在 COLMAP 流程里的位置。灰色是 COLMAP：用 hloc 提特征和匹配，增量建图，然后是需要 GPS 的那一步。我替换的就是
这一步：用公开数据的线索求相似变换，附带证书，再用 pycolmap 的 Reconstruction.transform 应用上去。另外两步也一样处理：注册
新照片——COLMAP 只能注册进它自己的坐标系，我注册进真实世界；还有给 Gaussian splat 做的去畸变，它的输出现在可以拿 lidar 检查。

### Slide 7 · Each cue fixes some of the seven numbers (5:00–5:45)

**Show / 操作:** the cue table. / 线索表。

**Say:** No single cue fixes everything, so each one fixes part of the seven numbers. Facade normals give the up
direction. The photographers' heights over the lidar ground fine-tune it: people stand at eye height, they don't
float. OpenStreetMap walls fix the heading and the position. Lidar roof edges, the top of McGraw Tower and pairs of
parallel walls each fix the scale, independently of each other. And free space: a camera's line of sight can't pass
through a building to reach its point.

**讲:** 没有哪条线索能定所有的数，所以每条线索定其中一部分。立面的法向给出"上"。摄影者在 lidar 地面上的高度再微调它：人站着
是眼睛的高度，不会飘在空中。OpenStreetMap 的墙定朝向和位置。lidar 的屋檐、钟楼的塔顶、成对的平行墙各自独立地定尺度。还有
自由空间：相机的视线不能穿过建筑去看到它的点。

### Slide 8 · It lands, with a certificate (5:45–6:45)

**Show / 操作:** the placed fragment; optionally switch to demo chapter 2 and let the snap play. / 放好的片段；可以切到演示
第 2 章看吸附动画。

**Say:** [chapter 2] It lands. And it comes with a certificate. The scale is fixed three independent ways and they
agree within plus or minus 3.9 percent. The best alternative heading scores only 72 percent of the winner. The vertical
was levelled by 3.7 degrees from the photographers' heights. And 83 percent of COLMAP's own points end up within 2.5
metres of a lidar surface.

**讲:** ［第 2 章］它落下来了，而且附带一张证书。尺度由三种独立的方式定出来，彼此误差在 ±3.9% 以内。第二好的朝向只有最优的
72% 的分数。竖直方向根据摄影者的高度校正了 3.7 度。COLMAP 自己的点有 83% 落在离 lidar 表面 2.5 米以内。

### Slide 9 · Knowing when it can't (6:45–7:30)

**Show / 操作:** the refusal table. / 拒绝的表格。

**Say:** The more interesting part is the refusals. I reconstructed the whole campus collection at once: 339
photographs, 29 fragments. Seven of them are big enough to try, and the certificate refuses all seven, each with a
reason: no facade seen, cameras inside buildings, cues that disagree, scale undetermined. Three of them carry enough
GPS to check, and those placements were 845, 64 and 325 metres off. All three had been refused. No fragment was
certified and then found wrong.

**讲:** 更有意思的是拒绝。我把整个校园的照片一起重建：339 张照片，29 个片段。其中 7 个够大可以试，证书把 7 个全部拒绝了，每个
都有原因：没看到立面、相机在建筑里面、线索互相矛盾、尺度定不下来。其中 3 个有足够的 GPS 可以核对，它们的放置偏了 845、64、
325 米——而这 3 个全都被拒绝了。没有一个片段是先被认证、后来发现是错的。

### Slide 10 · Geometry decides (7:30–8:15)

**Show / 操作:** the four facade layouts. / 四种立面布局。

**Say:** Why does it refuse? Geometry. I built a synthetic hall where the answer is known. One facade can't fix its
own scale: you can't tell a small building up close from a big one far away. Two parallel facades fix the scale,
but the fragment can still slide along them. A corner, or three facades, pins everything, within one
percent in scale and a tenth of a degree in heading. The certificate reads exactly this off the fragment.

**讲:** 为什么会拒绝？因为几何。我做了一个答案已知的合成建筑。只有一面墙定不了尺度：近处的小楼和远处的大楼看起来一样。两面平行
的墙能定尺度，但片段还能沿着墙滑动。一个墙角，或者三面墙，就全部定住了：尺度误差在 1% 以内，朝向误差 0.1 度。证书读的
就是这个。

### Slide 11 · A photograph it has never seen (8:15–9:00)

**Show / 操作:** the four steps and the two pictures; then demo chapter 11: click a long-lens photograph in the tray
(the dashed line), then "paint the 88 photographs back". / 先讲四步和两张图；再切到演示第 11 章：点托盘里一张长焦照片
（看虚线），然后点"paint the 88 photographs back"。

**Say:** Back to the photograph from the start. COLMAP can register a new image, but only into its own frame. I run
the same steps: NetVLAD finds the most similar of the 88 photographs, SuperPoint and LightGlue match them, and
pycolmap's RANSAC pose solver runs from several focal-length guesses. Because the model is already in metres, the
answer is a spot on the campus. On the left, the photograph painted onto the lidar city from that spot; on the right,
the same spot without the photograph. The tower is where the photograph says it is.

**讲:** 回到开头那张照片。COLMAP 能注册新照片，但只能注册进它自己的坐标系。我用同样的步骤：NetVLAD 从 88 张里找最相似的，
SuperPoint 和 LightGlue 匹配，pycolmap 的 RANSAC 位姿求解从几个焦距猜测出发。因为模型已经是以米为单位的，答案就是校园上的
一个位置。左边是照片从那个位置投影到 lidar 城市上；右边是同一个位置、没有照片。钟楼就在照片说的地方。

### Slide 12 · Tested by taking each photograph out (9:00–9:30)

**Show / 操作:** the chart and the four numbers. / 图表和四个数字。

**Say:** To test it, I took each photograph out of the reconstruction and placed it again from scratch. Of 76 with a
trustworthy reference pose, 53 are placed, with a median error of 0.7 metres. For 21, long-lens shots of a distant
tower, it says the direction is right but the distance is open, and draws the line the photographer stood on. 2 are
refused, and both would have been about 115 metres wrong. And all 120 street photographs from the Arts Quad side are
refused, because nobody on the internet photographed the tower from there.

**讲:** 为了检验，我把每张照片从重建里拿出来，从头再放一次。在 76 张有可信参考位姿的照片里，53 张被放置，中位误差 0.7 米；
21 张是远处拍钟楼的长焦照片，它说方向对但距离不确定，并画出摄影者可能站的那条线；2 张被拒绝，而这两张如果硬放都会偏大约
115 米。另外从 Arts Quad 那一侧拍的 120 张街景全部被拒绝，因为网上没有人从那一侧拍过钟楼。

### Slide 13 · What a world frame buys you (9:30–10:15)

**Show / 操作:** the two panels; optionally demo chapter 5 (the fly-through, tick "paint each Gaussian by the
lidar's verdict"). / 两个面板；可以切到演示第 5 章看 fly-through，勾选按 lidar 判定上色。

**Say:** Once the model is in metres, the lidar becomes a referee. I trained Gaussian splats from the same
photographs. A plain splat puts 41 percent of its Gaussians under the bare ground. Add one rule from the lidar,
measured free space is empty, and 88 percent sit on lidar surfaces, under 5 percent underground, and held-out
photographs render no worse. And because everything shares one frame, time comes for free: six aerial flights from
2002 to 2023 on the same terrain. Here's Gates Hall rising from a parking lot.

**讲:** 模型一旦以米为单位，lidar 就成了裁判。我用同样的照片训练 Gaussian splat。普通的 splat 有 41% 的高斯埋在地面以下。加上
lidar 的一条规则——测出来是空的地方就该是空的——88% 落在 lidar 表面上，地下的不到 5%，而且留出的照片渲染得不比原来差。因为
所有东西都在同一个坐标系里，时间也就顺带有了：2002 到 2023 年的六次航拍铺在同一块地形上。这是 Gates Hall 从停车场里长出来。

### Slide 14 · What it can't do yet (10:15–10:45)

**Show / 操作:** the four limits. / 四条局限。

**Say:** What it can't do yet. One of eight fragments is certified, and it has no independent ground truth yet; my
own phone photographs with GPS are the next check. A wrong lidar roof edge can fool the certificate: in the synthetic
test a three-metre error passed with the scale 23 percent off. The Arts Quad side stays blind until someone
photographs the tower from there. And the splats are still blurry, about 14.5 dB on held-out photographs.

**讲:** 还做不到的事。8 个片段只认证了 1 个，而且它还没有独立的真值；我自己带 GPS 的手机照片是下一步的检验。lidar 屋檐如果
错了能骗过证书：合成测试里 3 米的屋檐误差让尺度错了 23% 却通过了。Arts Quad 那一侧在有人从那里拍钟楼之前都是盲区。splat 也还很模糊，留出照片上大约 14.5 dB。

### Slide 15 · What is new here (10:45–11:15)

**Show / 操作:** the related-work table. / 相关工作表。

**Say:** This isn't the first attempt. Kaminsky and colleagues aligned reconstructions to overhead images in 2009;
Wang, Wilson and Snavely refined geotag-based placement in 2013; OrienterNet places single photographs on
OpenStreetMap. What's new here is lidar heights as the reference, explicit metric cues, and a certificate that
refuses.

**讲:** 这不是第一次有人做。Kaminsky 等人 2009 年把重建对齐到航拍图；Wang、Wilson 和 Snavely 2013 年改进了用地理标签放置；
OrienterNet 把单张照片放到 OpenStreetMap 上。这里新的是：用 lidar 高度做参照、明确的度量线索，以及一张会拒绝的证书。

### Slide 16 · COLMAP's frame is arbitrary. The world's isn't. (11:15–11:30)

**Show / 操作:** the closing slide; leave the demo open for questions. / 结束页；演示页面开着答问。

**Say:** So: COLMAP's frame is arbitrary; the world's isn't. With public data only and no GPS, a reconstruction can be
placed, and it can say when it can't. Thank you. The demo stays open for questions.

**讲:** 总结：COLMAP 的坐标系是随便定的，真实世界的不是。只用公开数据、不用 GPS，重建可以被放进世界，放不了的时候它也会说。
谢谢大家，演示开着，欢迎提问。

## Likely questions / 可能的提问

- **How accurate is the placement? / 放得有多准？** EN: There is no independent ground truth for the certified
  fragment yet. The evidence is that three independent cues fix its scale within ±3.9 %, that 83 % of COLMAP's points
  land within 2.5 m of a lidar surface, and that a new photograph taken out and placed again lands a median 0.7 m from
  where the reconstruction had it. Phone photographs with GPS are the next check. / 中文：这个片段还没有独立的真值。证据
  是：三条独立线索定出的尺度在 ±3.9% 内一致；COLMAP 的点 83% 落在 lidar 表面 2.5 米内；新照片拿出来再放回去，中位误差 0.7 米。
  下一步用带 GPS 的手机照片检验。
- **Why not just use GPS? / 为什么不直接用 GPS？** EN: A third of the Commons photographs carry it (129 of 393), but
  this fragment has one tag, 1.7 km off, and 63 Flickr copies with no metadata (Flickr may hold a location for some; I
  did not ask it). A GPS fit needs three good tags per fragment and is metres off (about 11 m at Gates Hall); one
  Commons tag in the collection is 4,200 km off. Where GPS exists it is used only as held-out truth. / 中文：三分之一的
  Commons 照片带 GPS，但这个片段只有 1 个，还偏 1.7 公里，另有 63 张 Flickr 网页版没有元数据（Flickr 上也许有位置，我没去
  查）。GPS 拟合每个片段要 3 个靠谱的点，而且会差几米（Gates Hall 约 11 米）；集合里还有一个标签偏了 4,200 公里。有 GPS
  的地方，我只拿它当留出的真值。
- **Has nobody done this before? / 以前没人做过吗？** EN: Kaminsky et al. (CVPR workshops 2009) aligned to overhead
  images; Wang, Wilson and Snavely (3DV 2013) refined geotag placement. New here: lidar heights and footprints as the
  reference, metric cues, and a certificate that refuses. / 中文：Kaminsky 等人 2009 年对齐到航拍图，Wang 等人 2013 年
  改进了地理标签放置。这里新的是 lidar 高度和建筑轮廓做参照、度量线索，以及会拒绝的证书。
- **What does COLMAP do, and what did you write? / 哪些是 COLMAP 做的，哪些是你写的？** EN: COLMAP (pycolmap) does the
  mapping, the transform, the RANSAC pose solver and the undistortion. I wrote the cue-based aligner and its
  certificate, the world-frame registration of new photographs with its three verdicts, the lidar scoring and the
  lidar rule for the splats, and the page. / 中文：建图、变换、RANSAC 位姿求解和去畸变是 COLMAP（pycolmap）做的。我写的是
  基于线索的对齐和证书、新照片注册进世界坐标和三种结论、splat 的 lidar 打分和 lidar 规则，以及这个网页。
- **Is the lidar a fair referee for walls? / lidar 对墙面公平吗？** EN: Airborne lidar sees roofs and ground densely and
  walls thinly, so the free-space test allows 2.5 m horizontally and the scores on walls are conservative; COLMAP's own
  points (83 % on surfaces) are the noise floor. / 中文：机载 lidar 屋顶和地面测得密，墙面稀，所以自由空间测试允许水平 2.5 米
  的误差，墙面上的分数偏保守；COLMAP 自己的点（83% 在表面上）就是噪声底线。
- **The lidar is from 2020; what about change? / lidar 是 2020 年的，变化怎么办？** EN: The lidar rule is applied only
  to buildings that stood throughout (the tower and the library); the time chapters use documented dates and aerial
  flights. / 中文：lidar 规则只用在一直存在的建筑上（钟楼和图书馆）；时间相关的章节用的是有记录的日期和航拍。
- **Does it work elsewhere? / 别的地方能用吗？** EN: Anywhere USGS 3DEP lidar and OpenStreetMap footprints exist, which
  is most of the United States; it has only been run on Cornell so far. / 中文：只要有 USGS 3DEP lidar 和 OpenStreetMap
  建筑轮廓的地方都可以，也就是美国大部分地区；目前只在康奈尔跑过。
- **Is this research or a project? / 这是研究还是项目？** EN: A project that ran into a research question: when can
  public data fix a reconstruction's frame, and when can't it. The evaluation is one certified fragment so far, so it
  is not a paper yet. / 中文：是一个项目，做的过程中碰到了一个研究问题：公开数据什么时候能定住重建的坐标系，什么时候不能。
  目前只有一个认证的片段，还不够写论文。

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
