# Before GhostMap: three directions we worked on, and why each one stopped
# 在 GhostMap 之前：我们认真做过的三个方向，以及它们为什么停下

Material for one or two opening slides. The three directions are in the order an audience finds them intuitive,
which is also roughly the order we tried them (2026-10-23 to 2026-10-26). Every number comes from a file in this
repository; the sources are listed at the end. The slide text and the spoken script are given in English and Chinese,
in the same format as [talk-track.md](talk-track.md).

## The short version / 一句话版本

**EN.** Before GhostMap we tried three intuitive things: bring back a demolished building from old postcards, build
one 3D model of the whole campus, and a twenty-year 3D time machine. Each one stopped on the data or on the
geometry, not on compute. On the day the GPU finally worked, we reconstructed the campus from 339 photographs in 7
minutes, and it was still in pieces. All three also needed the same missing thing: a COLMAP model that knows where
it is in the real world. Building that became the project.

**中文。** 做 GhostMap 之前，我们先试了三个很直觉的想法：用老明信片把拆掉的楼重建出来；把整个校园建成一个 3D 模型；做一个
二十年的 3D 时光机。三个都停在了数据或几何上，不是停在算力上：GPU 终于能用的那天，我们 7 分钟就用 339 张照片重建了整个
校园，结果还是一块一块的。而且这三个方向都缺同一样东西：一个知道自己在真实世界里哪里的 COLMAP 模型。把它做出来，就成了现在
的项目。

## At a glance / 一览

| | 1 · Bring back Boardman Hall | 2 · The whole campus as one model | 3 · A twenty-year time machine |
| --- | --- | --- | --- |
| The idea | rebuild a demolished building from public-domain postcards | more photographs and more compute give one 3D model of the Arts Quad | watch the campus change in 3D from 2002 to 2026 |
| How far we got | full study: 77 photographs, cross-era matching, 16 of 19 old photographs placed, carving code | four reconstructions, from 77 to 339 photographs, CPU and then GPU | a working page: aerial flights on lidar, dated buildings, years for every point |
| The number that stopped it | 203 points on Boardman where 1,000 were required; **every placed Boardman view was a mirror image** | **8 of 14 buildings got no camera**; on the GPU, still 7 separate fragments | **0 licensed ground-level photographs** of any site before construction |
| What kind of limit | data and geometry | data (coverage) | data, plus an idea already published in 2014 |
| Was it compute? | no: the sparse gate failed before compute mattered | at first, yes; once compute was fixed, the pieces stayed | no |
| What GhostMap kept | photographers stand on the ground; a certificate that can refuse | each fragment placed on its own, or refused with a reason | the time chapters, in one shared world frame |

---

## 1. Bring back Boardman Hall from old postcards / 用老明信片把拆掉的 Boardman Hall 重建出来

**Why it was the first idea.** It is where the name GhostMap comes from. Boardman Hall was Cornell's old law
building. It stood where Olin Library stands now, and it was photographed until at least 1958. Wikimedia Commons
holds 24 public-domain files of it (four photographs and twenty postcards, 1898 to 1934). The pitch: reconstruct a
building that no longer exists, from the internet alone.

**What we built (2026-10-23 to 2026-10-25).**
- The first study took 77 licensed Commons photographs (35 historical, 42 modern), admitted automatically under a
  protocol written before the run, with no hand-picking.
- Classic SIFT COLMAP registered **0** historical photographs. NetVLAD, SuperPoint and LightGlue registered 14
  historical and 22 modern ones (2,724 points, 178 verified cross-era pairs). So matching across eras works.
- Cross-era resection then placed each postcard against the surviving buildings (Uris Library, McGraw Tower) with
  the focal length unknown. It swept a grid of focal lengths and kept the 95 % interval of the camera's position
  along its viewing ray. 16 of 19 old photographs registered: the views of Boardman, and views of the library that
  still stands, which serve as controls.
- Two extra cues narrowed the intervals: the photographer stood on the lidar-measured ground, and the people in the
  postcard have human height.
