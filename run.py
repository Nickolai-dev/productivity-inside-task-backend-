from aiohttp import web
import json


async def hello(request):
    print(request)
    with open('./spec.json') as fp:
        return web.json_response(json.load(fp))


async def favicon(request):
    return web.Response(headers={
        'Content-Type': 'image/png; charset=utf-8'
    })

app = web.Application()
app.add_routes([web.get('/', hello), web.get('/favicon.ico', favicon)])

if __name__ == '__main__':
    web.run_app(app, port=8100)
