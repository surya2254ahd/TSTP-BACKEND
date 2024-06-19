import uuid

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def generate_unique_identifier(input_string):
    # Remove spaces from the input string
    input_string = input_string.replace(" ", "_")

    # Generate a unique identifier (UUID)
    unique_identifier = str(uuid.uuid4().hex)[:6]  # Using the first 6 characters of the UUID

    # Append the unique identifier to the modified input string
    unique_string = f"{input_string}_{unique_identifier}"

    return unique_string


def generate_unique_code(code):
    # Generate a UUID and convert it to a hexadecimal string
    unique_id = uuid.uuid4()
    unique_code = unique_id.hex

    return code + "_" + unique_code


def get_error_response(message):
    response = {
        'detail': message
    }
    return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


def get_error_response_for_serializer(logger, serializer, data):
    error = ''
    for field_name, field_errors in serializer.errors.items():
        try:
            if len(field_errors) > 1:
                for sub_field in field_errors:
                    for dict_field_name, dict_field_errors in sub_field.items():
                        error += str.capitalize(dict_field_name) + ': ' + str.capitalize(dict_field_errors[0]) + '<br/>'
            else:
                error += str.capitalize(field_name) + ': ' + str.capitalize(field_errors[0]) + '<br/>'
        except Exception as e:
            logger.info(f'Error processing error for - {field_name} because of {e}')
    if error == '':
        error = 'Oops! Something went wrong.'
    logger.exception(f'Error processing the request - {data} because of {serializer.errors}')
    response = {
        'detail': error
    }
    return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class CustomPageNumberPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })
