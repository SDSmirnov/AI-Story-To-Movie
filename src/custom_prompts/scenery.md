```markdown
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
  - motion_prompt: Specific Veo/Flux instruction
  - lights_and_camera: Camera and lighting specs
  - dialogue: Character speech (if any)
  - duration: Expected seconds

---
### Scene 1
- **scene_id**: 1
- **location**: A sterile, clinical laboratory inside a chrome dome.
- **pre_action_description**: The scientist, a mechanical being, has prepared his tools for the ultimate experiment: a self-dissection of his own clockwork brain to understand the nature of consciousness before the universe reaches a final, silent equilibrium. The air is still, the moment heavy with philosophical weight.
- **panels**:
  - **panel_index**: 1
    **visual_start**: A first-person view looking down at a polished titanium tray. On it, a set of impossibly precise and delicate tools are arranged in perfect order. They look like a cross between surgical instruments and a watchmaker's kit. The scientist's own hands, articulated chrome fingers with brass joints, are visible at the bottom of the frame, motionless above the tray. The reflection of sterile overhead lights gleams on every metallic surface.
    **visual_end**: The scientist's right hand has moved, its chrome fingers now hovering directly over a slender, pen-like tool with a fine, vibrating tip. The other tools remain untouched. The fingers are poised just a millimeter above the tool, the decision made, the action about to be committed. The reflection in the tray warps slightly with the hand's new position. The left hand remains still, resting on the edge of the table.
    **motion_prompt**: At 0 seconds, the camera holds a steady first-person view of the tool tray. At the 2-second mark, the scientist's right hand begins to move slowly and deliberately from the bottom of the frame. The motion is smooth, without any hesitation, showcasing the character's resolve. The chrome fingers drift over the other instruments before coming to a stop directly above the target tool at the 5-second mark. The fingers spread slightly, preparing to grasp it. The shot holds for the remaining seconds, building tension.
    **lights_and_camera**: FPOV. Bright, shadowless, clinical lighting from an overhead source. Macro focus on the tools, with the scientist's hands in the foreground having a shallow depth of field.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 2
    **visual_start**: The scientist's right hand is poised over the slender tool. His chrome fingers are slightly open, ready to grasp. The focus is sharp on the intricate design of his knuckles and the polished surface of the instrument below. The background is a soft blur of the metallic laboratory.
    **visual_end**: The scientist's right hand has now securely grasped the tool. His fingers are wrapped firmly around its textured handle. He has lifted it just a centimeter off the tray, its fine tip catching the overhead light. The movement is precise, without a single sound other than the faint, almost imperceptible whir of the joints in his hand. The empty space on the tray where the tool once lay is now starkly visible.
    **motion_prompt**: Starting at 0 seconds, the shot is static. At the 1-second mark, the chrome fingers of the right hand descend with mechanical precision. At 2 seconds, they make contact with the tool, wrapping around it smoothly. From 3 to 5 seconds, the hand lifts the tool vertically, clearing the tray. The motion is incredibly stable, like a piece of high-tech machinery. For the final seconds, the hand holds the tool perfectly still in mid-air, allowing the viewer to appreciate its delicate and complex design.
    **lights_and_camera**: Extreme Close-Up (ECU) on the hand and tool. Rack focus from the fingertips to the tool's tip as it is lifted. Lighting remains clinical and bright.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 3
    **visual_start**: The FPOV shot now looks up from the tray towards a large, perfectly polished chrome panel on the wall, which acts as a mirror. The reflection shows the upper torso of the mechanical scientist. His head is a smooth, metallic dome, with optical sensors for eyes that glow with a soft, analytical blue light. The right hand holding the tool is just coming into the bottom of the reflected view.
    **visual_end**: The scientist's reflection is now fully centered. He has raised the tool-wielding right hand so it is level with his head in the reflection. He appears to be looking at his own reflection, his optical sensors unblinking. It is a moment of final contemplation before the irreversible act. The tool's tip gleams menacingly close to the reflected cranium.
    **motion_prompt**: At 0 seconds, the camera begins a slow, deliberate tilt upwards from the tool tray to the reflective wall panel. The tilt takes 3 seconds, smoothly revealing the scientist's reflection. From the 3-second mark to the 6-second mark, the scientist's right arm, holding the tool, rises into the frame and stops when the tool is parallel with his temple in the reflection. The reflection's gaze is steady, focused, and intense. The shot holds this tense composition for the final second.
    **lights_and_camera**: FPOV with a slow vertical tilt. The reflection should be crystal clear, with no distortion. The depth of field is deep, keeping both the reflection and the edges of the chrome panel in focus.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 4
    **visual_start**: A tight, over-the-shoulder shot. We see the back of the scientist's metallic head and his right hand bringing the slender, vibrating tool towards a nearly invisible seam just above where an ear would be on a human. The tool is an inch away. The focus is on the tip of the tool and the polished surface of the cranium.
    **visual_end**: The tip of the tool has made contact with the seam on the scientist's head. There is no visible damage, but its purpose is clear. The scientist's chrome fingers are tensed slightly around the tool's handle, applying minimal but precise pressure. The rest of his body is perfectly still.
    **motion_prompt**: The shot starts static at 0 seconds, with the tool poised. Over the course of 4 seconds, the scientist's right hand moves forward with microscopic precision, closing the final inch of distance between the tool and his head. The movement is incredibly slow and controlled. At the 4-second mark, the tool makes contact. There is a very subtle vibration effect from the tool upon contact. The camera holds this point of contact for the remaining 3 seconds, emphasizing the critical, irreversible nature of the action.
    **lights_and_camera**: Over-the-shoulder shot, tight framing. Macro focus on the point of contact. The lighting creates a sharp, thin highlight along the tool and the cranial seam.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 5
    **visual_start**: An extreme close-up on the point of contact. The tool's vibrating tip is pressed against the hairline seam on the polished metal cranium. The metal is seamless and perfect.
    **visual_end**: A thin, precise incision has appeared along the seam. A faint wisp of pressurized air, shimmering like heat haze, escapes from the newly created opening. The tool has traced a quarter of a circle, leaving a perfectly cut line in its wake. The sound is a barely audible, high-frequency hiss.
    **motion_prompt**: At 0 seconds, the shot is a static macro view. At the 1-second mark, the tool begins to move, its tip glowing with a subtle energy. From 1 to 6 seconds, it glides smoothly along the circular seam, cutting the metal. The camera follows the tip of the tool. As it cuts, a minute gap is created, and a shimmering vapor, representing the escaping compressed air, is released. The motion is fluid and exact. At 6 seconds, the tool stops, having completed a section of the cut.
    **lights_and_camera**: ECU/Macro shot. The lighting needs to be precise to catch the shimmering effect of the escaping air. A slight rack focus follows the cutting tip.
    **dialogue**:
    **duration**: 6
  - **panel_index**: 6
    **visual_start**: The tool has finished tracing a perfect circle on the side of the scientist's head. The right hand moves the tool away, out of frame. The left hand, previously unseen in this proximity, comes into frame, its chrome fingertips approaching the newly cut circular plate.
    **visual_end**: The fingertips of the left hand are now pressed against the circular plate. Tiny, almost invisible micro-suction cups on the fingertips have activated, gripping the plate. The plate has been lifted by a few millimeters, breaking the final seals. A more significant, but still controlled, plume of shimmering air escapes from the gap.
    **motion_prompt**: The shot begins with the completed incision. At 0 seconds, the cutting tool zips out of the frame. At the 1-second mark, the scientist's left hand enters the frame from the bottom left. The fingers are slightly curled. From 2 to 4 seconds, the hand moves carefully until its fingertips align perfectly with the cut plate. At 5 seconds, the fingers press down gently, and a subtle light effect indicates the suction has engaged. At 6 seconds, the fingers lift, pulling the plate up and away from the cranium just slightly.
    **lights_and_camera**: Close-up shot, angled to see the gap opening. The lighting should highlight the escaping pressurized air against the dark, intricate machinery that is about to be revealed.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 7
    **visual_start**: The scientist's left hand has a firm grip on the circular cranial plate, which is lifted just a few millimeters from the opening. Through the gap, we see a tantalizing glimpse of impossibly complex, moving golden clockwork machinery, bathed in a soft internal light.
    **visual_end**: The left hand has fully removed the plate and is moving it out of frame. The opening is now completely exposed, revealing the scientist's brain: a breathtakingly intricate sphere of spinning golden gyroscopes, interlocking gears, and crystalline conduits through which shimmering currents of air flow like water. The machinery whirs with a soft, harmonious sound.
    **motion_prompt**: At 0 seconds, the shot holds on the partially opened cranium. From 1 to 4 seconds, the left hand lifts the plate clear of the head and moves it steadily downwards and out of the frame. As the plate moves, the camera performs a slow push-in, moving into the opening to get a clearer view of the clockwork brain inside. The reveal is gradual and awe-inspiring. From 5 to 7 seconds, the camera holds on the fully revealed, functioning mechanical brain.
    **lights_and_camera**: Close-up, slow push-in. The primary light source now comes from within the brain itself—a warm, golden glow that contrasts with the lab's cold, white light.
    **dialogue**:
    **duration**: 7
  - **panel_index**: 8
    **visual_start**: A full-frame, breathtaking macro shot of the clockwork brain in operation. Miniature golden gears spin in complex patterns. Tiny pistons pump rhythmically. Through transparent, crystal-like tubes, we can see patterns of light and shimmering air—the physical manifestation of thought and consciousness—flowing and eddying.
    **visual_end**: The camera has pushed in even closer on a specific region of the brain. We see a cluster of gears and levers suddenly shift their pattern, a cascade of motion rippling through the area. The flow of shimmering air through the conduits intensifies and changes direction, representing a specific thought or memory being accessed by the scientist.
    **motion_prompt**: This is a pure visual exploration. At 0 seconds, the camera is in a wide macro shot of the entire brain mechanism. From 0 to 5 seconds, it executes a very slow, smooth drift inwards towards a particularly active-looking cluster of machinery. The focus racks gently to follow the intricate layers of the clockwork. At the 5-second mark, a specific, synchronized mechanical action occurs in the focus area—a series of levers flip, causing the airflow to visibly reroute. This is the brain actively thinking about its next move.
    **lights_and_camera**: Extreme Macro shot. The lighting is entirely internal, emanating from the golden machinery. Use a very shallow depth of field to emphasize the infinite complexity and layers of the mechanism.
    **dialogue**:
    **duration**: 8
  - **panel_index**: 9
    **visual_start**: The shot pulls back slightly to a close-up of the exposed brain. The scientist's right hand, now holding a different tool—a delicate probe with a multi-lensed scope at its tip—enters the frame. The probe is held motionless, inches away from the whirring golden machinery.
    **visual_end**: The probe has moved closer, its tip now hovering just millimeters above a specific spinning gyroscope in the clockwork brain. The scientist is about to begin the diagnostic, to probe the very nature of his own consciousness. The shot freezes on this moment of ultimate scientific intrusion and self-discovery, the gleaming probe ready to touch the soul in the machine.
    **motion_prompt**: At 0 seconds, the shot shows the exposed brain. At the 2-second mark, the diagnostic probe, held by the right hand, enters the top right of the frame. The movement is slow, steady, and immensely careful. From 3 to 7 seconds, the probe advances towards the brain, its tip navigating the complex moving parts without touching them. It comes to a final, suspenseful halt just above a critical-looking component at the 7-second mark. The scene ends here, on the precipice of the experiment's true beginning.
    **lights_and_camera**: Close-up shot. The focus is on the tip of the probe, with the complex, moving brain just beyond it in a beautiful, soft focus. The probe reflects the golden light of the brain's machinery.
    **dialogue**:
    **duration**: 8
```