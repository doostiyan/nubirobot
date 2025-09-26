def obtain_api_key(request, format):
    if format == 'html':
        api_key = request.COOKIES.get('api_key')
    else:
        api_key = request.META["HTTP_AUTHORIZATION"].split()[1]
    return api_key
