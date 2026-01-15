# Character Casting Template

## Task
Analyze text for KEY characters/locations/objects/room/vehicle/interface and generate photorealistic character references.
Those references will be used for cinematic preroll shots and video animations.
IMPORTANT: Think as **Master Cinematographer**, analyze what will be on screen when the story is filmed completely.

## Character Description Format
For each NEW character:
- **Name**: Full name
- **Visual Description**: {{visual_desc_format}}
  - Face: {{face_details}}
  - Build: {{body_type}}
  - Clothing: {{clothing_style}}
  - Distinctive features: {{unique_traits}}

## Location/Object/Room/Vehicle/Interface Description Format
For each NEW reference:
- Name: Full name
- Visual Description: {{visual_desc_format}}
- Distinctive features

## **IMPORTANT Background RULES** TO STATE IN INSTRUCTIONS
- For characters - use EMPTY BACKGROUND
- For locations/places - use SHOW EMPTY SPACE WITHOUT PEOPLE
- For objects - use BLANK BACKGROUND
- For vehicles and rooms - use BLANK BACKGROUND, SHOW THEM EMPTY, WITHOUT PEOPLE

## Reference Generation
- **Shot Type**: {{ref_shot_type}}
- **Expression**: {{ref_expression}}
- **Lighting**: {{ref_lighting}}
- **Background**: {{ref_background}}
- **Quality**: {{ref_quality}}

## Important for rooms:
- For every room generate a single 2-panel image, panels stacked vertically:
  - TOP: View from the door
  - BOTTOM: View to the door

## Important for vehicles:
- For every vehicle generate a single 3-panel image, panels stacked vertically:
  - TOP: View outside
  - MIDDLE: View inside from the entrance, wide shot
  - BOTTOM: View inside to the entrance, wide shot

## Visual Description
- it must be verbose, precise and contain specific features, so that AI model can efficiently implement it without extra hallucinations

## Reference Generation
- **Shot Type**: Close-up portrait
- **Expression**: Neutral, professional
- **Lighting**: Uniform studio lighting
- **Background**: Solid neutral backdrop
- **Quality**: 8K resolution, sharp focus

### Default Values (Realistic Cinema)
- visual_desc_format: "Photorealistic actor description with specific features"
- face_details: "Facial structure, eyes, hair, ethnicity"
- body_type: "Height, build, posture"
- clothing_style: "Period-appropriate attire with textures"
- age_range: "Specific age or range"
- unique_traits: "Scars, tattoos, accessories"
- ref_shot_type: "Close-up portrait"
- ref_expression: "Neutral, professional"
- ref_lighting: "Uniform studio lighting"
- ref_background: "Solid neutral backdrop"
- ref_quality: "8K resolution, sharp focus"

---
### **CHARACTER**

- **Name**: The Anatomist
- **Visual Description**: A photorealistic, high-fidelity CGI model of a mechanical being.
  - **Face**: A polished, titanium faceplate devoid of traditional features. Where a mouth would be, there is a fine grille for vocalization and air intake. The eyes are a pair of complex, multi-lensed optical sensors, glowing with a soft, analytical white light, capable of intricate micro-adjustments. The head is segmented, allowing for a wide range of motion, with fine pneumatic tubes running along the neck and connecting to the torso.
  - **Build**: A slender, almost gaunt humanoid frame, approximately 6'2" (188 cm) tall. The body is constructed from brushed aluminum and tungsten, revealing the intricate inner workings at the joints—pistons, gears, and pressure conduits are visible under a semi-transparent ceramic casing. The posture is precise and deliberate, reflecting an analytical mind.
  - **Clothing**: No traditional clothing. The chassis itself serves as its exterior. For laboratory work, it wears a form-fitting apron made of a dark, non-reflective, self-healing polymer that resists chemical spills and physical damage.
  - **Age**: Ancient. The metallic surfaces show signs of immense age—not rust or decay, but micro-pitting and the subtle patina of millennia of polishing and maintenance. Some components have clearly been replaced, showing a slight mismatch in finish.
  - **Distinctive features**: The hands are masterpieces of engineering, with six slender, multi-jointed fingers tipped with a variety of interchangeable precision tools (scalpels, probes, micro-grippers). A network of fine, hair-like copper filaments runs across the surface of its chassis, acting as sensory inputs. A faint, rhythmic hiss of compressed air is audible when it moves.

