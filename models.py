# encoding: utf-8
import re
import pymongo


class User:
    def __init__(self, **kwargs):
        self.userId = kwargs.get('userId')
        self.nickname = kwargs.get('nickname')
        self.status = kwargs.get('status', 'active')
        self.favorites = kwargs.get('favorites', [])
        self.isAdmin = False
        self.validate()

    def validate(self):
        def is_valid_favorite():
            return True
        assert all([
            type(self.userId) == int,
            re.match(r'^\w+[\w\ ]*\w+$', self.nickname),
            self.status in ['active', 'locked'],
            (type(self.favorites) == list and
             all(list(map(is_valid_favorite, self.favorites)))),
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
    def get_user(**kwargs):
        return Database.users_collection().find_one(kwargs)

    @staticmethod
    def get_recipe(**kwargs):
        pass

    @staticmethod
    def get_free_user_id():
        assert 0  # TODO
