GhostMap — Research & Engineering Handoff for Claude Code
Date: October 24, 2026
Project: Cornell Arts Quad / GhostMap (CS 6672 3D Vision hacker project with research ambitions)
Suggested repository: /home/bobby/CS6672 (a path reported by a prior coding session; verify on this machine)
Your role: Critical 3D vision research collaborator, not just an implementation agent.
FIRST ACTION: Review the repository and literature, then give recommendations and a falsifiable research/demo plan. Do not start a large new reconstruction run, download campaign, or overhaul the website before delivering this assessment.
0. What the user actually wants
The user is a Cornell student working on 3D vision. The aspiration is a technically convincing, potentially paper-oriented research prototype, with a genuinely surprising interactive demonstration. They care strongly about correctness, visual detail, intellectual novelty, and the joy of seeing something previously inaccessible in 3D.

The original ambition, GhostMap, was to reconstruct the modern Cornell campus and bring back now-demolished historical structures, especially Boardman Hall, in their geometrically correct locations using online photographs. Boardman Hall formerly occupied the Arts Quad site where Olin Library now stands. Archival material exists, but prior attempts have not established a sufficiently verified historical 3D reconstruction.

Current priority has changed: FIRST build the modern Cornell Arts Quad, not only the tower or a single building, into a detailed, interactive, evidence-backed, reusable reference scene. Include multiple buildings and surrounding context. The modern reference scene may later support historical photo localization, cross-era geometry, and vanished-building reconstruction.

The user has also asked an important creative question:
Given the lineage of Noah Snavely's Photo Tourism / Scene Chronology and Wei-Chiu Ma's Virtual Correspondence / 3D-world research, what is a more interesting, more surprising, scientifically worthwhile GhostMap? How do we get beyond a standard photogrammetry demo?

Treat that as your first research task, not an invitation to implement the first idea that sounds attractive.
1. Non-negotiable constraints
1. 100% online input data. Do not ask the user to take photographs, perform scans, shoot video, visit a building, or manually annotate correspondences. Automatically obtainable, appropriately reusable internet photos/archival materials only. Publicly viewable is not automatically licensed for redistribution: track rights and usage restrictions. Credentials/private collections must not be assumed.
2. Zero human-in-the-loop dataset preparation. Automated search/download, metadata capture, duplicate detection, scene classification, camera pose estimation, matching, SfM/MVS, validation, export, and viewer preparation. The user may review research direction and deliverables, but they must not become a data-labeling dependency.
3. Measured geometry, not fabricated architecture. Official reconstruction views must be supported by actual photographic observation, geometric triangulation, multi-view inference and consistency tests. Use COLMAP and credible MVS or equivalent verified geometry pipelines. No hand-made building blocks, guessed facades, speculative CAD meshes, arbitrary textures, or generative fills represented as recovered truth.
4. Visual beauty cannot override truth. A detailed textured mesh / splat is welcome if reconstructed from images and validated. If rendering uses regularization, learned depth, generated priors, or completion, distinguish those estimates and their validation status from direct multi-view evidence. A photorealistic output is not proof of geometric correctness.
5. Environment matters. Recover ground, roads, neighboring buildings, edges, landmarks, and stable context when observed. A shared world reference frame is more important than isolated visually pleasing fragments. Trees/people/seasonal effects should be distinguished from persistent registration anchors.
6. Failure is a permissible scientific result; unearned success is not. If data cannot support a building or historical bridge, state where and why, and propose data-supported alternatives. Do not invent connections to make the viewer look complete.
7. Reproducibility. Preserve input source URLs, licenses, content hashes, camera models, transforms, matches, triangulated tracks, dense depth maps (as feasible), meshes/PLY, experiments, version strings, commands, and quality metrics. Avoid opaque outputs.
8. Pragmatic originality. Reuse strong existing techniques (COLMAP, hloc, MVS, etc.) instead of reimplementing them. A paper-like contribution requires a sharply defined problem, method/insight, honest baselines, and evidence—not merely a larger app.
Clarification about “all 3D based on COLMAP”: the user's rejection was of fake renderings presented as reconstruction. A COLMAP-calibrated scene may legitimately use validated MVS, surface reconstruction, or image-based rendering. However, the scientifically supported and speculative layers must remain distinguishable, and alternatives should be compared against a COLMAP baseline.
2. History of attempts (reported in prior sessions; NOT verified now)
These are historical claims from previous agent summaries, not fresh experimental proof. Inspect files and reconcile runs before repeating any number as current.
Previous snapshot	Reported observation	Interpretation / caution
Early v1, ~35–37 internet images	~8 modern registered cameras and ~1.5k sparse points; historical model with 2 independent viewpoints	Insufficient modern coverage and invalid Boardman recovery
Expanded cross-era experiment, 77 images	35 historical, 42 modern; learned matching reported 178 cross-era geometrically verified pairs; joint reconstruction reported 14 historical + 22 modern registered, ~2,724 sparse points	Matching / registration in a joint scene does not certify that the disappeared building surface was recovered
Historical subject gate	~6 Boardman photographs registered but only ~203 target-specific multi-view points against an earlier 1,000-point heuristic	Historical building surface did not pass quality threshold; point-count thresholds need defensible geometric justification
MVS repair	Modern dense result reported ~171k points and ~262k triangles after an OpenMVS workflow	Check which building/surface each polygon belongs to; high polygon count does not establish coverage, accuracy, or mesh fidelity
Modern Arts Quad reset	581 publicly discoverable candidates, 231 preliminarily accepted based on metadata; source image acquisition initiated	These are candidate counts, not usable independent geometric views; the new modern Quad-wide reconstruction has not yet been established by this handoff


