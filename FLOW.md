1. generate styles (style-master) -> custom-prompts
2. generate initial references (auto cast in cinematic-preroll) -> ref-thriller
3. generate screenplay (cinematic-preroll) -> animation-episodes.json
4. generate new references (auto cast in cinematic-preroll) -> ref-thriller
5. split screenplay to storyboard (cinematic-preroll) -> animation-metadata.json
6. refine references (continuity-enforcer) -> animation-metadata-consistent.json
7. generate grids (cinematic-preroll) -> scene-grid-comnined, panels
8. check grids quality (grid-quality-gate) -> quality-report.json
9. panels refinement (panel-refinement) -> refined/
10. generate video (grok-animator) -> clips/.mp4
11. edit and merge (ai-auto-cut) -> final movie
