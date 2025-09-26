from rest_framework.decorators import api_view
from rest_framework.response import Response

from .enums import LanguageType


@api_view()
def language_view(request):
    return Response(
        {
            "language": [{"title": lang.name, "code": lang.value} for lang in LanguageType],
        }
    )
