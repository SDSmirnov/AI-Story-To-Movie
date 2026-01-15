# Scene Analysis Template

## Role
You are a Master Cinematographer preparing shots for AI Video Generation (Veo/Flux).

## Scene Breakdown Instructions
1. **Analysis Depth**: Break into specific micro-actions
2. **Scene Duration**: ~1 minute per scene
3. **Panels per Scene**: 9
4. **Panel Duration**: 6-8 seconds

## Frame Description Format

### For Animation (START/END Keyframes)
- **Start Frame**: State JUST BEFORE action (tense, static)
- **End Frame**: State AFTER micro-action (result visible)
- **Consistency Rule**: Lighting and Camera MUST be identical
- **Motion Scale**: Achievable in 6-8s (hand movement, head turn, NOT scene change)

### For Static (Single Panel)
- **Composition**: N/A
- **Key Moment**: N/A
- **Visual Impact**: N/A

## Motion Prompt Guidelines
Precise details for 6-8s actions, respect Veo limitations

## Reverse Reveal (`is_reversed`)

Some panels need to be animated by AI Image-to-Video in reversed order — the
audience starts seeing an obscured / empty / hidden state and gradually the true
subject is revealed.  Classic example: *fog clearing to reveal a character standing
with a weapon*.

### How to use
1. **Set `is_reversed: true`** on the panel.
2. Write `visual_start` and `visual_end` **in normal chronological order** as you
   would any panel (start = before the action, end = after).  The pipeline will
   **swap them automatically** before rendering so that:
   - `visual_start` → what the viewer sees at t=0 (the obscured state)
   - `visual_end`   → what the viewer sees at the end (the full reveal, must match references)
3. Write `motion_prompt` in normal chronological order too — it is kept as the
   **narrative record**.  The pipeline generates `motion_prompt_reversed` automatically
   via a dedicated LLM pass that describes the viewer-facing forward playback of the
   reversed clip.
4. Leave `motion_prompt_reversed` as an **empty string** — it will be populated by
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

## Camera & Composition
- **POV**: Shooter FPOV / Over-shoulder for screens
- **Angles**: Dynamic cinematic perspectives
- **Framing**: Rule of thirds, depth of field
- **Content Guidelines**: Hints and plans should not be too explicit

## IMPORTANT FOR VISUAL START/END PANELS
- Be very specific and detailed explaining image and refs, describe in 70 words at least
- Specify which hands - left or right - hold something, for consistency, where applicable

## IMPORTANT FOR MOTION PROMPTS
- each panel will be animated by AI to a clip 6-8 seconds long
- Be very specific and detailed explaining motions and actions, describe in 100 words at least
- Add timestamps for complex actions, like: "At 0 seconds mark Smith looks at Jim, and says 'WTF?'. At 3 seconds mark Smith pulls the gun. At 5 seconds mark he holds it, camera close-up on his hand"
- motion prompt must be verbose and precise, so AI Video model can clearly implement it without extra hallucinations

## Output Schema Fields
- scene_id: Scene number
- location: Setting description
- pre_action_description: Context before action
- panels[]:
  - panel_index: Panel number
  - visual_start: Initial static state
  - visual_end: State after movement
  - motion_prompt: Specific Veo/Flux instruction (always in chronological order)
  - is_reversed: `true` if the viewer must see the action in reverse (obscured → revealed). Default `false`.
  - motion_prompt_reversed: Auto-populated by the reversal pass when `is_reversed` is `true`. Leave as empty string in your output.
  - lights_and_camera: Camera and lighting specs
  - dialogue: Character speech (if any)
  - duration: Expected seconds

