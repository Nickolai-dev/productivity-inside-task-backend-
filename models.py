# encoding: utf-8
import re
import pymongo
import hashlib
import random


class User:
    _PASSWORD_SALT = 'super secret'

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', Database.get_free_user_id())
        self.nickname = kwargs.get('nickname')
        self.status = kwargs.get('status', 'active')
        self.favorites = kwargs.get('favorites', [])
        self.recipes = kwargs.get('recipes', [])
        self.recipes_total = kwargs.get('recipes_total', len(self.recipes))
        password = kwargs.get('password', None)
        self.crypt_password = kwargs.get(
            'crypt_password', (User.encrypt_password(password) if password else None))
        self.isAdmin = False
        self.validate()

    @staticmethod
    def encrypt_password(password):
        return hashlib.md5(''.join([User._PASSWORD_SALT, password]).encode('utf-8')).hexdigest()

    def validate(self):
        assert all([
            type(self.user_id) == int,
            re.match(r'^\w+[\w ]*\w+$', self.nickname),
            self.status in ['active', 'locked'],
            (type(self.favorites) == list and
             all(list(map(lambda x: type(x) is int, self.favorites)))),
            (type(self.recipes) == list and
             all(list(map(lambda x: type(x) is int, self.recipes)))),
            self.isAdmin in [False, True]
        ])


class Recipe:
    def __init__(self, **kwargs):
        self.authorId = kwargs.get('authorId')
        self.date = kwargs.get('date')
        self.name = kwargs.get('name')
        self.type = kwargs.get('type', 'other')
        self.description = kwargs.get('description')
        self.steps = kwargs.get('steps')
        self.status = kwargs.get('status', 'active')
        self.hashTags = kwargs.get('hashTags', [])
        self.likes = kwargs.get('likes', [])
        self.imageBlob = kwargs.get('imageBlob')
        self.validate()

    def validate(self):
        pass


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
    def create_user(nickname, password):
        user_exists = Database.users_collection().find_one({'nickname': nickname})
        if user_exists:
            return False, user_exists
        new_user = User(nickname=nickname, password=password)
        Database.users_collection().insert_one(new_user.__dict__)
        return True, new_user

    @staticmethod
    def get_free_user_id():
        while True:
            user_id = random.randrange(100000, 1000000)
            if not Database.users_collection().find_one({'user_id': user_id}):
                return user_id
