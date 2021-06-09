import re


class User:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.nickname = kwargs.get('nickname')
        self.status = kwargs.get('status', 'active')
        self.favorites = kwargs.get('favorites', [])
        self.isAdmin = False
        self.validate()

    def validate(self):
        def is_valid_favorite():
            return True
        assert all([
            type(self.id) == int,
            re.match(r'^\w+$', self.nickname),
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