- A carving step was written and passed a synthetic test. Sky pixels prove their rays empty, which bounds the vanished
  building from above.

**What we measured.**
- **Too few points on the target.** Only **203** points were seen by at least two Boardman photographs and by no
  modern one; the protocol required **1,000**. Every other point belonged to the library or the tower, which still
  stand.
- **The focal length is unknown, so the distance is unknown.** The postcards' lenses are unknown, and a longer lens
  further away looks the same as a shorter lens up close (the dolly-zoom effect). Changing the focal-length guess
  from 0.8 to 1.2 moved the 90th-percentile point by **3.3 scene radii** (329 %).
- **How far each postcard could slide.** For the 1914 "In the Quadrangle" card, the 95 % interval along its viewing
  ray was 875 m with the anchors alone, 91 m with the measured ground, and 7 m with the people in it.
- **The 7 m was precise, and it was wrong.** Every registered Boardman pose was a **mirror image**:
  - All 26 photographers in the modern tower fragment of that time stood west or south-west of it (bearings 213° to
    305°). The postcards were taken from the Arts Quad side, north-east of the site.
  - McGraw Tower's faces look alike, so the matcher paired east-face features with west-face points.
  - The resulting poses fit every anchor to a few pixels and look at the Boardman site from the wrong side. Neither
    automatic check caught it (the line-of-sight test against lidar buildings, and the test of whether the vanished
    building would have hidden the anchors). We found it by looking.
- **Even perfect pictures would not be enough.** After removing duplicates (one 1934 card was uploaded twice, and one
  negative was reused by two publishers), 4 or 5 independent exposures remain. They all look at the site from one
  wedge about 50° wide. The 2026-10-24 review estimated that carving from *perfect* silhouettes in that wedge would
  still bound an area 2.4 to 3.7 times the real footprint (an estimate on the earlier model).

**Why we stopped.** The surviving record does not contain the views it would take. Better software, a GPU or more
time cannot add a postcard taken from the east. The honest output of this direction is a map of what cannot be known,
a calibrated negative result. It would not make a demo. We kept the carving code and did not run it, because carving
from mirror poses would put the empty space on the wrong side of the site.

**Was it compute?** Partly at first, and it did not matter. COLMAP's dense stereo stopped with *"PatchMatch requires
CUDA but COLMAP was not compiled with it"*. But the target had already failed the sparse test (203 of 1,000 points)
before dense stereo started. Our own write-up said at the time: "GPU availability alone would not turn this run into
an accepted result." The GPU later worked and changed nothing here.

**What GhostMap kept.**
- *Photographers stand on the ground.* On the modern photographers, the measured ground narrowed the median position
  interval from 15.3 m to 4.2 m. It is now one of the estimator's cues.
- *A fit is not a placement.* The mirror poses fit to a few pixels. That is why every GhostMap placement carries a
  certificate that can say "refused" and give the reason.
- The mirror finding is on the limits slide. The same coverage hole explains why all 120 Mapillary street photographs
  from the Arts Quad side are refused today.

**中文要点。** 这是 GhostMap 名字的来历：Boardman Hall 是康奈尔以前的法学院楼，位置就是现在的 Olin Library。我们做了完整的
研究：77 张授权照片，跨年代匹配（SIFT 一张老照片都注册不上，学习特征能注册 14 张），19 张老照片里有 16 张通过还在的建筑
（图书馆和钟楼）定了位。停下的原因有三层：
1. 真正落在 Boardman 上的点只有 203 个，标准是 1,000 个。
2. 明信片的焦距未知：长焦站远和短焦站近拍出来一样，焦距猜 0.8 还是 1.2，点能差 3.3 倍场景半径。
3. 最致命的一点：所有定位出来的 Boardman 视角都是镜像。现代照片全是从钟楼西南边拍的，明信片是从 Arts Quad（东北边）拍的；钟楼四面
   长得一样，匹配把东面当成了西面。每个位姿重投影误差只有几个像素，但站在了错的一侧。最紧的 7 米区间，套住的是一个错误答案。

