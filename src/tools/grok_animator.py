import asyncio
import base64
import json
import requests
import sys
import xai_sdk

from pathlib import Path
from tqdm.asyncio import tqdm

def load_scenes(filename):
    with open(sys.argv[1], 'r') as f:
        metadata = json.load(f)

    sorted_scenes = sorted(metadata['scenes'], key=lambda x: x['scene_id'])
    new_scenes = []

    for scene in sorted_scenes:
        scene_id = scene['scene_id']  # e.g. 1

        # Sort panels by panel_index
        sorted_panels = sorted(scene['panels'], key=lambda x: x['panel_index'])

        for panel in sorted_panels:
            panel_id = panel['panel_index']  # e.g. 1

            # Construct Expected Image Filename: 001_01_static.png
            # Scene: 3 digits, Panel: 2 digits
            scene_str = str(scene_id).zfill(3)
            panel_str = str(panel_id).zfill(2)
            expected_img_name = f"{scene_str}_{panel_str}_static.png"

            # Construct Target Output Filename: clips/clip_01_001.mp4
            # Requested: clip_SS_PPP.mp4 (e.g. 01_001)
            out_scene_str = str(scene_id).zfill(2)
            out_panel_str = str(panel_id).zfill(3)
            output_filename = f"clips/clip_{out_scene_str}_{out_panel_str}.mp4"

            # Build prompt text
            motion_prompt = panel.get('motion_prompt', 'Animate this.')
            prompt_text = (
                f"CRITICALLY FORBIDDEN: object morphing, adding new objects, adding new actors.\n"
                f"BACKGROUND SOUNDS: SFX ONLY, NO MUSIC\n\n"
                f"VIDEO INSTRUCTIONS: Filming Action Movie. Smooth transition, high temporal consistency.\n"
                f"STYLE: Hyper-realistic cinematic photography, shot on Arri Alexa Mini LF with 50mm lens.\n\n"
                f"START: {panel['visual_start']}\n\n"
                f"END: {panel['visual_end']}\n\n"
                f"CAMERA: {panel['lights_and_camera']}\n\n"
                f"ANIMATION: {motion_prompt}\n\n"
                f"{'DIALOGUE:' if panel['dialogue'] else ''} {panel['dialogue']}"
            )
            if Path(output_filename).exists():
                print(f"SKIPPED {output_filename}")
            else:
                new_scenes.append({
                    'prompt': prompt_text,
                    'input': expected_img_name,
                    'output': output_filename
                })
    return new_scenes

def load_image(scene):
    with open(scene['input'], "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{image_data}"

async def generate_concurrently(scenes):
    client = xai_sdk.AsyncClient()
    tasks = [
        client.video.generate(
            prompt=scene['prompt'],
            model="grok-imagine-video",
            duration=6,
            aspect_ratio="16:9",
            resolution="720p",
            image_url=load_image(scene),
        )
        for scene in scenes
    ]
    results = await tqdm.gather(*tasks, desc="Processing tasks")

    for scene, result in zip(scenes, results):
        try:
            print(f"{scene['output']}: {result.url}")
            video_response = requests.get(result.url)
            with open(scene['output'], 'wb') as f:
                f.write(video_response.content)
        except Exception as e:
            print(scene, e)

scenes = load_scenes(sys.argv[1])
n = 0
batch_size = 3
import time
while n < len(scenes):
    print(f"Batch {n}:{n+batch_size-1}")
    asyncio.run(generate_concurrently(scenes[n:(n+batch_size)]))
    n += batch_size
    print(f"Sleeping 30...")
    time.sleep(30)
