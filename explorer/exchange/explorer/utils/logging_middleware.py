import copy
import json

from django.core.cache import cache
from django.urls import resolve
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from exchange.blockchain.service_based.logging import logger


class ELKLoggingMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        request.request_time = timezone.now()
        request.initial_http_body = copy.deepcopy(request.body)
        request.initial_http_headers = copy.deepcopy(request.headers)

    def process_response(self, request, response):
        try:
            if request.path.rstrip('/') in self.get_excluded_paths():
                return response

            resolved_url = resolve(request.path_info)

            loggable_headers = dict(request.initial_http_headers) if hasattr(request, 'initial_http_headers') else {}
            loggable_headers = {k.lower(): v for k, v in loggable_headers.items()}
            ip_header_key = 'x-real-ip'

            if ip_header_key in loggable_headers:
                client_ip = loggable_headers[ip_header_key]

                ip_map_cache_key = f"logging_middleware:ip_map:{client_ip}"

                anonymous_client_id = cache.get(ip_map_cache_key)

                if not anonymous_client_id:
                    counter_cache_key = "logging_middleware:client_id_counter"

                    if not cache.get(counter_cache_key):
                        cache.add(counter_cache_key, 0)

                    new_id_num = cache.incr(counter_cache_key)

                    anonymous_client_id = f"client{new_id_num}"

                    cache.set(ip_map_cache_key, anonymous_client_id, timeout=None)

                loggable_headers[ip_header_key] = anonymous_client_id

            response_size_bytes = len(response.content) if response.content else 0
            logger.info(msg=resolved_url.url_name, extra={
                "method": request.method,
                "path": request.path,
                "full_path": request.get_full_path(),
                "request_body": self.get_request_body(request),
                "status_code": response.status_code,
                "response_headers": {k: v for k, v in response.headers.items()},
                "response_body": self.get_response_body(response),
                "response_size_bytes": response_size_bytes,
                "response_time": round((timezone.now() - request.request_time).total_seconds() * 1000, 2),  # in ms
                "request_cookies": dict() if not request.COOKIES else request.COOKIES,
                "response_cookies": dict() if not response.cookies else response.cookies,
                "request_headers": loggable_headers,
                "index_name": 'api',
                "path_params": resolved_url.kwargs,
                "query_params": dict(request.GET) if request.GET else {},
            })
            return response
        except Exception as e:
            try:
                url_name: str = resolved_url.url_name
            except Exception:
                url_name = "unknown"
            logger.exception('failed to log request-response', extra={"url_name": url_name, "error": str(e)})
            return response

    @staticmethod
    def get_excluded_paths():
        """Returns a list of URL paths to exclude from logging."""
        return [
            '/',
            '/favicon.ico',
            '/swagger',
            '/redoc',
            '/metrics',
        ]

    def get_request_body(self, request) -> dict:
        if not hasattr(request, 'initial_http_body') or not request.initial_http_body:
            return {}
        try:
            return json.loads(request.initial_http_body)
        except json.JSONDecodeError:
            return {"raw_body": str(request.initial_http_body)}

    def get_response_body(self, response) -> dict:
        if not response.content:
            return {}
        try:
            content_str = response.content.decode('utf-8')
            return json.loads(content_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw_response": str(response.content)}
