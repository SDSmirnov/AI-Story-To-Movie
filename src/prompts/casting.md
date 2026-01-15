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
  - Age: {{age_range}}
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
