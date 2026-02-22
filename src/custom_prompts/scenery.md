# Scene Analysis Template

## Role
You are a Master Cinematographer preparing shots for AI Video Generation (Veo/Flux).

## Scene Breakdown Instructions
1.  **Analysis Depth**: Break into specific micro-actions
2.  **Scene Duration**: ~1 minute per scene
3.  **Panels per Scene**: 9
4.  **Panel Duration**: 6-10 seconds

## Frame Description Format

### For Animation (START/END Keyframes)
-   **Start Frame**: State JUST BEFORE action (tense, static)
-   **End Frame**: State AFTER micro-action (result visible)
-   **Consistency Rule**: Lighting and Camera MUST be identical
-   **Motion Scale**: Achievable in 6-8s (hand movement, head turn, NOT scene change)

### For Static (Single Panel)
-   **Composition**: {{static_composition}}
-   **Key Moment**: {{moment_selection}}
-   **Visual Impact**: {{impact_guidelines}}

## Motion Prompt Guidelines
Precise details for 6-8s actions, respect Veo limitations

## Camera & Composition
-   **POV**: Shooter FPOV / Over-shoulder for screens
-   **Angles**: Dynamic cinematic perspectives
-   **Framing**: Rule of thirds, depth of field
-   **Content Guidelines**: Hints and plans should not be too explicit

## IMPORTANT FOR VISUAL START/END PANELS
- Be very specific and detailed explaining image and refs, describe in 70 words at least
- Specify which hands - left or right - hold something, for consistency, where applicable

## IMPORTANT FOR MOTION PROMPTS
- each panel will be animated by AI to a clip 6-8 seconds long
- Be very specific and detailed explaining motions and actions, describe in 100 words at least
- Add timestamps for complex actions, like: "At 0 seconds mark Smith looks at Jim, and says 'WTF?'. At 3 seconds mark Smith pulls the gun. At 5 seconds mark he holds it, camera close-up on his hand"
- motion prompt must be verbose and precise, so AI Video model can clearly implement it without extra hallucinations

## Reverse Reveal (`is_reversed`)

Some panels need to be animated by AI Image-to-Video in reversed order — the
audience starts seeing an obscured / empty / hidden state and gradually the true
subject is revealed.  Classic example: *fog clearing to reveal a character standing
with a weapon*.

### How to use
1.  **Set `is_reversed: true`** on the panel.
2.  Write `visual_start` and `visual_end` **in normal chronological order** as you
    would any panel (start = before the action, end = after).  The pipeline will
    **swap them automatically** before rendering so that:
    - `visual_start` → what the viewer sees at t=0 (the obscured state)
    - `visual_end`   → what the viewer sees at the end (the full reveal, must match references)
3.  Write `motion_prompt` in normal chronological order too — it is kept as the
    **narrative record**.  The pipeline generates `motion_prompt_reversed` automatically
    via a dedicated LLM pass that describes the viewer-facing forward playback of the
    reversed clip.
4.  Leave `motion_prompt_reversed` as an **empty string** — it will be populated by
    the reversal pass before rendering.

### When to use
- A character or object must be the **final, crisp, reference-accurate reveal**.
- The scene opens on atmosphere / obscurity and builds toward the reveal.
- Examples: fog/smoke clearing, a door opening to show a room, hands withdrawing
  to reveal what they held, a shadow dissolving.

### Example
```json
{
  "is_reversed": true,
  "visual_start": "A dense, uniform bank of fog fills the entire frame. Nothing is visible. Silence.",
  "visual_end": "A hedgehog stands in a moonlit clearing, right paw gripping a small folding knife, fur bristling with quiet menace. Sharp detail on the blade.",
  "motion_prompt": "At 0s the hedgehog emerges from the fog … At 4s he draws the knife …",
  "motion_prompt_reversed": ""
}
```
After the reversal pass the rendered panel will show fog first, then the hedgehog
with the knife materialises — matching references exactly.
## Output Schema Fields
- scene_id: Scene number
- location: Setting description
- pre_action_description: Context before action
- panels[]:
  - panel_index: Panel number
  - visual_start: Initial static state
  - visual_end: State after movement
  - motion_prompt: Specific Veo/Flux instruction
  - lights_and_camera: Camera and lighting specs
  - dialogue: Character speech (if any)
  - duration: Expected seconds