去重后独立的明信片只有 4 到 5 张，全挤在大约 50° 的一个扇区里，就算轮廓完美也围不出这栋楼。这是数据和几何的问题，不是算力：
COLMAP 的稠密重建确实因为没有 CUDA 跑不了，但稀疏那一关已经先挂了；后来有了 GPU 也没有改变结论。留下来的东西：摄影者
站在地面上这个约束，和一个会拒绝的证书。

---

## 2. The whole campus as one 3D model / 把整个校园建成一个 3D 模型

**Why it was the next idea.** It is the obvious thing to do with COLMAP and the internet (Photo Tourism, Building
Rome in a Day): collect every licensed photograph of the Arts Quad and get one model of all fourteen buildings. If it
breaks into pieces, add more photographs and more compute.

**What we built (2026-10-23 to 2026-10-26).** Reconstructions of growing collections, each from a frozen snapshot
with licences recorded:
- 77 training photographs from Wikimedia Commons, then 139;
- on the GPU, the campus-wide run: 339 photographs from the complete collection (Commons, and Flickr through
  Openverse);
- the tower run with 178 Flickr photographs added (the 88-photograph fragment GhostMap uses now).

Along the way we tried calibration fixes (EXIF focal lengths held, radial distortion fixed) and a probe of Mapillary
street-level imagery.

**What we measured.**
- **Most buildings had no camera.** On the 145-photo snapshot 36 of 77 photographs registered, in 6 separate models
  (21, 5, 3, 3, 2 and 2 cameras). **8 of the 14 target buildings had no camera at all.**
- **More matching did not help.** Exhaustive SIFT over all 2,926 pairs found only 43 verified pairs. The learned
  matcher found 205 verified pairs, and its match graph was almost connected (65 of 67 images), yet the mapper still
  produced 6 models: the links between buildings were one to five weak pairs.
- **Calibration was not the cause.** Holding EXIF focal lengths cut the focal blow-ups from 5 to 2 and merged
  nothing (22, 5, 3, 3, 2 cameras). Our note at the time: "Missing views, not calibration, split the scene."
- **More photographs, more pieces.** 139 photographs registered 82, and the first cameras appeared on Tjaden, Sibley,
  Lincoln, Rand and Milstein, but in separate fragments.
- **On the GPU it was still in pieces.** The campus-wide run reconstructed 339 photographs in 7 minutes into seven
  fragments of eight or more cameras. None could be placed that night, each for a stated reason:
  - a square tower cannot fix its own heading;
  - a single facade cannot fix its scale;
  - a mixture of buildings puts cameras inside walls.
- **The pieces disagree with each other.** Uris Library placed through two different fragments came out 25 m apart.
- **The internet photographs one side.** All 120 Mapillary street photographs from the Arts Quad side of the tower
  are refused (at most 19 agreeing points). The internet's photographers stand on Libe Slope and Ho Plaza, so no
  photograph links that side to the rest.

**Why we stopped.** A COLMAP model connects only what overlapping photographs connect, and people photograph
landmarks, not the walls between them. The fragments are not a bug to fix with a bigger run. They are what the
public record looks like. So the useful question changed: instead of forcing one model, put each fragment into the
real world by itself, and say which ones cannot be placed and why.

**Was it compute?** At first, yes, and we fixed it:
- The out-of-memory killer stopped the 139-photograph run twice during LightGlue matching (7.6 GB of RAM, on a disk
  97 % full). Matching in short-lived batches fixed that.
- The Python stack had no CUDA. A CUDA build of torch and a user-space CUDA compiler fixed that.

Once compute was fixed, the answer did not change: 339 photographs in 7 minutes, still seven fragments. A larger pair
budget does not create overlapping views.

**What GhostMap kept.**
- Fragments named by their buildings, each placed on its own in the lidar frame.
- The campus run, all refused for stated reasons, is now the "knowing when it can't" slide.
- Comparing two fragments that contain the same building is the sharpest consistency check we have.