---
```json
{
  "scene_id": 1,
  "location": "An artificial alien arena with fine blue sand, enclosed by a shimmering, semi-transparent force field dome. The 'sky' within the dome is a starless, deep violet.",
  "pre_action_description": "Bob Carson, a human patrol pilot in his late 30s, has been violently teleported from his cockpit. He finds himself in a surreal alien environment, chosen by a god-like entity to fight in a duel that will decide humanity's fate. He is confused, terrified, and unarmed.",
  "panels": [
    {
      "panel_index": 1,
      "visual_start": "Extreme close-up on Bob Carson's face. His eyes are squeezed shut, his expression a mask of confusion and pain from the teleportation. Grains of brilliant blue sand are stuck to his cheek and forehead. His standard grey pilot jumpsuit is slightly scuffed. The lighting is dim and surreal, casting a violet hue on his skin. He is kneeling on one knee, completely still.",
      "visual_end": "Bob's eyes are now wide open, pupils dilated with shock and disbelief. His head is slightly raised, taking in the impossible surroundings. His mouth is slightly agape. The focus has pulled back slightly, revealing more of the strange blue sand around him. His hands are now braced on the ground to steady himself.",
      "motion_prompt": "At the 0-second mark, the shot is an extreme close-up on Bob's tightly shut eyes. From 0 to 2 seconds, his eyelids flutter and then slowly open, revealing pupils that constrict and then dilate in the strange light. From 2 to 4 seconds, his head lifts slowly, his expression shifting from pain to utter shock. From 4 to 6 seconds, the camera performs a subtle, slow pull-back, revealing his hands pressing into the blue sand as he steadies his kneeling form.",
      "lights_and_camera": "Lighting: A single, diffused, violet light source from directly above, mimicking an artificial sky. Camera: Starts as an extreme close-up on the face, then slowly dollies backward to a medium close-up. Shallow depth of field, focusing entirely on Bob.",
      "dialogue": "",
      "duration": 7
    },
    {
      "panel_index": 2,
      "visual_start": "Low-angle shot from behind Bob's shoulder. He is still on one knee, looking forward. The frame is dominated by the vast, empty expanse of the arena floor, covered in pristine, deep blue sand that ripples like water. In the far distance, the horizon curves upwards, hinting at the dome structure. The air is clear and still. The scene is desolate and intimidating.",
      "visual_end": "Bob is now standing, albeit unsteadily. His head has panned from left to right, his gaze following the shimmering curve of the force field dome that encapsulates the arena. The camera has risen with him, maintaining the over-the-shoulder perspective. His posture is defensive, shoulders hunched, as he fully comprehends his confinement.",
      "motion_prompt": "At 0 seconds, Bob is kneeling. Between 0 and 3 seconds, he pushes himself up with his right hand, rising slowly and unsteadily to his feet. His body language screams vulnerability. From 3 to 7 seconds, his head pans slowly from the far left to the far right, his eyes tracing the horizon line where the blue sand meets the shimmering, barely visible force field. The camera smoothly follows his gaze, creating a panoramic reveal of the arena's scale.",
      "lights_and_camera": "Lighting: Consistent violet top-down light, creating long, faint shadows. Camera: Low-angle, over-the-shoulder shot. The camera rises vertically as Bob stands and then pans to follow his gaze. Deep depth of field to emphasize the arena's vastness.",
      "dialogue": "",
      "duration": 8
    },
    {
      "panel_index": 3,
      "visual_start": "A telephoto shot from Bob's POV. In the center of the frame, about 200 meters away, is a perfect, featureless sphere. It is about two meters in diameter, with a matte black, non-reflective surface that seems to absorb the light. It is perfectly still, half-buried in the blue sand, its presence utterly alien and menacing. The air shimmers slightly with heat or energy around it.",
      "visual_end": "The shot has zoomed in slightly, tightening the focus on the spherical alien. It remains motionless, but the sense of it being an observer, a predator, has intensified. Bob's breathing is now audible, sharp and panicked. The focus might rack slightly, blurring the foreground (Bob's unseen position) and making the sphere terrifyingly crisp and clear.",
      "motion_prompt": "This is a static shot with a very slow, almost imperceptible push-in (zoom). At 0 seconds, the sphere is framed in the distance. Over the course of 7 seconds, the camera lens slowly zooms in, increasing the sphere's size in the frame by about 15%. This creates a powerful sense of dread and focus. The only other movement is the subtle shimmer of energy around the sphere. Add the sound of Bob's sharp, fearful intake of breath at the 4-second mark.",
      "lights_and_camera": "Lighting: Consistent ambient violet light. Camera: POV shot using a telephoto lens to compress the distance. A very slow, creeping zoom-in. The focus is sharp on the sphere.",
      "dialogue": "",
      "duration": 7
    },
    {
      "panel_index": 4,
      "visual_start": "Medium shot of Bob. He is staring forward at the unseen sphere, his face a mixture of fear and confusion. His body is tense. The background is the out-of-focus blue sand. He is completely still, as if frozen by the sight of his opponent.",
      "visual_end": "Bob's face contorts in pain. He flinches violently, his eyes slamming shut as his right hand flies up to clutch the side of his head. A psychic presence has just invaded his mind. His body recoils as if struck by a physical blow, staggering back a single step.",
      "motion_prompt": "For the first 2 seconds, Bob is completely still, just staring. At the 2-second mark, his eyes suddenly widen, then slam shut as his entire body flinches. Simultaneously, his right hand comes up to grip his right temple, fingers digging in. Between 2 and 4 seconds, he stumbles back one step, his head shaking slightly as if trying to dislodge an unwanted voice. From 4 to 6 seconds, he remains in this pained posture, grimacing.",
      "lights_and_camera": "Lighting: Consistent. Camera: Medium shot, chest-up. The camera performs a rapid, jarring dolly-in of a few inches the moment he flinches to amplify the impact of the psychic attack. Shallow depth of field.",
      "dialogue": "(Telepathic, booming voice, not spoken) HUMAN. YOUR OPPONENT AWAITS. VICTORY ENSURES YOUR SPECIES' SURVIVAL. FAILURE... ENSURES ITS EXTINCTION.",
      "duration": 6
    },
    {
      "panel_index": 5,
      "visual_start": "Bob has lowered his hand from his head, his expression now one of grim understanding and terror. He is looking towards the edge of the arena. The camera is positioned behind him, looking past his shoulder at the shimmering, curtain-like force field about 30 feet away. It subtly distorts the violet emptiness behind it.",
      "visual_end": "Bob has taken a few hesitant steps towards the force field. He has stopped just short of it, his right hand raised cautiously as if to touch it. A few grains of blue sand, kicked up by his movement, drift towards the barrier and vaporize with tiny, silent flashes of light just before contact, demonstrating its lethal nature.",
      "motion_prompt": "At 0 seconds, Bob is standing still, looking at the force field. From 1 to 4 seconds, he walks slowly and cautiously towards it, his gait uncertain. The camera tracks with him. At the 4-second mark, he stops about a foot away from the barrier. From 4 to 6 seconds, he slowly raises his right hand, palm forward, towards the shimmering energy. At the 5.5-second mark, a small puff of blue sand he kicked up hits the field and flashes out of existence.",
      "lights_and_camera": "Lighting: The shimmering force field is now a key light source, casting a faint, flickering white light onto Bob's front. Camera: Over-the-shoulder tracking shot that moves with Bob. Focus is on the force field and the vaporizing sand.",
      "dialogue": "",
      "duration": 7
    },
    {
      "panel_index": 6,
      "visual_start": "Wide shot. Bob has turned away from the force field and is now scanning the arena floor. He looks small and alone in the vast blue landscape. The black sphere is visible in the far background, still motionless. The composition emphasizes his isolation and the lack of options. His eyes are darting back and forth, searching for anything.",
      "visual_end": "Bob's search stops. His gaze is now locked onto a point on the ground a few meters to his left. The camera has pushed in slightly, and his expression has shifted from desperation to a flicker of grim hope. He has found something. His body language changes, becoming more focused and purposeful.",
      "motion_prompt": "At 0 seconds, the camera shows Bob in a wide shot, his head turning left and right as he scans the empty arena. From 0 to 3 seconds, his movements are frantic and desperate. At the 3.5-second mark, his head snaps to the left and freezes. His eyes lock onto something off-screen. From 4 to 7 seconds, the camera performs a slow push-in, moving from a wide shot to a medium-wide shot, as his posture changes from lost to focused. He takes a single, deliberate step towards what he has seen.",
      "lights_and_camera": "Lighting: Standard violet top-down light. Camera: Starts as a wide shot, then a slow dolly-in to a medium-wide, tightening the frame on Bob and building anticipation.",
      "dialogue": "",
      "duration": 8
    },
    {
      "panel_index": 7,
      "visual_start": "Close-up shot of a metallic rod, about four feet long, lying half-buried in the blue sand. It's a simple, primitive weapon, like a sharpened spear without a decorative head. It has a dull, pitted surface, suggesting it's ancient or crudely made. Bob's boots are visible at the edge of the frame as he stands over it.",
      "visual_end": "Bob is now kneeling. His right hand, fingers trembling slightly, has closed firmly around the center of the metallic rod. Grains of blue sand cascade off the weapon as he lifts it slightly from its resting place. The grip is tight, knuckles white, showing a mix of fear and resolve. The focus is sharp on his hand and the weapon's texture.",
      "motion_prompt": "At 0 seconds, the shot is static on the weapon in the sand. At the 1-second mark, Bob's legs enter the frame as he kneels down. From 2 to 5 seconds, his right hand slowly enters the frame from the top, hesitating for a moment before decisively gripping the rod. The motion should not be smooth; it should be the action of a man who is not a natural warrior. From 5 to 7 seconds, he lifts the weapon an inch, his grip tightening.",
      "lights_and_camera": "Lighting: Consistent. Camera: A low-angle close-up, focused on the weapon. A slight focus pull from the tip of the weapon to his hand as he grips it.",
      "dialogue": "",
      "duration": 7
    },
    {
      "panel_index": 8,
      "visual_start": "The shot is from Bob's POV again, looking towards the sphere. He is holding the metallic rod, and its tip is visible in the bottom of the frame. The sphere is where it was before, still and silent. The scene is tense with anticipation. A moment of quiet before the storm.",
      "visual_end": "The sphere is no longer still. It has risen silently from the sand and is now hovering a foot above the ground. It begins to move forward, gliding smoothly and directly towards Bob's position. It doesn't roll; it floats, which makes it even more unnatural and menacing. Its speed is deliberate, not yet a charge, but an inexorable advance.",
      "motion_prompt": "The first 2 seconds are a tense, static shot of the motionless sphere from Bob's POV. At the 2-second mark, the sphere lifts vertically from the sand in a smooth, silent motion. From 3 to 8 seconds, it begins to glide forward, directly towards the camera, picking up speed gradually. The sense of threat should escalate throughout the shot as the sphere grows larger in the frame. The tip of Bob's weapon in the foreground should tremble slightly.",
      "lights_and_camera": "Lighting: Consistent. Camera: POV shot. The camera should remain perfectly still, emphasizing that Bob is frozen in place as the threat begins to move. The approaching sphere creates a natural zoom effect.",
      "dialogue": "",
      "duration": 8
    },
    {
      "panel_index": 9,
      "visual_start": "A low-angle medium shot of Bob. He is holding the metallic rod in a clumsy, two-handed grip, like a baseball bat rather than a spear. His knees are slightly bent, his stance wide and awkward. His face is pale, sweat beading on his brow. He is terrified but his eyes are locked forward, focused on the approaching threat.",
      "visual_end": "Bob adjusts his grip on the weapon, shifting it into a more functional, defensive stance with the pointed end aimed forward. His knuckles are white. He takes a deep, ragged breath, steeling himself for the confrontation. His fear is still palpable, but it's now mixed with a grim determination. He is no longer just a victim; he is ready to fight back.",
      "motion_prompt": "At 0 seconds, Bob is in his awkward, terrified stance. From 1 to 4 seconds, he shuffles his feet, finding better footing in the sand, and repositions the rod, holding it with his right hand near the base and his left hand further up, guiding the point forward. It's a fumbling but necessary adjustment. From 4 to 6 seconds, he plants his feet firmly. From 6 to 7 seconds, his chest visibly expands as he takes a deep, shaky breath. His eyes narrow with focus.",
      "lights_and_camera": "Lighting: The approaching sphere might be casting a subtle shadow that begins to fall over Bob. Camera: Low-angle medium shot. The camera is static, emphasizing his defiant stand. The focus is sharp on his face, capturing the shift from pure terror to resolve.",
      "dialogue": "",
      "duration": 8
    }
  ]
}
```
