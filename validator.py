# encoding: utf-8


class RequestValidator:
    @staticmethod
    def validate(field_name, post_data, prev_errors=None):
        field_value = post_data.get(field_name)
        if not field_value:
            errors = (prev_errors or []) + [{
                'field': field_name,
                'message': 'you must fill {0} field'.format(field_name)
            }]
            return False, errors
        return field_value.decode('utf-8'), prev_errors