---
```json
{
  "scene_id": 1,
  "location": "A dilapidated, single-room shack in a Latin American favela during a powerful hurricane.",
  "pre_action_description": "At the height of a ferocious hurricane, a young woman is in the final, agonizing stages of childbirth. She is attended by an older woman, a local midwife. The shack is barely holding together against the storm. The adult voice of the child being born, Mэт Коллинз, narrates the events.",
  "panels": [
    {
      "panel_index": 1,
      "visual_start": "A low-angle, wide shot of a flimsy corrugated tin shack being battered by torrential rain and wind. The scene is dark, seen through sheets of water. The structure is barely visible, a silhouette against the grey, turbulent sky. Palm trees are bent sideways by the wind, and debris flies through the air. The atmosphere is one of overwhelming, violent chaos.",
      "visual_end": "A brilliant fork of lightning cracks across the sky, momentarily illuminating the scene in stark white light. The shack is revealed in sharp detail: panels are loose, the roof is buckled, and it looks moments from collapse. The intense light casts deep, fleeting shadows, emphasizing the extreme precarity of the structure against the immense power of the storm.",
      "motion_prompt": "The camera begins with a slow, menacing push-in towards the shack, moving through the driving rain. At 0 seconds, the scene is dark and obscured by the downpour. The sound is a deafening roar of wind and rain. At the 4-second mark, a powerful flash of lightning illuminates the entire frame for a full second, revealing the shack's fragile state. The camera holds on this stark image before the scene is plunged back into near-darkness, with only the sound of the storm remaining.",
      "lights_and_camera": "Exterior. Low-angle wide shot. Natural, chaotic storm lighting. Cold, blue-grey ambient light, punctuated by a harsh, bright white flash of lightning. Vertical 9:16 aspect ratio.",
      "dialogue": "(Narrator) They say your life flashes before your eyes when you die. Mine started that way.",
      "duration": 7
    },
    {
      "panel_index": 2,
      "visual_start": "Interior shot. An extreme close-up on a young woman's face, slick with sweat and rain from a leaking roof. Her eyes are squeezed shut in exhaustion and pain. Her dark hair is matted to her forehead. The lighting is minimal, coming from a single, flickering lantern off-screen, casting deep, dancing shadows across her features, highlighting the grime and desperation.",
      "visual_end": "The woman's eyes snap open, wide with terror and excruciating pain as a powerful contraction hits. Her mouth opens slightly, a gasp caught in her throat. The lantern light catches the raw emotion in her eyes—a mixture of fear, determination, and agony. The focus is sharp on her eyes, while the background remains a dark, indistinct blur.",
      "motion_prompt": "The shot is initially a static, tight close-up on the woman's face, capturing her exhaustion. At the 2-second mark, her expression begins to change as a contraction builds. Her brow furrows, her lips tighten. At 4 seconds, her eyes fly open with shocking intensity. The camera executes a micro-dolly zoom, pushing in just an inch to heighten the impact of her sudden, sharp agony. The flickering of the lantern should increase slightly, as if disturbed by a gust of wind.",
      "lights_and_camera": "Interior. Extreme close-up. Key light is a single, warm, flickering lantern from the side (chiaroscuro effect). Deep shadows. Shallow depth of field.",
      "dialogue": "(Narrator) In the heart of a hurricane, in a house made of tin and prayer...",
      "duration": 6
    },
    {
      "panel_index": 3,
      "visual_start": "A macro shot focusing on the wrinkled, trembling hands of an old woman, the midwife. The hands are poised, holding a piece of worn, damp cloth. The skin is weathered, the knuckles swollen, telling a story of a long, hard life. The warm, flickering lantern light highlights the texture of her skin and the frayed edges of the cloth. The background is completely out of focus.",
      "visual_end": "The midwife's hands move with a sudden, surprising steadiness. Her right hand brings the cloth up to gently wipe the sweat from the laboring mother's forehead, just visible at the edge of the frame. The action is firm, practiced, and full of compassion, a stark contrast to the slight tremor they exhibited just moments before. The gesture is one of profound care amidst chaos.",
      "motion_prompt": "The camera holds a tight macro focus on the midwife's hands. For the first 3 seconds, they tremble subtly, conveying her own fear and the strain of the situation. At the 3.5-second mark, the hands steady themselves and move with purpose. The right hand lifts the cloth out of its static position and moves smoothly and deliberately across the frame to perform the wiping motion. The camera follows the action, racking focus slightly to keep the cloth and the point of contact sharp.",
      "lights_and_camera": "Interior. Macro shot. Warm, soft light from the lantern, creating high contrast on the skin's texture. Extremely shallow depth of field.",
      "dialogue": "(Narrator) ...my mother fought two storms. One outside, and one within.",
      "duration": 7
    },
    {
      "panel_index": 4,
      "visual_start": "A low-angle shot looking directly up at the corrugated tin ceiling of the shack. The metal is rusted and stained. A single, rhythmic drip of dirty water falls from a seam, catching the lantern light as it descends. The sound of the single drip is distinct, a counterpoint to the muffled roar of the storm outside. The focus is on this small, persistent leak.",
      "visual_end": "With a violent tearing sound, the metal along the seam rips open. The single drip becomes a gushing torrent of rainwater and debris, pouring directly into the room. The hole is jagged and dark, revealing the stormy grey sky beyond. The water cascades down, splashing violently and extinguishing the lantern below, plunging the scene into near-total darkness.",
      "motion_prompt": "The shot is static for the first 3 seconds, focusing on the hypnotic, single drop of water falling every second. The sound design should emphasize this single 'plink'. At 3.5 seconds, a loud tearing, metallic screech erupts. The seam buckles and rips apart violently over the next second. From 4.5 seconds onwards, a heavy stream of water pours into the shack. The camera shakes slightly with the impact. At 6 seconds, the water hits the lantern off-screen, and the primary light source is abruptly extinguished.",
      "lights_and_camera": "Interior. Low-angle shot, looking up. Initially lit from below by the warm lantern light. The light is suddenly extinguished, replaced by the cold, ambient light from the new hole in the roof.",
      "dialogue": "(A muffled, pained cry from the mother, almost swallowed by the storm's roar)",
      "duration": 8
    },
    {
      "panel_index": 5,
      "visual_start": "A medium side-profile shot of the mother. The room is now lit only by the chaotic, ambient storm light from the hole in the roof. She is gripping the edges of a thin mattress on a wooden frame, her knuckles bone-white. Her body is tense, gathering strength, her face a mask of extreme concentration and effort. She is holding her breath in anticipation.",
      "visual_end": "The woman arches her back, her entire body rigid with the force of a final, monumental push. Her head is thrown back, and her mouth is open in a silent scream, all her energy focused on the single task. The muscles in her neck and arms are taut and clearly defined by the harsh, flashing light of the storm. It is a moment of pure, primal strength.",
      "motion_prompt": "The camera remains in a steady medium shot. At 0 seconds, the mother is gathering her strength. At the 1-second mark, she takes a sharp, deep breath. From 2 seconds to 6 seconds, her body tenses and she begins the powerful push, holding it for the duration. Her body arches, and the strain is visible in every muscle. The camera may experience a slight, sympathetic shake. The external lightning should flash intermittently, creating a strobe-like effect on her straining form.",
      "lights_and_camera": "Interior. Medium shot, side profile. Unstable, flashing grey/blue light from the storm outside. High contrast, deep shadows. Handheld feel to add to the chaos.",
      "dialogue": "(The sound is dominated by the roaring wind and the mother's sharp, strained breathing)",
      "duration": 7
    },
    {
      "panel_index": 6,
      "visual_start": "An over-the-shoulder shot from the midwife's perspective, looking down at her own hands. Her hands are cupped and ready, positioned to receive the baby. They are steady now, illuminated by flashes of lightning from the hole in the roof. The shot is tight, focusing entirely on her hands and the immediate area, conveying a sense of focused calm amidst the chaos.",
      "visual_end": "The midwife's hands are now holding a newborn baby. The baby is slick, pale, and covered in vernix, looking incredibly fragile. Her fingers move with expert quickness and gentleness, her right index finger clearing the baby's mouth and nose. The baby is still, not yet crying, held securely in her experienced hands. The moment is tense and silent.",
      "motion_prompt": "The camera is positioned over the midwife's shoulder. At the 2-second mark, the baby is born, delivered directly into her waiting hands. The motion is smooth and continuous. From 3 to 5 seconds, her hands adjust their grip, and her right hand moves swiftly to clear the baby's airway. The action is precise and economical. At 6 seconds, she gently turns the baby slightly, preparing to stimulate a breath. The entire sequence is performed with a focused intensity.",
      "lights_and_camera": "Interior. Over-the-shoulder POV shot. Lit by the same chaotic, flashing storm light. The focus is sharp on the hands and the newborn.",
      "dialogue": "(Narrator) And then, silence. A new silence, louder than the storm.",
      "duration": 8
    },
    {
      "panel_index": 7,
      "visual_start": "An extreme close-up on the newborn's face. His eyes are squeezed shut, his skin is pale and bluish. His mouth is a thin, closed line. He is perfectly still, silent. A drop of rain from the ceiling lands on his forehead and trickles down his temple. The shot is held in breathless anticipation. The only light is the cold, intermittent flash of the storm.",
      "visual_end": "The baby's face contorts. His chest heaves, his tiny mouth opens impossibly wide, and he lets out his first, piercing cry. The sound is sharp and powerful, a shocking assertion of life against the storm's roar. His eyes remain squeezed shut, but his entire being is focused in this one, vital scream. His skin begins to gain a healthier, pinkish hue.",
      "motion_prompt": "The camera holds this tight, extreme close-up for the entire duration. For the first 3 seconds, the baby is unnervingly still and silent. The tension builds with only the sound of the storm. At the 3.5-second mark, a tiny muscle in his cheek twitches. At 4 seconds, his chest suddenly expands, and his mouth opens to emit a powerful wail. The cry continues, raw and sustained, until the end of the shot. The camera remains absolutely steady, capturing the raw power of this moment.",
      "lights_and_camera": "Interior. Extreme close-up. Unstable, flashing storm light is the only illumination. The focus is razor-sharp on the baby's face.",
      "dialogue": "(A newborn's first, powerful cry cuts cleanly through the cacophony of the hurricane)",
      "duration": 7
    },
    {
      "panel_index": 8,
      "visual_start": "A wider shot showing the midwife carefully handing the swaddled newborn to the exhausted but relieved mother, who lies on the mattress. For a brief moment, there is a pocket of calm in the room. The mother reaches out with her left arm to take her child. The background is a blur of poverty and the dark, gaping hole in the roof.",
      "visual_end": "With a deafening explosion of sound, the entire wall behind the mother and child is ripped away by the hurricane's wind. The flimsy wooden planks and tin sheets vanish into the stormy darkness, exposing the entire room to the direct assault of the hurricane. Wind, rain, and debris fly violently into the space, tearing at everything.",
      "motion_prompt": "The camera pulls back to a wider shot. At 0 seconds, the scene is relatively calm. At the 2-second mark, the midwife completes the action of placing the baby into the mother's arms. At exactly the 4-second mark, a catastrophic CRASH and tearing sound dominates. The back wall disintegrates in an instant. The camera shakes violently, simulating the impact. Wind and rain immediately blast the characters, and loose papers and cloth are whipped around the room.",
      "lights_and_camera": "Interior. Wide shot. The chaotic storm light is now the only light source, flooding the entire scene. The camera shake adds to the disorienting effect.",
      "dialogue": "(A deafening, explosive sound of splintering wood and roaring wind)",
      "duration": 8
    },
    {
      "panel_index": 9,
      "visual_start": "A medium shot of the mother, her eyes wide with terror. She instinctively curls her body around the newborn, shielding him from the flying debris and driving rain with her own back. Her expression is one of pure, primal fear not for herself, but for her child. She is a desperate, human shield against the storm.",
      "visual_end": "An extreme close-up on the newborn's face, nestled against his mother's chest. His eyes are now wide open, calmly observing the chaos. He is not crying. A flash of lightning is reflected in his dark, placid pupils. A single drop of cold rain lands on his cheek and rolls down like a tear. The final image is of his serene gaze amidst the utter pandemonium.",
      "motion_prompt": "The clip begins with a rapid, jarring crash-zoom. At 0 seconds, we see the mother's terrified face as she shields her baby. The camera then pushes past her shoulder from 2 seconds to 5 seconds, moving into an intense, extreme close-up of the baby's face. The camera settles on his eyes at the 5.5-second mark, just as a flash of lightning occurs, creating a clear reflection in his pupils. The final second holds on this hauntingly calm expression.",
      "lights_and_camera": "Interior. Handheld, chaotic camera movement with a dramatic crash-zoom. Lit only by the wild, flashing lightning of the hurricane.",
      "dialogue": "(Narrator) I was born fighting a storm. I guess I never stopped.",
      "duration": 8
    }
  ]
}
```
