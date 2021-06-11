# encoding: utf-8
from aiohttp import web
import json
import hashlib
from models import User, Recipe, Database, DatabaseUpdateException
from validator import RequestValidator

import time
import base64
from cryptography import fernet
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage


def admin_only(handler):
    async def new_handler(request):
        session = await aiohttp_session.get_session(request)
        if not Database.users_collection().find_one({'user_id': session['user_id']}).get('isAdmin'):
            return web.json_response({
                'name': 'Forbidden',
                'message': 'insufficient rights to the resource'
            }, status=403)
        return await handler(request)
    return new_handler


def protect_for_user(handler):
    async def new_handler(request):
        session = await aiohttp_session.get_session(request)
        user_id = int(request.match_info['user_id'])
        if user_id != int(session['user_id']):
            return web.json_response({
                'name': 'Forbidden',
                'message': 'insufficient rights to the resource'
            }, status=403)
        return await handler(request)
    return new_handler


def protect(handler):
    async def new_handler(request):
        session = await aiohttp_session.get_session(request)
        if 'user_id' not in session:
            return web.json_response({
                'name': 'Unauthorized',
                'message': 'your request was made with invalid credentials'
            }, status=401)
        return await handler(request)
    return new_handler


@protect
@protect_for_user
async def delete_user(request):
    user_id = int(request.match_info['user_id'])
    deleted = Database.users_collection().delete_one({'user_id': user_id})
    if deleted.deleted_count > 0:
        return web.json_response({
            'name': 'Deleted',
            'message': 'User {0} deleted successfully'
        }, status=205)
    else:
        return web.json_response({
            'name': 'Not exists',
            'message': 'User {0} is not exists'
        }, status=200)


async def sign_in(request):
    data = await request.post()
    nickname, errors = RequestValidator.validate_single_string('nickname', data, [])
    password, errors = RequestValidator.validate_single_string('password', data, errors)
    user = Database.users_collection().find_one({'nickname': nickname})
    if errors:
        return RequestValidator.error_response(errors)
    if user:
        return web.json_response({
            'name': 'OK',
            'message': 'User {0} already exists'.format(nickname)
        }, status=200)
    try:
        user = User(nickname=nickname, password=password)
    except AssertionError:
        return web.json_response({
            'name': 'User validation failed',
            'message': 'nickname does not match syntax, nickname must consist of latin letters, digits and spaces'
        }, status=422)
    Database.users_collection().insert_one(user.__dict__)
    return web.json_response({
        'name': 'Created',
        'message': 'User {0} created successfully'.format(nickname)
    }, status=201)


async def session_generate(request):
    data = await request.post()
    nickname, errors = RequestValidator.validate_single_string('nickname', data, [])
    password, errors = RequestValidator.validate_single_string('password', data, errors)
    if errors:
        return RequestValidator.error_response(errors)
    crypt_password = User.encrypt_password(password)
    user_with_nickname = Database.users_collection().find_one({'nickname': nickname})
    if (not user_with_nickname) or user_with_nickname['crypt_password'] != crypt_password:
        return web.json_response({
            'name': 'Bad Request',
            'message': 'incorrect user or password'
        }, status=400)
    session = await aiohttp_session.new_session(request)
    session['user_id'] = user_with_nickname['user_id']
    return web.json_response({
        'name': 'OK',
        'message': 'authorized successfully'
    }, status=200)


@protect
async def logout(request):
    session = await aiohttp_session.get_session(request)
    session.invalidate()
    return web.json_response({
        'name': 'OK',
        'message': 'logged out'
    }, status=204)


@protect
async def user_profile(request):
    session = await aiohttp_session.get_session(request)
    user_id = int(request.match_info['user_id'])
    user = Database.users_collection().find_one({'user_id': user_id})
    current_user = Database.users_collection().find_one({'user_id': session['user_id']})
    if not user:
        return web.json_response({
            'name': 'Not found',
            'message': 'profile you looking for appears to be not exists'
        }, status=404)
    if user.get('status') is 'locked' and not current_user.get('isAdmin'):
        return web.json_response({
            'name': 'Locked',
            'message': 'user locked'
        }, status=423)
    response = {
        'name': 'OK',
        'message': 'user profile info',
    }
    response.update(dict(filter(lambda item: item[0] in [
        'user_id', 'nickname', 'status', 'recipes_total'] + (['favorites', 'recipes']
        if current_user.get('user_id') == user_id or current_user.get('isAdmin') else []), user.items())))
    return web.json_response(response, status=200)