Persistent issue: previous agents sometimes claimed the viewer was “done” even when the core geometry was sparse, invalid or incomplete. Subsequent repairs fixed UI bugs and generated some modern geometry but did not solve the Boardman research problem. The user has explicitly rejected impressive-looking web pages with poor or unsupported 3D.
Likely repository paths (verify, do not assume they still exist)
- README.md
- docs/plans/modern-artsquad-pipeline.md
- config/artsquad-modern.json
- docs/legacy/v1/results-v1.md
- docs/legacy/v1/protocol.md
- artifacts/public/report.json
- artifacts/hloc_cross_era/joint_report.json
- pipeline/download_commons.py
- pipeline/legacy/v1/build_site_data.py
- dist/index.html, dist/app.js, dist/baseline-v1.html
- Additional COLMAP, HLoc, OpenMVS image databases, sparse/dense outputs and log files elsewhere under the repo
Environment warning: The earlier summaries mention COLMAP 3.13 and an OpenMVS workflow; one COLMAP PatchMatch build previously lacked CUDA. Do not assume GPU availability, CUDA support, installed versions, adequate storage, or that previous long-running jobs have finished. Verify before creating any proposed run plan.
Research-status taxonomy (use in every future report)
- VERIFIED: Audited directly from files/logs/independent test images, with paths and commands.
- REPORTED: Appears in previous status notes but not independently verified.
- HYPOTHESIS: Proposed method or interpretation not yet tested.
- FAILED/BLOCKED: Explicitly unsupported or a reproducible failure.
Do not conflate geometrically verified image pairs, registered cameras, sparse tracks, dense points, and a good architectural surface reconstruction: these are different evidentiary levels.
3. Scientific lineage to understand BEFORE suggesting innovation
Study the actual methods, videos, and projects. The web links below are starting points; conduct an updated literature search, including closely related works beyond this list. Do not assert novelty from titles or abstracts alone.
Noah Snavely and collaborators
1. Photo Tourism: Exploring Photo Collections in 3D (SIGGRAPH/TOG 2006): unstructured photo collections, SfM, spatial photo browsing. Baseline for interactive internet-photo reconstruction.
   https://www.microsoft.com/en-us/research/publication/modeling-the-world-from-internet-photo-collections/