**中文要点。** 用 COLMAP 和网上照片，最直觉的就是把整个 Arts Quad 建成一个模型（Photo Tourism、Building Rome in a Day 就是这个
思路），碎了就加照片、加算力。我们从 77 张一路做到 339 张，先 CPU，后 GPU，结果：
- 77 张里只注册上 36 张，分成 6 个互不相连的模型，14 栋楼里 8 栋一个相机都没有。
- 穷举 2,926 对只验证出 43 对。
- 固定 EXIF 焦距能消掉焦距爆炸，但一块都没合并：缺的是视角，不是标定。
- 上了 GPU，7 分钟重建 339 张，还是 7 个片段。
- 同一栋 Uris Library 在两个片段里差 25 米。
- 从 Arts Quad 一侧拍的 120 张 Mapillary 街景全部被拒：网上的人都站在 Libe Slope 和 Ho Plaza 拍钟楼。

算力一开始确实是瓶颈（内存只有 7.6 GB，139 张那次 LightGlue 匹配两次被系统因内存不足杀掉），分批匹配和 GPU 都解决了，但碎片还在。所以问题变成了：
不强求一个大模型，而是把每个片段单独放进真实世界，放不了的说清楚为什么。

---

## 3. A twenty-year 3D time machine / 二十年的 3D 时光机

**Why it was the next idea.** If a century back to Boardman is too thin, take the twenty years where photographs
exist (2002 to 2026) and watch the campus change. Gates Hall rises from a parking lot (built 2012 to 2014), Klarman
Hall fills the courtyard behind Goldwin Smith (2016), Milstein Hall replaces a parking lot behind Sibley (2011), and
McGraw Tower, which never changes, holds the timeline in place. The mechanism is the one from Scene Chronology: each
3D point carries the years in which photographs saw it.

**What we built (2026-10-25 to 2026-10-26).**
- A year slider over six New York State aerial flights (2002, 2007, 2012, 2015, 2018 and 2023), draped on the 2020
  USGS lidar terrain.
- Changed buildings shown only after their documented construction dates.
- The year intervals of every point of the tower fragment.
- Acquisition and reconstruction runs for the Gates, Klarman and Milstein sites.

**What we measured.**
- **No "before" photographs exist at ground level.** There is not one licensed photograph of any of the three sites
  before construction:
  - Gates: 0 of 53 eligible;
  - Klarman: 9 near the site, none showing it;
  - Milstein: 0.

  The "before" state exists only from the air.
- **The "after" photographs do not make a model either.** Gates Hall's ground record is 37 licensed photographs by 4
  photographers, mostly one photographer's walk on 2014-06-08. They show the entrance undercroft, stairs and bike
  racks, not the facades. They map into fragments of 11, 8 and 3 cameras, and the largest cannot be placed. On the
  campus run the Gates fragment rests on one wall's roof edge, so its scale is undetermined.
- **A point's years are the years someone photographed it.** That is not the same as the years it stood, so "the
  building appears in 2014" says when people started photographing it.

**Why it is not the main line.** The 3D part of the time machine has no data before construction. The mechanism
(per-point time intervals) was published in 2014 (Matzen and Snavely, *Scene Chronology*, ECCV 2014; learned version:
Lin et al., *Neural Scene Chronology*, CVPR 2023). And it depends on something we did not have: the aerial flights
and the lidar are in metres on the Earth (UTM), while COLMAP's model is in a frame of its own. To put a reconstructed
building on a dated aerial photograph, the model first has to be placed in the world. So the time machine became the
application, and the placement became the research.

**Was it compute?** No. Every limit here is photographs that do not exist, or that cover the wrong part of the
building.

**What GhostMap kept.**
- The time chapters of the page: the campus from above, Gates Hall, Klarman Hall, the tower.
- The line on the "what a world frame buys you" slide: once everything shares one frame, time comes for free.

