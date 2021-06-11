# encoding: utf-8
import re
import pymongo
import hashlib
import random
import time


class DatabaseUpdateException(Exception):
    pass


class User:
    _PASSWORD_SALT = 'super secret'

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', Database.get_free_id(Database.users_collection()))
        self.nickname = kwargs.get('nickname')
        self.status = kwargs.get('status', 'active')
        self.favorites = kwargs.get('favorites', [])
        self.likes_total = kwargs.get('likes_total', 0)
        self.recipes = kwargs.get('recipes', [])
        self.recipes_total = kwargs.get('recipes_total', len(self.recipes))
        password = kwargs.get('password', None)
        self.crypt_password = kwargs.get(
            'crypt_password', (User.encrypt_password(password) if password else None))
        self.isAdmin = False
        self.validate()

    def add_recipe(self, recipe_id):
        try:
            Database.users_collection().update_one({'user_id': self.user_id}, [
                {'$set': {'recipes': {'$concatArrays': ['$recipes', [recipe_id]]}}}
            ])
            Database.users_collection().update_one({'user_id': self.user_id}, {
                '$inc': {'recipes_total': 1}
            })
        except Exception as e:
            print(e)
            raise DatabaseUpdateException
        self.recipes_total += 1
        self.recipes.append(recipe_id)

    @staticmethod
    def encrypt_password(password):
        return hashlib.md5(''.join([User._PASSWORD_SALT, password]).encode('utf-8')).hexdigest()

    def validate(self):
        assert all([
            type(self.user_id) == int,
            re.match(r'^[\w\d]+[\w\d ]*[\w\d]+$', self.nickname),
            self.status in ['active', 'locked'],
            (type(self.favorites) == list and
             all(list(map(lambda x: type(x) is int, self.favorites)))),
            (type(self.recipes) == list and
             all(list(map(lambda x: type(x) is int, self.recipes)))),
            self.isAdmin in [False, True]
        ])


class Recipe:
    def __init__(self, **kwargs):
        self.recipe_id = kwargs.get('recipe_id', Database.get_free_id(Database.recipes_collection()))
        self.author_id = kwargs.get('author_id')
        self.author = kwargs.get('author')
        self.date = kwargs.get('date', time.time())
        self.title = kwargs.get('title', '')
        self.type = kwargs.get('type', 'other')
        self.description = kwargs.get('description', '')
        self.steps = kwargs.get('steps', [])
        self.status = kwargs.get('status', 'active')
        self.hashtags = kwargs.get('hashtags', [])
        self.likes = kwargs.get('likes', [])
        self.likes_total = kwargs.get('likes_total', 0)
        self.image_bytes = kwargs.get('image_bytes', None)
        self.validate()

    def validate(self):
        assert all([
            type(self.author_id) is int,
            re.match(r'^[\w\d]+[\w\d ]*[\w\d]+$', self.title),
            self.type in ['other', 'drink', 'salad', 'first course', 'second course', 'soup', 'dessert']
        ])


class Database:
    _client = None
    _users = None
    _recipes = None

    @staticmethod
    def client():
        if not Database._client:
            Database._client = pymongo.MongoClient()
        return Database._client

    @staticmethod
    def users_collection():
        if not Database._users:
            Database._users = Database.client().database.users
        return Database._users

    @staticmethod
    def recipes_collection():
        if not Database._recipes:
            Database._recipes = Database.client().database.recipes
        return Database._recipes

    @staticmethod
    def get_free_id(collection):
        while True:
            free_id = random.randrange(100000, 1000000)
            if collection.find().where('this.user_id == {0} || this.recipe_id == {0}'.format(free_id)).count() == 0:
                return free_id