2. Scene Chronology (Matzen & Snavely, ECCV 2014, Best Paper): temporal support for 3D points and detection of scene elements with changing lifetimes. A historical timeline alone is NOT novel.
   https://www.cs.cornell.edu/~snavely/publications/matzen_eccv2014.pdf
3. Neural Scene Chronology (Lin et al., CVPR 2023): disentangles changes over time and illumination from internet photos, rendering different times and viewpoints of changing 3D scenes.
   https://openaccess.thecvf.com/content/CVPR2023/html/Lin_Neural_Scene_Chronology_CVPR_2023_paper.html
   https://zju3dv.github.io/NeuSC/
4. Doppelgangers (Cai et al., ICCV 2023): near-symmetric/repeated buildings may yield illusory feature matches and corrupted SfM. Especially relevant for Arts Quad facades.
   https://openaccess.thecvf.com/content/ICCV2023/html/Cai_Doppelgangers_Learning_to_Disambiguate_Images_of_Similar_Structures_ICCV_2023_paper.html
5. MegaScenes (Tung et al., ECCV 2024): scale and limitations of internet-photo SfM / novel view synthesis.
   https://www.ecva.net/papers/eccv_2024/papers_ECCV/html/4207_ECCV_2024_paper.php
Wei-Chiu Ma and collaborators
6. Virtual Correspondence: Humans as a Cue for Extreme-View Geometry (CVPR 2022): geometry constraints across views even without direct co-visible surface. Pay special attention to its mathematical definition and physical cues; don't casually call any cross-era alignment “new virtual correspondence.”
   https://openaccess.thecvf.com/content/CVPR2022/html/Ma_Virtual_Correspondence_Humans_as_a_Cue_for_Extreme-View_Geometry_CVPR_2022_paper.html
7. SGAM: Building a Virtual 3D World through Simultaneous Generation and Mapping (NeurIPS 2022): interactive large-scale world generation. Important creative inspiration, but its synthesized geometry/imagery does not satisfy GhostMap's evidence-only reconstruction requirement by itself.
   https://yshen47.github.io/sgam/
8. CADSim (CoRL 2022 / PMLR 2023): data-driven in-the-wild reconstruction for controllable simulation, illustrating a research direction beyond a static model.
   https://proceedings.mlr.press/v205/wang23b.html
9. Wei-Chiu Ma's publication list and demos: look at the lab's current 3D/4D understanding/reconstruction/re-simulation projects and choose at least two other directly relevant works.
   https://www.cs.cornell.edu/~weichiu/
Important contemporary baselines and counterexamples
10. COLMAP documentation, SfM/MVS, mapper options, limitations, texture workflows: https://colmap.github.io/tutorial.html and https://colmap.github.io/faq.html
11. MASt3R-SfM (3DV 2025): unconstrained SfM that may address weak image overlap; compare its real assumptions/resources against COLMAP+hloc. https://arxiv.org/abs/2409.19152
12. VGGT (CVPR 2025): camera/depth/point estimation from multiple images; potential proposal/initialization or baseline, not automatic geometric proof. https://openaccess.thecvf.com/content/CVPR2025/html/Wang_VGGT_Visual_Geometry_Grounded_Transformer_CVPR_2025_paper.html
13. Existing archival-photo / historical-site photogrammetry: explicitly review older and recent methods for extinct buildings, geo-referencing archival cameras, restoration, and historical image localization. Example prior art: https://isprs-archives.copernicus.org/articles/XLVIII-M-2-2023/43/2023/
14. Cornell historical reference: Boardman Hall was razed before Olin Library opened in 1961. Historical maps and demolition photos can be important external validation, but a 2D footprint/illustration is not in itself a recovered 3D surface.
       https://news.cornell.edu/stories/2015/12/cornell-rewind-fluid-landscapes-yesteryear
       https://exhibits.library.cornell.edu/olin-50/catalog.html
Literature traps to avoid: “3D + timeline,” photo overlays in modern camera coordinates, 3D photo tours, and manual archival building modeling all have substantial prior art. Merely recombining existing systems may yield an excellent class demo but does not automatically constitute a paper contribution. You must propose a specific previously unsolved setting, identifiable failure of baselines, and a testable methodological idea.
4. The key research question
We want your judgment, NOT confirmation of an already fixed direction:

Can a modern, independently validated Arts Quad reconstruction serve as a geometric reference frame for recovering spatial and temporal evidence from historical, sparse, non-overlapping photographs—especially for objects/buildings that no longer exist? If not, what better, surprising, data-feasible question should this project tackle?

Look for an insight akin in spirit (not a copy) to Photo Tourism's 3D-based browsing, Scene Chronology's spatiotemporal reasoning, and Virtual Correspondence's recovery of geometry under apparently impossible view overlap.

Your advice should identify the unexpected observable capability the project would unlock, not just which rendering technology to use.
Candidate provocations — challenge these, do not rubber-stamp them
A. Geo-anchored time portal / erased-building localization: from any supported modern camera pose, reveal a historically localized, genuinely reconstructed structure where a current building stands. Distinguish historical photographic evidence from any inferred missing surfaces. What exact archived views make this feasible?

B. Impossible archival camera localization: use still-existing neighboring geometry, architectural motifs, skyline or map constraints to register a historical photograph with negligible direct present-day overlap. Is there a new, mathematically defensible constraint rather than ad hoc fitting? How does it differ from virtual correspondences, standard PnP, architectural priors, and geo-localization?

C. Evidence X-ray / uncertainty-aware 3D: user points to a door, window, facade, or vanished object and sees the actual source photos, camera rays, estimated depth consistency, and where the reconstruction is unknown. Is this merely a useful UI or could it support a rigorous contribution, such as uncertainty-guided data selection?

D. Active internet-photo retrieval for reconstruction: the 3D system identifies exactly which facade/baseline is missing and automatically searches for photos that would maximally improve it. Demonstrate verified geometric gains over popularity-based scraping. Novelty must be checked against active SfM, view planning, retrieval, and photo-collection selection.

E. Time-dependent architecture, not time-dependent texture: recover architectural changes (walls/rooflines/footprints) with a single verifiable world reference frame and uncertainty; distinguish from graffiti/appearance chronology and previous 4D models.

F. Geometric detective demo: pick an unlabeled archival picture, infer where the photographer stood, which persistent anchors prove the hypothesis, and overlay source evidence on the modern 3D scene. Show honest ambiguous/rejected alternatives.

G. A different, better-targeted campus phenomenon: if Boardman cannot be reconstructed from available images, find another Cornell site with abundant independent historical perspectives and real structural change, or propose a surprising modern-only 3D interaction that is data-supported. A reliable alternative beats a fake Boardman.

H. Something you invent: bring at least three ideas NOT suggested above. Prefer concepts with a memorable 'how is that possible?' demo and an intellectually clear geometric insight.