**中文要点。** 一百年太薄，那就做有照片的二十年（2002 到 2026）：Gates Hall 从停车场里长出来，Klarman Hall 填满 Goldwin Smith
后面的院子，钟楼不变、把时间轴钉住。机制就是 Scene Chronology：每个 3D 点带着拍到它的年份。我们做出了能用的页面：六次纽约州
航拍铺在 lidar 地形上、按建成日期出现的建筑、钟楼每个点的年份。停下的原因：
1. 三个工地在建成之前，一张地面的授权照片都没有，"之前"只能从天上看。
2. "之后"的照片也建不出模型：Gates 的 37 张大多是同一个人 2014 年一次散步拍的入口、楼梯、自行车架，拍不到立面，碎成 11、8、
   3 三块，最大那块也放不进世界。
3. 一个点的年份只是有人拍它的年份，不是它存在的年份。
4. 每点带时间区间这个机制 2014 年就发表了（Scene Chronology），神经网络版本 2023 年（Neural Scene Chronology）。

更根本的是：航拍和 lidar 都在地球上、以米为单位，COLMAP 的模型却在自己的坐标系里。要把重建出来的楼放到某一年的航拍上，得先把
模型放进世界。所以时光机变成了应用，"放进世界"变成了研究。跟算力无关。

---

## Was it compute? / 是不是算力的问题？

The question an audience asks first. The honest answer is that we did hit compute limits, fixed most of them, and
fixing them revived none of the three directions.

| Limit we hit | What it blocked | Fixed? | Did fixing it bring a direction back? |
| --- | --- | --- | --- |
| pycolmap built without CUDA: COLMAP's dense stereo refused to run | a dense Boardman surface | worked around with OpenMVS on the CPU | no: the Boardman target had already failed the sparse test (203 of 1,000 points) |
| 7.6 GB of RAM: the out-of-memory killer stopped the 139-photograph matching twice | the larger campus model | yes: matching in short-lived batches (82 of 139 registered) | no: more photographs registered, in more separate fragments |
| no GPU in the Python stack until 2026-10-26 | learned matching at scale, Gaussian splats | yes: CUDA torch and a user-space CUDA compiler; 339 photographs in 7 minutes | no: seven fragments, none placeable that night |
| full-resolution dense fusion killed by memory | the tower's dense surface | half resolution | not a direction blocker |
| Commons throttling (about one original every ten minutes) | download speed | the sites the demo needed went first | no |

What compute cannot fix, in one line per direction:
- **Boardman:** no postcard was taken from the east, and the lens of each postcard is unknown.
- **Campus:** nobody photographs the walls between landmarks, or the tower from the Arts Quad side.
- **Time machine:** nobody photographed the parking lot before Gates Hall was built.

**中文。** 我们确实碰到过算力限制（没有 CUDA 跑不了稠密重建、内存不够导致匹配被杀、一开始没有 GPU），大部分都解决了。
但解决之后，三个方向没有一个活过来。算力补不出没人拍过的照片：没人从东边拍过 Boardman，没人拍地标之间的墙，没人在 Gates
Hall 建之前拍过那个停车场。

---

## The common thread / 共同的线索

All three directions needed a model in metres, with north and up, at a place on the Earth: the ground under a
postcard's photographer, a shared frame for separate fragments, the frame the aerial flights and the lidar live in.
COLMAP fixes those seven numbers arbitrarily, and its own way of fixing them needs GPS, which these photographs do not
have. The review we wrote on 2026-10-24, after eleven candidate directions and 22 adversarial reviews, put it the
same way: "Every direction is limited by the same thing: one alignable fragment and no metric frame." So we made
the frame the project: put COLMAP's reconstruction into the world's own 3D model without GPS, and say when it cannot.

**中文。** 三个方向缺的是同一样东西：一个以米为单位、有北有上、在地球上有位置的模型。明信片摄影者脚下的地面、各个片段共用的
坐标系、航拍和 lidar 所在的坐标系，都要求这一点。COLMAP 的 7 个自由度是随便定的，它自己的办法要靠 GPS，而这些照片没有。
10 月 24 日我们评估了 11 个候选方向、做了 22 轮反方审查，结论也是这句："每个方向都被同一件事卡住：只有一个能对齐的片段，
没有度量坐标系。" 于是我们把这个坐标系本身变成了项目：不用 GPS，把 COLMAP 的重建放进世界自己的 3D 模型里，放不了的时候说清楚。

