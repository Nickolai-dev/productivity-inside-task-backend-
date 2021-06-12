# encoding: utf-8
from aiohttp import web
import pymongo
import re


class RequestValidator:
    @staticmethod
    def validate_single_string(field_name, post_data, prev_errors=None, optional=False):
        field_value = post_data.get(field_name)
        if not field_value and not optional:
            errors = (prev_errors or []) + [{
                'field': field_name,
                'message': 'you must fill {0} field'.format(field_name)
            }]
            return None, errors
        if field_value:
            field_value = field_value.decode('utf-8')
        return field_value if optional else (field_value, prev_errors)

    @staticmethod
    def validate_array_string(field_name, post_data, prev_errors=None, optional=False):
        try:
            values = post_data.getall(field_name)
        except KeyError:
            if optional:
                return []
            else:
                errors = (prev_errors or []) + [{
                    'field': field_name,
                    'message': 'you must (multiply) fill {0} field'.format(field_name)
                }]
                return None, errors
        decoded_values = list(map(lambda b: b.decode('utf-8'), values))
        return decoded_values if optional else (decoded_values, prev_errors)

    @staticmethod
    def validate_recipe_steps(post_data, prev_errors=None, fields_prefix_name='recipe_step_'):
        steps = []
        for i in range(1, 100):
            step_name = fields_prefix_name + str(i)
            step_value = post_data.get(step_name)
            if i == 1 and not step_value:  # min one step
                errors = (prev_errors or []) + [{
                    'field': step_name,
                    'message': 'you must fill almost 1 recipe step field'
                }]
                return None, errors
            if step_value:
                steps.append(step_value.decode('utf-8'))
            else:
                break
        return steps, prev_errors

    @staticmethod
    def error_response(errors):
        return web.json_response({
            'name': 'Unprocessable entity',
            'message': 'you missed some required fields',
            'errors': errors
        }, status=422)

    @staticmethod
    def sort_filter_options(post_data):
        sort_by = post_data.get('sort_by')
        sort_by = sort_by.decode('utf-8') if sort_by else None
        sort_opts = {
            'title': [('title', pymongo.ASCENDING)],
            'likes': [('likes_total', pymongo.DESCENDING)],
            'date_ascending': [('date', pymongo.ASCENDING)],
            'date_descending': [('date', pymongo.DESCENDING)],
            None: []
        }[sort_by]
        filter_opts = {}
        filter_type = list(filter(lambda x: x, map(lambda tp: tp.decode('utf-8'), post_data.getall('type_filter', []))))
        if filter_type:
            filter_opts.update({'type': {'$in': filter_type}})
        if post_data.get('title_filter'):
            filter_opts.update({'title': {
                '$regex': re.compile(post_data.get('title_filter').decode('utf-8'), re.IGNORECASE)}})
        if post_data.get('author_filter'):
            filter_opts.update({'author': {
                '$regex': re.compile(post_data.get('author_filter').decode('utf-8'), re.IGNORECASE)}})
        filter_hashtags = list(filter(
            lambda x: x, map(lambda tag: tag.decode('utf-8'), post_data.getall('hashtag_filter', []))))
        if filter_hashtags:
            filter_opts.update({'hashtags': {'$in': filter_hashtags}})
        if post_data.get('image_filter'):
            filter_opts.update({'image_bytes': {'$ne': None}})
        return sort_opts, filter_opts

    @staticmethod
    def recipe_options(post_data, user, optional_all=False):
        recipe_title, errors = RequestValidator.validate_single_string('recipe_title', post_data, [])
        recipe_description, errors = RequestValidator.validate_single_string('recipe_description', post_data, errors)
        recipe_steps, errors = RequestValidator.validate_recipe_steps(post_data, errors)
        if errors and not optional_all:
            return None, errors
        image_bytes = post_data.get('recipe_image').file.read() if post_data.get('recipe_image') else None
        recipe_options = {
            'author_id': user.user_id,
            'author': user.nickname,
            'hashtags': RequestValidator.validate_array_string('recipe_hashtag', post_data, [], optional=True) or [],
            'type': RequestValidator.validate_single_string('recipe_type', post_data, optional=True) or 'other',
            'title': recipe_title,
            'description': recipe_description,
            'steps': recipe_steps
        }
        if optional_all:
            recipe_options = dict(filter(lambda i: i[1], recipe_options.items()))
        if image_bytes or (not image_bytes and not optional_all):
            recipe_options.update({
                'image_bytes': bytes(image_bytes) if image_bytes else None,
            })
        return recipe_options, errors