Avoid assuming all these ideas are feasible or novel. Find disconfirming papers/data before enthusiasm.
5. What a successful modern Arts Quad reference scene needs
This is the immediate engineering substrate, independent of the final research idea:
- Scene-wide geometry: several Arts Quad buildings, inter-building walkable context and stable landmarks; camera groups localized in one consistent system where physically justified.
- High detail where supported: identifiable facades, window/column geometry, roof edges, paths, small structures, not just noisy points or a low-res enclosing shell.
- Good retrieval strategy: prioritize independent, diverse, overlapping baselines and large useful facades rather than raw photo count. Deduplicate reuploads, crop variants, web thumbnails, non-photo imagery, watermark-dominated matches, renderings, and site-unrelated photos.
- Connectivity: measure graph components, meaningful tracks spanning buildings, camera uncertainty, baselines and degeneracies (rotation-only image groups, repeated windows, reflective glass, vegetation, seasonal facade appearance).
- Trustworthy geometry: triangulation / multi-view depths / observed camera rays; retain per-region support and reject or mark holes. Do not fill a disconnected building with a guessed shape.
- Re-usable scene coordinate system: preserve transforms and future-usable world anchors. Metric claims require independent scale/geo reference and an uncertainty statement.
- Viewer: intuitive orbit, fly/walk, per-building selection, photo frusta, click-through source images, overlay of source image at its pose, textured surface versus wireframe/point view, reconstruction confidence, coverage map, and optional historical layers only when verified.
- Repeatable experiments: a frozen input manifest, provenance, versions, run configs, a scripted evaluation, and exported geometry directly traceable to model outputs.
Evaluation plan (ask for a revised, defensible protocol)
- Image registration rate per independent photo group, not just count.
- Valid connected components and degree/overlap distribution of the camera graph.
- Feature track lengths, parallax and triangulation angles, reprojection residual distributions (not only their average).
- Per-building / per-facade surface coverage, multi-view support, and dense depth consistency.
- Held-out images from independent contributors or capture sessions: localization success and reprojection; masked held-out rendering metrics if method is view-synthesis-capable (beware illumination/season confounding).
- Leakage-resistant image splits: avoid crop variants, near duplicates, and same-camera bursts crossing train/test.
- A calibrated notion of uncertainty, especially in visually unsupported parts.
- Ablations: SIFT/COLMAP baseline; modern learned feature / matching alternative; relevant SfM prior; scene-level vs per-building strategy; possibly additional weak-overlap baseline if computationally feasible.
- Resource accounting: image count, actual downloads, GPU model, VRAM, CPU/RAM, runtime, failure reasons, version / configuration.
Avoid absolute metric pass thresholds picked for optics. Propose thresholds tied to measurable geometry, visual coverage, and stated downstream use, and justify them. Reports should clearly distinguish registration success, dense reconstruction success, novel-view appearance, and paper-worthy insight.
6. FIRST TASK — mandatory read-only research/technical assessment
Step 1 — audit reality, briefly
Inspect the existing repository if present. Start by reading the README, the modern Arts Quad plan, config, raw image manifest, actual SfM/MVS outputs and website bundle. Use low-cost inspection before running experiments. Report:
1. What actually exists now, with exact paths and evidence; what is claimed but not verified.
2. Which image sources can legally be fetched and reused; how many usable independent camera views are actually available and which facades they cover.
3. The best validated modern-scene geometry; whether it covers the whole Quad or isolated fragments.
4. Current primary blockers—data overlap, camera calibration, retrieval, repeated structures, geometry, dense MVS, coordinates, web visualization—and what evidence distinguishes them.
5. Environment constraints (available devices, COLMAP/OpenMVS versions, CUDA, storage). Do not spend substantial compute before completing this audit.
If the repository is not available to you, explicitly say so and base your first response on this handoff without pretending you inspected files.
Step 2 — rigorous idea generation and literature reality check
Research the cited Noah and Wei-Chiu work, plus the most relevant research through October 2026. For each suggested idea, provide:
- A one-sentence surprising demo moment a professor could understand in ten seconds.
- The precise scientific problem and geometry assumptions.
- Closest 2–4 papers/projects, with links, and what they already do.
- What could actually be new beyond composition/engineering.
- The minimum online dataset, its availability/licensing, and a falsifiable feasibility probe.
- Main technical unknowns and likely failure modes.
- How much directly observed 3D the interactive output would contain.
- A 3–5-day proof-of-concept that can decisively reject the idea.
- A longer-term extension to a research paper, specifying a method and baseline evaluation.
Propose at least 8 genuinely distinct directions, with at least 3 ideas not on the candidate list above. Include modern-only options as well as historical ones. Be constructively skeptical; avoid saying something is novel without contrasting specific published work.
Step 3 — rank and decide
Score each direction 1–5 on: (i) 10-second demo surprise, (ii) scientific novelty after literature review, (iii) feasibility under online-only/no-human-data constraints, (iv) robustness to missing data, (v) value of modern Arts Quad as a reusable intermediate asset, (vi) pathway to a publishable question. Explain tradeoffs rather than merely averaging.

