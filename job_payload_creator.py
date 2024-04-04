# job_payload_creator.py
from conversation import generate_scene
from audio import get_context
import json
import random
import config
import logging
import re
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Possible RENDER_MODE values
render_modes = ["Leonardo","Civitai","Prodia","Midjourney","Dalle"]
# render_modes = ["Civitai","Leonardo","Prodia"]

def create_job_payloads(structure_params, scene_descriptions, num_images_to_generate):
    logging.info("Creating job payloads...")
    job_payloads, prompts, scene_index = [], [], 0  # Initialize lists and scene index in one line

    scene_descriptions_list = scene_descriptions['Scene Description']

    # Condense shuffle operation
    [random.shuffle(values) for values in structure_params.values()]

    # SECTION 1
    try:
        logging.info(f"Loop started for: {num_images_to_generate}")

        # SECTION 1.1 Looping to generate all image required
        for index in range(num_images_to_generate):

            scene_index += 1

            # SECTION 1.2 Looping trough all render mode
            for render_mode in render_modes:

                # Set RENDER_MODE based on BROADCAST_MODE or RANDOM_MODE
                config.RENDER_MODE = render_mode if config.BROADCAST_MODE == 1 else (
                    random.choice(render_modes) if config.RANDOM_MODE == 1 else config.RENDER_MODE)

                # Determine which model IDs to load based on RENDER_MODE
                # Populating the model_ids dictionary since both 'IF' case will need it
                model_id_configs = {
                    "Prodia": config.PRODIA_MODEL_IDS,
                    "Civitai": config.CIVITAI_MODEL_IDS,
                    "Leonardo": config.LEONARDO_MODEL_IDS
                }
                model_ids = json.loads(model_id_configs.get(config.RENDER_MODE, config.LEONARDO_MODEL_IDS))

                # Select a scene
                scene_full = scene_descriptions_list[(scene_index - 1) % len(scene_descriptions_list)]

                # Trim the prompt to 850 characters
                scene = scene_full[:850]

                # SECTION 1.2.1 Behaviour when we run on Override Mode
                if config.OVERRIDE_MODE:
                    # SECTION 1.2.1 Behaviour when we run on Override Mode
                    prompt = re.sub("<SCENE>", scene, config.SCENE)
                    model_id, random_style = (random.choice(model_ids), random.choice(
                        json.loads(config.PRODIA_STYLES))) if config.RENDER_MODE == "Prodia" else (
                    config.OVERRIDE_MODEL, config.STYLE)
                else:
                    # SECTION 1.2.2 Behaviour when we run NOT in Override Mode
                    # Setting probability rate for each dictionary or default to 50%
                    probabilities_value = {
                        "Leonardo": config.LEONARDO_RATE,
                        "Prodia": config.PRODIA_RATE,
                        "Midjourney": config.MIDJOURNEY_RATE,
                        "Dalle": config.DALLE_RATE
                    }.get(config.RENDER_MODE, 0.5)

                    # Safely get the Prefix if the key exists, otherwise default to an empty list
                    environment_options = structure_params.get('Prefix', [])
                    environment = random.choice(
                        environment_options) if random.random() < probabilities_value and environment_options else ''

                    # Add the environment to the prompt as a prefix
                    prompt = f"{environment + ' ' if environment else ''}{config.FORCE_UNIVERSE + ' ' if config.FORCE_UNIVERSE else ''}{scene}"

                    # Add all the other key to the prompt
                    selected_options = {key: random.choice(value) for key, value in structure_params.items() if
                                        key != 'Prefix'}
                    prompt += ''.join(f", {value}" for key, value in selected_options.items() if
                                      random.random() < probabilities_value)

                    # Randomly select a style
                    styles = json.loads(config.PRODIA_STYLES if config.RENDER_MODE == "Prodia" else config.LEONARDO_STYLES)
                    random_style = random.choice(styles)

                    # Randomly select a model ids
                    model_id = random.choice(model_ids)

                # SECTION 1.3 End of the Override Mode, now processing the final rules
                # Add ratio directly in the prompt if midjourney
                prompt += " --fast --ar 9:16 --v 6" if config.RENDER_MODE == 'Midjourney' and config.IMAGE_HEIGHT > config.IMAGE_WIDTH else " --fast --ar 16:9 --v 6" if config.RENDER_MODE == 'Midjourney' else ""

                # Trim the prompt to 850 characters in case all our new additions have made it too long
                trimmed_prompt = prompt[:850]

                # TODO:
                # Now create the payload with the trimmed prompt
                ## FOR COMFY, this needs to do:                
                #payload = config.COMFY_PAYLOAD (COMFY_PAYLOAD is the comfy.json file)
                #payload[config.PROMPT_NODE]["inputs"]["text"] = prompt
                payload = create_api_specific_payload(model_id, trimmed_prompt, random_style)


                # logging.info(f"Render Mode: {config.RENDER_MODE} and loop mode {render_mode}")
                job_payloads.append(payload)
                # print(job_payloads)

                # Conclusion: As we loop all render mode only in Broadcast Mode, otherwise we break the loop
                if not config.BROADCAST_MODE:
                    break  # Exit the render_modes loop if not in broadcast mode

        # End of SECTION 1.1 creation of all image
        logging.info(f"Number of job payloads generated: {len(job_payloads)}")

    except Exception as e:
        logging.error(f"An error occurred while generating job payloads: {e}")
        raise

    return job_payloads, prompts