---

## Slides / 幻灯片

The opening slide below is slide 3 of the deck (`artifacts/presentation/ghostmap-talk.pptx`, built by
`pipeline/ghostmap/package/talk_deck.js`; its script is slide 3 of [talk-track.md](talk-track.md)). The compute
question is deliberately not a slide: it is an engineering story, not the project's, so it lives in the section above
and in the Q&A below, for when someone asks. / 下面的开场页就是幻灯片的第 3 页（讲稿见 talk-track.md 第 3 页）。算力问题
故意不做成一页：那是工程上的事，不是项目本身，所以只留在上面那一节和下面的问答里，有人问再答。

### The opening slide: three things we tried first / 开场页：我们先试的三件事

**Title:** Three things we tried first / 我们先试的三件事

Three columns, one per direction, each with a picture, the idea in bold, one big number and a grey tag.

| | Boardman Hall | The whole campus | Twenty years |
| --- | --- | --- | --- |
| Picture | the 1934 postcard `data/raw/historical/114317667_Cornell_-_Boardman_Hall_and_the_library.jpg` (public domain, Curt Teich & Co.) | `dist/assets/presentation/refuse.png` (the refused fragments) | `data/orthoimagery/gates-site/2012-utm18n.jpg` beside `2015-utm18n.jpg` (the parking lot, then the building; NYS GIS Program Office). Crop both to the block north of the baseball field: in the full 2,500-pixel crop the change is small |
| Idea (EN) | Rebuild a demolished building from old postcards | One 3D model of the whole Arts Quad | Watch the campus change in 3D, 2002–2026 |
| Idea (中文) | 用老明信片重建拆掉的楼 | 整个 Arts Quad 一个 3D 模型 | 用 3D 看校园二十年的变化 |
| Big number | every Boardman view placed as a **mirror image** | **8 of 14** buildings: no camera | **0** photographs before construction |
| Tag | data and geometry | data: coverage | data, and published in 2014 |

Bottom line, full width: *All three needed the same thing: a COLMAP model that knows where it is.* / *三个方向缺的是同一样东西：
知道自己在哪里的 COLMAP 模型。*

**Say (about 45 s):** Before this project there were three others. The first is where the name comes from: Boardman
Hall, Cornell's old law building, which stood where Olin Library is now. Twenty public-domain postcards of it
survive. We placed the old photographs against the library and the tower, and every view of Boardman came out as a
mirror image. All the modern
photographs of the tower are taken from the south-west, the postcards from the north-east, and the tower's faces
look alike. Second: one model of the whole campus. Eight of fourteen buildings got no camera at all. Third: a
twenty-year time machine. Not one photograph of any construction site exists from before the building went up.

**讲（约 45 秒）：** 做这个项目之前，我们先做过三个方向。第一个是名字的来历：Boardman Hall，康奈尔以前的法学院楼，位置就是
现在的 Olin Library。留下来二十张公有领域的明信片，我们用图书馆和钟楼给这些老照片定位，结果每一张 Boardman 都是镜像：现代照片全是从西南边
拍钟楼，明信片是从东北边拍的，钟楼四面又长得一样。第二个：把整个校园建成一个模型，十四栋楼里八栋一个相机都没有。第三个：
二十年的时光机，可是每个工地在楼盖起来之前，一张照片都没有。

---

## Likely questions / 可能的提问

**"Why not just get more photographs?"** We did: from 77 photographs to 339, then 178 Flickr photographs of the tower
through Openverse, and a Mapillary probe. More photographs of the tower from Libe Slope do not connect the Arts Quad
side; all 120 Mapillary photographs from that side are refused. / **"为什么不多找点照片？"** 找了：从 77 张到 339 张，
再加上 Openverse 上 178 张钟楼的 Flickr 照片，还试了 Mapillary。从 Libe Slope 多拍几张钟楼，连不上 Arts Quad 那一侧；那一侧的 120 张 Mapillary
全部被拒。