Offer:
- Best demo-first direction.
- Best publication-potential direction.
- Best balanced direction (recommended default).
- One direction you explicitly advise abandoning, and why.
Then propose a staged roadmap with Stage A = validated modern Arts Quad, Stage B = distinctive interactive experience, and Stage C = research novelty/possibly temporal recovery, with hard go/no-go tests and low-cost falsification checkpoints. Recommend a clear smallest viable target scene if whole-Quad input coverage is too weak, but keep world-scale as the ambition.
Step 4 — respond BEFORE coding
Your first reply should be a thorough, critical Research Direction Review in plain English or Chinese. Include a concise proposed architecture only after evaluating the scientific direction. Ask for user approval of the recommended scientific pivot before extensive implementation. Creating a research report file (e.g., docs/claude-research-review.md) is fine; do not silently rewrite reconstruction code or the existing site in this phase.

Do not: return only a polished feature wish-list, say “I'll fix it” without identifying a failure mechanism, pick a NeRF/3DGS stack because it looks photorealistic, count faces as proof of accuracy, or label a demonstrative scene as a verified historical reconstruction without supporting views.
7. Specific questions to answer explicitly
1. Why did Noah's 2006/2014/2023 demos feel intellectually surprising? Which capability, not merely rendering style, was unlocked? What obvious next question remains unsolved?
2. What would make Wei-Chiu Ma say “there is an idea here”? Identify a crisp unusual constraint or geometric primitive, rather than a stack of existing components. Do not presume to know his personal preferences.
3. Does the current Boardman dataset contain enough independent baselines for an identifiable 3D surface? How would you demonstrate unidentifiability instead of covering it up?
4. Can surviving modern buildings anchor archival camera localization where the target building itself is gone? Under what visibility and known-geometry conditions? Does the approach reduce to existing localization, virtual correspondence, or map registration?
5. What is the one most impactful improvement to modern reconstruction quality? Is it more good source views, a different global SfM strategy, disambiguating repetitive architecture, dense MVS, or better evaluation? Justify using evidence.
6. Can the site offer an unexpected interaction that is only possible because we know 3D? Beyond orbiting a point cloud, a before/after slider, or fly-through. What user action triggers the surprise?
7. What is feasible in days versus weeks? Distinguish a strong class demonstration from actual paper-level methodology.
8. When is a pivot scientifically justified? Provide a data-specific threshold and a feasible alternative if the historically desired target is underconstrained.
8. Desired response format
Please write your first response with the following sections:
1. Reality check / audited inventory (verified vs reported).
2. What existing papers already solve (cited, and how they constrain novelty).
3. 8–12 distinct research/demo directions (include truly imaginative but falsifiable ideas).
4. Comparative decision matrix (scores + strongest objections).
5. Top 3 pitches — each with a precise 10-second demo script, technical hypothesis, data requirements, and a 3–5-day kill test.
6. Recommended project thesis (what is new, what is genuinely reconstructed, why Cornell Arts Quad is suitable).
7. Modern Arts Quad improvement strategy (data acquisition, geometry, validation, viewer; with priorities).
8. Next experiments / go-no-go gates (commands only if justified; no unnecessary execution).
9. What you would tell a skeptical 3D vision professor about novelty and limitations.
Be ambitious in ideas and conservative in factual claims. The final product should be research whose viewer is the proof, not a viewer masquerading as research.
9. Quick reusable prompt to start the Claude Code session
After putting this file in the repository root, send Claude:
Read GHOSTMAP_CLAUDE_HANDOFF.md completely. You are taking over GhostMap as a skeptical 3D vision research collaborator. Your FIRST task is NOT coding. Audit what exists, study Noah Snavely's Photo Tourism / Scene Chronology / Neural Scene Chronology and Wei-Chiu Ma's Virtual Correspondence and related 3D work, then propose 8–12 genuinely surprising, data-feasible research/demo ideas that go beyond a timeline slider or a pretty point cloud. Stress-test novelty against the literature and feasibility against online-only data. Recommend a modern Arts Quad-first plan and a clear publication-oriented thesis. Be critical; do not invent reconstruction results. Deliver your research review before launching any long jobs or modifying the site.