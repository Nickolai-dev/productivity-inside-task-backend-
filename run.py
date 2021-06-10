# encoding: utf-8
from aiohttp import web
import json
import hashlib
from models import User, Recipe, Database
from validator import RequestValidator

import time
import base64
from cryptography import fernet
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from aiohttp_session import SimpleCookieStorage


PASSWORD_SALT = 'super secret'


def protect(handler):
    async def new_handler(request):
        session = await aiohttp_session.get_session(request)
        if 'userId' not in session:
            return web.json_response({
                'name': 'Unauthorized',
                'message': 'your request was made with invalid credentials'
            }, status=401)
        return await handler(request)
    return new_handler


async def session_generate(request):
    data = await request.post()
    nickname, errors = RequestValidator.validate('nickname', data, [])
    password, errors = RequestValidator.validate('password', data, errors)
    if not (password and nickname):
        return web.json_response(errors, status=422)
    crypt_password = hashlib.md5(''.join([PASSWORD_SALT, password]).encode('utf-8')).hexdigest()
    user_attempt_login = Database.get_user(nickname=nickname)
    if (not user_attempt_login) or user_attempt_login['crypt_password'] != crypt_password:
        return web.json_response({
            'name': 'Bad Request',
            'message': 'incorrect user or password'
        }, status=400)
    session = await aiohttp_session.new_session(request)
    session['userId'] = user_attempt_login['userId']
    return web.json_response({
        'name': 'OK',
        'message': 'authorized successfully'
    }, status=200)


async def hello(request):
    print(request)
    with open('./spec.json') as fp:
        return web.json_response(json.load(fp))


async def favicon(request):
    return web.Response(headers={
        'Content-Type': 'image/png; charset=utf-8'
    })


@protect
async def test(request):
    session = await aiohttp_session.get_session(request)
    session['last_visit'] = time.time()
    text = 'Last visited: {}'.format(session['last_visit'])
    return web.Response(text=text)


async def make_app():
    app = web.Application()
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key, max_age=3600))
    app.add_routes([
        web.get('/', hello),
        web.get('/favicon.ico', favicon),
        web.post('/auth', session_generate),
        web.post('/test', test),
    ])
    return app

if __name__ == '__main__':
    web.run_app(make_app(), port=8100)
