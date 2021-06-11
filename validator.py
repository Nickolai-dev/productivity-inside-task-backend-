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
            if i in [1, 2] and not step_value:  # min two steps
                errors = (prev_errors or []) + [{
                    'field': step_name,
                    'message': 'you must fill almost 2 recipe step fields'
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
        sort_opts = {
            'title': [('title', pymongo.ASCENDING)],
            'likes': [('likes_total', pymongo.ASCENDING)],
            'date_ascending': [('date', pymongo.ASCENDING)],
            'date_descending': [('date', pymongo.DESCENDING)],
        }[post_data.get('sort_by')]
        filter_opts = {}
        if post_data.get('type_filter'):
            filter_opts.update({'type': post_data.get('type_filter').decode('utf-8')})
        if post_data.get('title_filter'):
            filter_opts.update({'title': {
                '$regex': re.compile(post_data.get('title_filter').decode('utf-8'), re.IGNORECASE)}})
        if post_data.get('author_filter'):
            filter_opts.update({'title': {
                '$regex': re.compile(post_data.get('author_filter').decode('utf-8'), re.IGNORECASE)}})
        filter_hashtags = list(filter(lambda hashtag: hashtag, post_data.getall('hashtag_filter', [])))
        if filter_hashtags:
            filter_opts.update({'hashtags': {'$in': filter_hashtags}})
        if post_data.get('image_filter'):
            filter_opts.update({'image_bytes': {'$ne': None}})
        return sort_opts, filter_opts