**"Isn't Boardman the cooler project?"** Yes. With the surviving record its honest result is a map of what cannot be
known. It needs old photographs that see the site from another side and still register through surviving
buildings, plus modern photographs of the tower from the Arts Quad side to stop the mirror match. If those turn up,
the carving code is ready. / **"Boardman 不是更酷吗？"** 是更酷。但以现有的照片，它诚实的结果只能是一张"哪里无法确定"的图。它需要
从另一侧拍到那块地、又能通过还在的建筑注册上的老照片，还需要从 Arts Quad 一侧拍钟楼的现代照片来避免镜像匹配。哪天有了，
雕刻的代码是现成的。

*(Check this one before you use it: nothing in this repository tries DUSt3R or VGGT, so the answer below assumes you
didn't either.)* / *（用之前先确认：仓库里没有试过 DUSt3R 或 VGGT，下面的回答假设你也没试过。）*

**"Did you try learned reconstruction (DUSt3R, VGGT)?"** No. They would give another model in a frame of its own, with
no north and no place on the Earth, so the placement question would stay the same. / **"试过 DUSt3R、VGGT 这类学习方法吗？"**
没有。它们给出的仍然是自己坐标系里的模型，没有北、没有地理位置，放进世界的问题还在。

**"So the GPU was useless?"** No. It is why a new photograph is placed in about two seconds, and why the splats train.
It just could not create views nobody took. / **"那 GPU 没用吗？"** 有用：新照片两秒放好、splat 能训练，都靠它。它只是变不出
没人拍过的视角。

---

## Also considered, on paper only / 只在纸面上深入想过的

From the 2026-10-24 review: eleven candidate directions, each with an adversarial novelty review and an adversarial
feasibility review. Four of the rejected ones, in case someone asks:

| Idea | Why it was dropped |
| --- | --- |
| The lidar as a detector of wrong merges ("could a photographer have stood there?") | blind by structure: a fragment slid along the row of look-alike halls on the Arts Quad keeps every check satisfied |
| The sun as a clock (shadows date a photograph and check its pose) | already published (Hauagge 2014, Wehrwein 2015); our data held 1 to 3 of the 6 shadow sessions it needs |
| Re-photography from the same standpoint across a century | killed by measurement: on every registered archival photograph the parallax was at most 0.7 px per metre against the 1.5 px needed; the near objects that would give parallax (lamps, paths, trees) did not survive the century |
| Download the most informative photographs first | undefined for a building with no camera yet; needed a Flickr API key; an estimated 4.7 registrations per 10 downloads |

---

## Sources in this repository / 数据来源

- The Boardman study, its protocol and its failure analysis: [the legacy summary](../legacy/README.md) and
  [the Boardman results](../legacy/v1/results-v1.md)
- Cross-era resection, the mirror-pose finding, the photographers' ground cue, EXIF calibration:
  [the COLMAP-extensions checkpoint](../checkpoints/2026-10-25-colmap-extensions.md)
- Coverage per building, focal sensitivity, independent exposures, the eleven directions and their reviews:
  [the research direction review](../research/claude-research-review.md) (the inventory, the adversarial reviews and
  the decision matrix)
- The time machine's data check and pivot: [the time-machine plan](../plans/cornell-time-machine-plan.md) and
  [its checkpoint](../checkpoints/2026-10-25-time-machine.md)
- The campus-wide run on the GPU, its refusals and the distances between fragments:
  [the georegistration checkpoint](../checkpoints/2026-10-26-georegistration.md)
- The GPU, the disk and the Mapillary refusals: the decisions log in
  [the research plan](../plans/georegistration-paper-plan.md); the out-of-memory stops: the commit "Match missing pairs
  in short-lived batches"
