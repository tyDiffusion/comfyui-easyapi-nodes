import os

import folder_paths
import nodes
from server import PromptServer
from aiohttp import web
import execution
#from simple_lama_inpainting import SimpleLama
from .util import image_to_base64, base64_to_image
from .settings import reset_history_size, get_settings, set_settings

extension_folder = os.path.dirname(os.path.realpath(__file__))

"""
simple_lama = None
lama_model_dir = os.path.join(folder_paths.models_dir, "lama")
lama_model_path = os.path.join(lama_model_dir, "big-lama.pt")
if not os.path.exists(lama_model_path):
    os.environ['LAMA_MODEL'] = lama_model_path
    print(f"## lama model not found: {lama_model_path}, pls download from https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt")
else:
    os.environ['LAMA_MODEL'] = lama_model_path
os.makedirs(lama_model_dir, exist_ok=True)
"""

def register_routes():
    @PromptServer.instance.routes.post("/easyapi/history/size")
    async def set_history_size(request):
        json_data = await request.json()
        size = json_data["maxSize"]
        if size is not None:
            promptQueue = PromptServer.instance.prompt_queue
            with promptQueue.mutex:
                maxSize = int(size)
                execution.MAXIMUM_HISTORY_SIZE = maxSize
                history = promptQueue.history
                end = len(history) - maxSize
                i = 0
                for key in list(history.keys()):
                    if i >= end:
                        break
                    history.pop(key)
                    i = i + 1
                reset_history_size(maxSize)
            return web.Response(status=200)

        return web.Response(status=400)

    @PromptServer.instance.routes.get("/easyapi/history/maxSize")
    async def get_history_size(request):
        maxSize = execution.MAXIMUM_HISTORY_SIZE
        data = get_settings(file='config/easyapi.json')
        if 'history_max_size' in data:
            maxSize = data['history_max_size']

        return web.json_response({"maxSize": maxSize})

    @PromptServer.instance.routes.post("/easyapi/settings/{id}")
    async def set_setting(request):
        setting_id = request.match_info.get("id", None)
        if not setting_id:
            return web.Response(status=400)
        json_body = await request.json()
        set_settings(setting_id, json_body[setting_id])
        return web.Response(status=200)

    @PromptServer.instance.routes.get("/easyapi/settings/{id}")
    async def get_setting(request):
        setting_id = request.match_info.get("id", None)
        settings = get_settings(file='config/easyapi.json')
        if settings and setting_id in settings:
            return web.json_response({setting_id: settings[setting_id]})

        return web.json_response({})

    @PromptServer.instance.routes.post("/easyapi/prompt")
    async def post_prompt(request):
        print("got prompt")
        json_data = await request.json()
        json_data = PromptServer.instance.trigger_on_prompt(json_data)
        prompt_id = json_data["prompt_id"]
        print("prompt_id={}".format(json_data["prompt_id"]))

        if "number" in json_data:
            number = float(json_data['number'])
        else:
            number = PromptServer.instance.number
            if "front" in json_data:
                if json_data['front']:
                    number = -number

            PromptServer.instance.number += 1

        if "prompt" in json_data:
            prompt = json_data["prompt"]
            valid = execution.validate_prompt(prompt)
            extra_data = {}
            if "extra_data" in json_data:
                extra_data = json_data["extra_data"]

            if "client_id" in json_data:
                extra_data["client_id"] = json_data["client_id"]
            if valid[0]:
                outputs_to_execute = valid[2]
                PromptServer.instance.prompt_queue.put((number, prompt_id, prompt, extra_data, outputs_to_execute))
                response = {"prompt_id": prompt_id, "number": number, "node_errors": valid[3]}
                return web.json_response(response)
            else:
                print("invalid prompt:", valid[1])
                return web.json_response({"error": valid[1], "node_errors": valid[3]}, status=400)
        else:
            return web.json_response({"error": "no prompt", "node_errors": []}, status=400)

    @PromptServer.instance.routes.post("/easyapi/interrupt")
    async def post_interrupt(request):
        json_data = await request.json()
        prompt_id = json_data["prompt_id"]
        current_queue = PromptServer.instance.prompt_queue.get_current_queue()
        queue_running = current_queue[0]
        if queue_running is not None and len(queue_running) > 0:
            if len(queue_running[0]) > 0 and queue_running[0][1] == prompt_id:
                nodes.interrupt_processing()

        delete_func = lambda a: a[1] == prompt_id
        PromptServer.instance.prompt_queue.delete_queue_item(delete_func)
        return web.Response(status=200)

    """
    @PromptServer.instance.routes.post("/easyapi/lama_cleaner")
    async def lama_cleaner(request):
        json_data = await request.json()
        image = json_data["image"]
        mask = json_data["mask"]
        if image is None or mask is None:
            return web.json_response({"error": "missing required params"}, status=400)

        global simple_lama
        if simple_lama is None:
            simple_lama = SimpleLama()

        image = base64_to_image(image)
        mask = base64_to_image(mask)
        mask = mask.convert('L')

        res = simple_lama(image, mask)

        encoded_image = image_to_base64(res)

        response = {"base64Image": encoded_image}
        return web.json_response(response, status=200)
    """

def init():
    reset_history_size(isStart=True)
    register_routes()