def create_api_specific_payload(model_id, prompt, style):
    # Common parameters for both APIs

    # Define your options
    options = [
        (1360, 768),
        (768, 1024),
        (768, 1360)
    ]

    # Randomly select one option
    selected_option = random.choice(options)

    # Assign the values
    IMAGE_HEIGHT = config.IMAGE_HEIGHT
    IMAGE_WIDTH = config.IMAGE_WIDTH

    # Assign random orientation values

    if config.RENDER_MODE == 'Civitai':
        codex_params = {
            "height": IMAGE_HEIGHT,
            "width": IMAGE_WIDTH,
            "model": model_id,
            "sampler": config.SAMPLER,
            "steps": 25,
            "seed": -1,
            "cfgScale": 4.6,
            "negativePrompt": config.NEGATIVE
        }
    else:
        codex_params = {
            "height": IMAGE_HEIGHT,
            "width": IMAGE_WIDTH,
            "modelId": model_id,
            "sd_model": model_id,
            "model": model_id,
            "presetStyle": style,
            "style_preset": style,
            "num_images": config.NUM_IMAGES,
            "steps": 25,
            "cfg_scale": 4.6,
            "seed": -1,
            "upscale": False,
            "sampler": config.SAMPLER,
            "aspect_ratio": "portrait",
            "negative_prompt": config.NEGATIVE
        }

    # Add random value parameters for CivitAI
    # "cfg_scale": random.uniform(3, 15),  # Random float between 3 and 15
    #  "steps": random.randint(10, 50)  # Random integer between 10 and 50
    if config.RENDER_MODE == 'Civitai':
        codex_params.update({
            "cfgScale": 4.7,
            "steps": 30
        })

    # Add random value parameters for Leonardo
    # "cfg_scale": random.uniform(3, 15),  # Random float between 3 and 15
    #  "steps": random.randint(10, 50)  # Random integer between 10 and 50
    if config.RENDER_MODE == 'Prodia':
        codex_params.update({
            "cfg_scale": 4.6,
            "steps": 25
        })

    # Add provider-specific parameters
    if config.RENDER_MODE == 'Prodia':
        service_options = {
            "provider": "prodia",
            "api_key": config.PRODIA_TOKEN
        }
    elif config.RENDER_MODE == 'Midjourney':  # Check if the RENDER_MODE is 'Midjourney'
        service_options = {
            "provider": "midjourney",
            "api_key": config.MIDJOURNEY_TOKEN  # Assuming you have a separate token for Midjourney
        }
    elif config.RENDER_MODE == 'Dalle':  # Check if the RENDER_MODE is 'Dalle'
        service_options = {
            "provider": "dalle",
            "api_key": config.DALLE_TOKEN  # Assuming you have a separate token for Midjourney
        }
    elif config.RENDER_MODE == 'Civitai':  # Check if the RENDER_MODE is 'CivitAI'
        service_options = {
            "provider": "civitai",
            "api_key": config.CIVITAI_TOKEN  # Assuming you have a separate token for Midjourney
        }
    else:  # Defaults to 'Leonardo' for any api_type other than 'Prodia'
        service_options = {
            "provider": "leonardo",
            "api_key": config.LEONARDO_TOKEN
        }

    return {
        "prompt": prompt,
        "service_options": service_options,
        "codex_parameters": codex_params
    }