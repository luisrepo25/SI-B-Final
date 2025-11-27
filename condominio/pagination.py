from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class ReservaPagination(PageNumberPagination):
    page_size = 100  # o 10
    page_size_query_param = 'page_size'
    max_page_size = 1000

    def get_paginated_response(self, data):
        # Solo devuelve la lista de datos, sin metadatos
        return Response(data)