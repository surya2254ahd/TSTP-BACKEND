def validate_add_question_request(request):
    data = request.data

    required_fields = ['course_subject_id', 'description', 'options']
    for required_field in required_fields:
        if data.get(required_field) is None:
            raise Exception(f'{required_field} is mandatory')
