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
    async def new_handler(*args, **kwargs):
        session = await aiohttp_session.get_session(args[0])
        if not Database.users_collection().find_one({'user_id': session['user_id']}).get('isAdmin'):
            return web.json_response({
                'name': 'Forbidden',
                'message': 'insufficient rights to the resource'
            }, status=403)
        return await handler(*args, **kwargs)
    return new_handler


def process_recipe_in_uri(handler):
    async def new_handler(*args, **kwargs):
        recipe_id = int(args[0].match_info.get('recipe_id'))
        recipe = Database.recipes_collection().find_one({'recipe_id': recipe_id})
        admin = args[2].get('isAdmin')
        if not recipe or (not admin and recipe.get('status') is 'locked'):
            return web.json_response({
                'name': 'Not found',
                'message': 'recipe not found'
            }, status=404)
        return await handler(*args, recipe, **kwargs)
    return new_handler


def protect_for_user(handler):
    async def new_handler(*args, **kwargs):
        session = await aiohttp_session.get_session(args[0])
        user_id = int(args[0].match_info.get('user_id'))
        if user_id != int(session['user_id']):
            return web.json_response({
                'name': 'Forbidden',
                'message': 'insufficient rights to the resource'
            }, status=403)
        return await handler(*args, **kwargs)
    return new_handler


def protect(handler):
    async def new_handler(*args, **kwargs):
        session = await aiohttp_session.get_session(args[0])
        if 'user_id' not in session:
            return web.json_response({
                'name': 'Unauthorized',
                'message': 'your request was made with invalid credentials'
            }, status=401)
        user = Database.users_collection().find_one({'user_id': int(session['user_id'])})
        if user.get('status') == 'locked':
            return web.json_response({
                'name': 'Forbidden',
                'message': 'your account has been locked'
            }, status=403)
        return await handler(*args, session, user, **kwargs)
    return new_handler


@protect
@protect_for_user
async def delete_user(request, session, user):
    user_id = int(request.match_info.get('user_id'))
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
async def logout(request, session, user):
    session.invalidate()
    return web.json_response({
        'name': 'OK',
        'message': 'logged out'
    }, status=204)


@protect
async def user_profile(request, session, current_user):
    user_id = int(request.match_info.get('user_id'))
    user = Database.users_collection().find_one({'user_id': user_id})
    if not user:
        return web.json_response({
            'name': 'Not found',
            'message': 'profile you are looking for appears not to be exist'
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
async def explore_peoples(request, session, user):
    peoples = [user for user in Database.users_collection().find(
        limit=10, projection=['user_id', 'nickname', 'status', 'recipes_total'],
        filter={'status': 'active'} if not user.get('isAdmin') else {}, sort=[('recipes_total', -1)])]
    peoples_reduced = list(map(lambda item: dict(filter(lambda item: item[0] in [
        'user_id', 'nickname', 'status', 'recipes_total'], item.items())), peoples))
    response = {
        'name': 'OK',
        'message': 'list of famous ramsy',
        'collection': peoples_reduced
    }
    return web.json_response(response, status=200)


@protect
async def recipe_create(request, session, user):
    data = await request.post()
    recipe_title, errors = RequestValidator.validate_single_string('recipe_title', data, [])
    if errors:
        return RequestValidator.error_response(errors)
    if Database.recipes_collection().find_one({'title': recipe_title}):
        return web.json_response({
            'name': 'OK',
            'message': 'recipe {0} already exists'.format(recipe_title),
        }, status=200)
    user = User(**user)
    recipe_options, errors = RequestValidator.recipe_options(data, user)
    if errors:
        return RequestValidator.error_response(errors)
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
async def recipe_delete(request, session, user):
    recipe_id = int(request.match_info.get('recipe_id'))
    recipe = Database.recipes_collection().find_one({'recipe_id': recipe_id})
    if not recipe:
        return web.json_response({
            'name': 'OK',
            'message': 'recipe doesnt exist'
        }, status=200)
    recipe = Recipe(**recipe)
    if recipe.author_id != int(session['user_id']):
        return web.json_response({
            'name': 'Forbidden',
            'message': 'you cannot deelte recipe you don`t own'
        }, status=403)
    user = User(**user)
    try:
        recipe.delete_recipe(user)
    except DatabaseUpdateException:
        return web.json_response({
            'name': 'Something went wrong',
            'message': 'error when deleting recipe or deleting it from favorites stats: run.py -> recipe_like'
        }, status=500)
    return web.json_response({
        'name': 'No content',
        'message': 'recipe has deleted'
    }, status=204)


@protect
@process_recipe_in_uri
async def recipe_update(request, session, user, recipe):
    data = await request.post()
    user = User(**user)
    if recipe.get('recipe_id') not in user.recipes:
        return web.json_response({
            'name': 'Forbidden',
            'message': 'you cannot modify recipe you doesnt own'
        }, status=403)
    recipe_options, errors = RequestValidator.recipe_options(data, user, optional_all=True)
    set_recipe_options = list(map(lambda t: {t[0]: t[1]},
                                  (map(lambda option: ('$set', {option[0]: option[1]}),
                                       recipe_options.items()))))
    Database.recipes_collection().update_one({'recipe_id': recipe.get('recipe_id')}, set_recipe_options)
    return web.json_response({
        'name': 'OK',
        'message': 'recipe updated'
    }, status=200)


@protect
@process_recipe_in_uri
async def recipe_like(request, session, user, recipe):
    recipe = Recipe(**recipe)
    user = User(**user)
    try:
        user.like_recipe(recipe)
    except DatabaseUpdateException:
        return web.json_response({
            'name': 'Something went wrong',
            'message': 'error when adding recipe to liked or rewriting recipe likes or author stats: run.py -> recipe_like'
        }, status=500)
    return web.json_response({
        'name': 'OK',
        'message': 'recipe liked',
    }, status=200)


@protect
@process_recipe_in_uri
async def get_recipe(request, session, user, recipe):
    projection = ['author', 'author_id', 'recipe_id', 'date', 'title', 'description', 'status', 'hashtags',
                  'likes', 'likes_total', 'type', 'image_bytes', 'steps']
    recipe_reduced = dict(filter(lambda item: item[0] in projection, recipe.items()))
    recipe_reduced.update({'user_status': user.get('status')})
    recipe_reduced['image_base64_encoded_bytes'] = base64.encodebytes(
        recipe_reduced['image_bytes']).decode('utf-8').replace('\n', '') if recipe_reduced['image_bytes'] else None
    del recipe_reduced['image_bytes']
    response = {
        'name': 'OK',
        'message': 'recipe complete data'
    }
    response.update(recipe_reduced)
    return web.json_response(response, status=200)


@protect
@admin_only
async def block_user(request, session, admin):
    data = await request.post()
    status, errors = RequestValidator.validate_single_string('set_status', data)
    user = Database.users_collection().find_one({'user_id': int(request.match_info.get('user_id'))})
    if status not in ['locked', 'active']:
        return web.json_response({
            'name': 'Bad request',
            'message': 'incorrect request'
        }, status=400)
    Database.users_collection().update_one({'user_id': user.get('user_id')}, [{
        '$set': {'status': status}
    }])
    return web.json_response({
        'name': 'OK',
        'message': 'for user {0} set status {1}'.format(user.get('nickname'), status)
    }, status=205)


@protect
@admin_only
async def block_recipe(request, session, admin):
    data = await request.post()
    status, errors = RequestValidator.validate_single_string('set_status', data)
    recipe = Database.recipes_collection().find_one({'recipe_id': int(request.match_info.get('recipe_id'))})
    if status not in ['locked', 'active']:
        return web.json_response({
            'name': 'Bad request',
            'message': 'incorrect request'
        }, status=400)
    Database.recipes_collection().update_one({'recipe_id': recipe.get('recipe_id')}, [{
        '$set': {'status': status}
    }])
    return web.json_response({
        'name': 'OK',
        'message': 'for recipe {0} set status {1}'.format(recipe.get('title'), status)
    }, status=205)


@protect
async def explore_recipes(request, session, user):
    data = await request.post()
    admin = user.get('isAdmin')
    get_from, get_to = int(request.query.get('from', '0')), int(request.query.get('to', '10'))
    skip, limit = get_from, get_to - get_from
    limit = limit if limit > 0 else 1
    sort_opt, filter_opt = RequestValidator.sort_filter_options(data)
    if not admin:  # admin can see locked
        filter_opt.update({'status': 'active'})
    projection = ['author', 'author_id', 'recipe_id', 'date', 'title', 'description', 'status', 'hashtags',
                  'likes', 'likes_total', 'type',
                  # 'image_bytes' # Too big data for search; it is better to do thumbnails TODO thumbnails
                  # or simply do not pass megabytes of full image
                  ]
    cursor = Database.recipes_collection().find(
        filter_opt,
        projection=projection,
        sort=sort_opt, skip=skip, limit=limit)
    recipes_list = list(map(lambda item: dict(filter(lambda item: item[0] in projection, item.items())), cursor))
    all_recipes_count = Database.recipes_collection().find(filter_opt, projection=projection).count()

    def encode_imagebytes(recipe):
        # recipe['image_base64_encoded_bytes'] = base64.encodebytes(
        #     recipe['image_bytes']).decode('utf-8') if recipe['image_bytes'] else None
        # del recipe['image_bytes']
        pass
    map(encode_imagebytes, recipes_list)
    return web.json_response({
        'name': 'OK',
        'message': 'list of filtered and sorted recipes{0}'.format(
            '; (if you are admin you can see locked)' if admin else ''),
        'collection': recipes_list,
        'total_recipes_count': all_recipes_count,
        'pagination': {
            'from': get_from,
            'to': get_to,
        },
    })


@protect
async def user_favorites(request, session, user):
    favorites = user.get('favorites')
    Database.recipes_collection().find({})
    return web.json_response({})


async def hello(request):
    print(request)
    with open('./spec.json') as fp:
        return web.json_response(json.load(fp))


async def favicon(request):
    return web.Response(headers={
        'Content-Type': 'image/png; charset=utf-8'
    })


def no_cache(handler):
    async def new_handler(*args, **kwargs):
        response = await handler(*args, **kwargs)
        # if type(response.headers) is not dict:
        #     response.headers = {}
        response.headers.update({
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache'
        })
        return response
    return new_handler


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
        web.get(r'/profile/{user_id:\d+}', no_cache(user_profile)),
        web.get(r'/profile/{user_id:\d+}/favorites', no_cache(user_favorites)),
        web.get(r'/recipes/{recipe_id:\d+}', no_cache(get_recipe)),
        web.post('/peoples', explore_peoples),
        web.put('/recipes/create', recipe_create),
        web.post('/recipes/explore', explore_recipes),
        web.delete(r'/recipes/{recipe_id:\d+}/delete', recipe_delete),
        web.put(r'/recipes/{recipe_id:\d+}/update', recipe_update),
        web.post(r'/recipes/{recipe_id:\d+}/like', recipe_like),
        web.post(r'/admin/block-user/{user_id:\d+}', block_user),
        web.post(r'/admin/block-recipe/{recipe_id:\d+}', block_recipe),
    ])
    return app

if __name__ == '__main__':
    web.run_app(make_app(), port=8100)