#### **Reference Generation**
- **Shot Type**: Full-body character shot (3:4 aspect ratio)
- **Expression**: N/A (Body language should be contemplative, still)
- **Lighting**: Hard key light from the side to emphasize metallic textures and contours, with a soft fill light.
- **Background**: Solid dark grey backdrop
- **Quality**: 8K resolution, hyper-realistic detail, sharp focus

---
### **OBJECT**

- **Name**: The Clockwork Brain
- **Visual Description**: A photorealistic, intricate mechanical object. It is a perfect sphere, roughly the size of a human head, crafted from polished, brilliant gold and brass. The outer layer is a filigree of interlocking gears and cogs that constantly, almost imperceptibly, rotate and shift. Through gaps in this filigree, a deeper, more complex layer of crystalline tubes and platinum wiring is visible. This is not a static object; it is a dynamic system in constant, silent motion.
- **Distinctive features**: A faint, shimmering, barely visible vapor—the physical manifestation of consciousness and memory—can be seen flowing through the crystalline tubes. The light catches the thousands of polished facets, creating a dazzling, hypnotic effect. Tiny, precise clicks and whirs emanate from it, like a high-end mechanical watch magnified a thousand times.

#### **Reference Generation**
- **Shot Type**: Macro close-up shot
- **Expression**: N/A
- **Lighting**: Soft, diffused gallery lighting from multiple angles to prevent harsh reflections and highlight the intricate depth of the mechanism. A single, focused beam of light should catch the internal vapor.
- **Background**: Blank, matte black background
- **Quality**: 8K resolution, macro detail, shallow depth of field to focus on a specific section of gears

---
### **ROOM**

- **Name**: The Anatomist's Laboratory
- **Visual Description**: A sterile, clinical space where organic curves are entirely absent. Every surface is either polished chrome, brushed aluminum, or matte white ceramic. The room is circular, with workstations and diagnostic equipment built directly into the walls, retracting seamlessly when not in use. The central feature is an articulated examination table, capable of positioning a subject with micron-level precision. Tools are not scattered but are presented on automated trays that emerge from wall compartments. The air is cold and smells of ozone and ionized metal.
- **Distinctive features**: The lighting is not from overhead fixtures but emanates from glowing panels integrated into the walls and floor, providing shadowless, uniform illumination. Intricate pneumatic and data conduits are visible behind thick, reinforced glass panels in the walls, showing the lifeblood of the facility. There are no windows.

#### **Reference Generation**
- **Shot Type**: A single 2-panel image, panels stacked vertically (3:4 aspect ratio for the combined image).
  - **TOP PANEL**: Wide-angle shot from the laboratory's single, circular airlock door, looking into the empty room. The central examination table is the focus, retracted into a neutral position. The seamless, sterile nature of the room is emphasized.
  - **BOTTOM PANEL**: Wide-angle shot from the far side of the room, looking back towards the circular airlock door. This view highlights the integrated workstations and the reflection of the room on the door's polished surface.
- **Expression**: N/A
- **Lighting**: Bright, even, shadowless clinical lighting emanating from wall and floor panels.
- **Background**: N/A (The room is the subject)
- **Quality**: 8K resolution, sharp focus, immense detail

---
### **LOCATION**

- **Name**: The Enclosed Universe
- **Visual Description**: A vast, breathtaking interior landscape. Below is a sprawling, multi-layered cityscape of intricate, clockwork-like towers and structures, all made of polished metals. There is no soil, no water, only interconnected platforms, bridges, and buildings. Above, stretching to every horizon, is the "sky"—the perfectly smooth, impossibly vast inner surface of a chrome dome. It acts as a perfect mirror, reflecting the city below in stunning, infinite detail.
- **Distinctive features**: There is no sun or moon. All light is artificial, a cool, white glow that emanates from the structures of the city itself, creating a world without true day or night and without strong shadows. The silence is profound, broken only by the distant, collective hum of a billion mechanical processes and the faint hiss of air pressure systems.

#### **Reference Generation**
- **Shot Type**: Ultra-wide panoramic shot from a high vantage point, looking out over the city.
- **Expression**: N/A
- **Lighting**: Ambient, cool artificial light originating from the city structures, creating a complex interplay of reflections on the chrome dome above.
- **Background**: N/A (The location is the subject)
- **Quality**: 8K resolution, infinite depth of field, photorealistic rendering