@protect
async def explore_peoples(request):
    peoples = [user for user in Database.users_collection().find(
        limit=10, projection=['user_id', 'nickname', 'status', 'recipes_total'],
        filter={'status': 'active'}, sort=[('recipes_total', -1)])]
    peoples_reduced = list(map(lambda item: dict(filter(lambda item: item[0] in [
        'user_id', 'nickname', 'status', 'recipes_total'], item.items())), peoples))
    response = {
        'name': 'OK',
        'message': 'list of famous ramsy',
        'collection': peoples_reduced
    }
    return web.json_response(response, status=200)


@protect
async def recipe_create(request):
    data = await request.post()
    recipe_title, errors = RequestValidator.validate_single_string('recipe_title', data, [])
    recipe_description, errors = RequestValidator.validate_single_string('recipe_description', data, errors)
    recipe_steps, errors = RequestValidator.validate_recipe_steps(data, errors)
    if errors:
        return RequestValidator.error_response(errors)
    session = await aiohttp_session.get_session(request)
    user = User(**Database.users_collection().find_one({'user_id': session['user_id']}))
    image_bytes = data.get('recipe_img')
    recipe_options = {
        'author_id': user.user_id,
        'author': user.nickname,
        'image_bytes': bytes(image_bytes) if image_bytes else None,
        'hashtags': RequestValidator.validate_array_string('recipe_hashtag', data, [], optional=True) or [],
        'type': RequestValidator.validate_single_string('recipe_type', data, optional=True) or 'other',
        'title': recipe_title,
        'description': recipe_description,
        'steps': recipe_steps
    }
    try:
        recipe = Recipe(**recipe_options)
    except AssertionError:
        return web.json_response({
            'name': 'Recipe validation failed',
            'message': 'maybe title does not match syntax; title must consist of latin letters, digit and spaces'
        }, status=422)
    try:
        Database.recipes_collection().insert_one(recipe.__dict__)
        user.add_recipe(recipe.recipe_id)
    except DatabaseUpdateException as e:
        Database.recipes_collection().delete_one({'recipe_id': recipe.recipe_id})
        return web.json_response({
            'name': 'Something went wrong',
            'message': 'error when adding recipe to db and rewriting user stats: run.py -> recipe_create'
        }, status=500)
    return web.json_response({
        'name': 'Created',
        'message': 'new recipe {0} successfully created by user {1}'.format(recipe_title, user.nickname)
    }, status=201)


@protect
async def recipe_delete(request):
    return web.json_response({})


@protect
async def recipe_update(request):
    return web.json_response({})


@protect
async def recipe_like(request):
    return web.json_response({})


@protect
async def get_recipe(request):
    return web.json_response({})


@protect
@admin_only
async def block_user(request):
    return web.json_response({})


@protect
@admin_only
async def block_recipe(request):
    return web.json_response({})


@protect
async def explore_recipes(request):
    return web.json_response({})


async def hello(request):
    print(request)
    with open('./spec.json') as fp:
        return web.json_response(json.load(fp))


async def favicon(request):
    return web.Response(headers={
        'Content-Type': 'image/png; charset=utf-8'
    })


async def make_app():
    app = web.Application()
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key, max_age=3600))
    app.add_routes([
        web.get('/', hello),
        web.get('/favicon.ico', favicon),
        web.post('/auth', session_generate),
        web.post('/logout', logout),
        web.put('/signin', sign_in),
        web.delete(r'/profile/{user_id:\d+}/delete', delete_user),
        web.get(r'/profile/{user_id:\d+}', user_profile),
        web.get('/peoples', explore_peoples),
        web.get('/explore-recipes', explore_recipes),
        web.put('/recipe/create', recipe_create),
        web.delete(r'/recipe/{recipe_id:\d+}/delete', recipe_delete),
        web.put(r'/recipe/{recipe_id:\d+}/update', recipe_update),
        web.post(r'/recipe/{recipe_id:\d+}/like', recipe_like),
        web.post('/admin/block-user', block_user),
        web.post('/admin/block-recipe', block_recipe),
    ])
    return app

if __name__ == '__main__':
    web.run_app(make_app(), port=8100)
