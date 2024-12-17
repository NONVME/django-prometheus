from django.utils.deprecation import MiddlewareMixin
from prometheus_client import Counter, Histogram
import re
from django.urls import Resolver404, get_resolver

from django_prometheus.conf import NAMESPACE, PROMETHEUS_LATENCY_BUCKETS, PROMETHEUS_USE_PATH_LABELS
from django_prometheus.utils import PowersOf, Time, TimeSince


class Metrics:
    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        return metric_cls(name, documentation, labelnames=labelnames, **kwargs)

    def __init__(self, *args, **kwargs):
        self.register()

    def register(self):
        self.requests_total = self.register_metric(
            Counter,
            "django_http_requests_before_middlewares_total",
            "Total count of requests before middlewares run.",
            namespace=NAMESPACE,
        )
        self.responses_total = self.register_metric(
            Counter,
            "django_http_responses_before_middlewares_total",
            "Total count of responses before middlewares run.",
            namespace=NAMESPACE,
        )
        self.requests_latency_before = self.register_metric(
            Histogram,
            "django_http_requests_latency_including_middlewares_seconds",
            ("Histogram of requests processing time (including middleware " "processing time)."),
            buckets=PROMETHEUS_LATENCY_BUCKETS,
            namespace=NAMESPACE,
        )
        self.requests_unknown_latency_before = self.register_metric(
            Counter,
            "django_http_requests_unknown_latency_including_middlewares_total",
            (
                "Count of requests for which the latency was unknown (when computing "
                "django_http_requests_latency_including_middlewares_seconds)."
            ),
            namespace=NAMESPACE,
        )
        self.requests_latency_by_view_method = self.register_metric(
            Histogram,
            "django_http_requests_latency_seconds_by_view_method",
            "Histogram of request processing time labelled by view.",
            ["view" if not PROMETHEUS_USE_PATH_LABELS else "path", "method"],
            buckets=PROMETHEUS_LATENCY_BUCKETS,
            namespace=NAMESPACE,
        )
        self.requests_unknown_latency = self.register_metric(
            Counter,
            "django_http_requests_unknown_latency_total",
            "Count of requests for which the latency was unknown.",
            namespace=NAMESPACE,
        )
        # Set in process_request
        self.requests_ajax = self.register_metric(
            Counter,
            "django_http_ajax_requests_total",
            "Count of AJAX requests.",
            namespace=NAMESPACE,
        )
        self.requests_by_method = self.register_metric(
            Counter,
            "django_http_requests_total_by_method",
            "Count of requests by method.",
            ["method"],
            namespace=NAMESPACE,
        )
        self.requests_by_transport = self.register_metric(
            Counter,
            "django_http_requests_total_by_transport",
            "Count of requests by transport.",
            ["transport"],
            namespace=NAMESPACE,
        )
        # Set in process_view
        self.requests_by_view_transport_method = self.register_metric(
            Counter,
            "django_http_requests_total_by_view_transport_method",
            "Count of requests by view/path, transport, method.",
            ["view" if not PROMETHEUS_USE_PATH_LABELS else "path", "transport", "method"],
            namespace=NAMESPACE,
        )
        self.requests_body_bytes = self.register_metric(
            Histogram,
            "django_http_requests_body_total_bytes",
            "Histogram of requests by body size.",
            buckets=PowersOf(2, 30),
            namespace=NAMESPACE,
        )
        # Set in process_template_response
        self.responses_by_templatename = self.register_metric(
            Counter,
            "django_http_responses_total_by_templatename",
            "Count of responses by template name.",
            ["templatename"],
            namespace=NAMESPACE,
        )
        # Set in process_response
        self.responses_by_status = self.register_metric(
            Counter,
            "django_http_responses_total_by_status",
            "Count of responses by status.",
            ["status"],
            namespace=NAMESPACE,
        )
        self.responses_by_status_view_method = self.register_metric(
            Counter,
            "django_http_responses_total_by_status_view_method",
            "Count of responses by status, view/path, method.",
            ["status", "view" if not PROMETHEUS_USE_PATH_LABELS else "path", "method"],
            namespace=NAMESPACE,
        )
        self.responses_body_bytes = self.register_metric(
            Histogram,
            "django_http_responses_body_total_bytes",
            "Histogram of responses by body size.",
            buckets=PowersOf(2, 30),
            namespace=NAMESPACE,
        )
        self.responses_by_charset = self.register_metric(
            Counter,
            "django_http_responses_total_by_charset",
            "Count of responses by charset.",
            ["charset"],
            namespace=NAMESPACE,
        )
        self.responses_streaming = self.register_metric(
            Counter,
            "django_http_responses_streaming_total",
            "Count of streaming responses.",
            namespace=NAMESPACE,
        )
        # Set in process_exception
        self.exceptions_by_type = self.register_metric(
            Counter,
            "django_http_exceptions_total_by_type",
            "Count of exceptions by object type.",
            ["type"],
            namespace=NAMESPACE,
        )
        self.exceptions_by_view = self.register_metric(
            Counter,
            "django_http_exceptions_total_by_view",
            "Count of exceptions by view.",
            ["view"],
            namespace=NAMESPACE,
        )


class PrometheusBeforeMiddleware(MiddlewareMixin):
    """Monitoring middleware that should run before other middlewares."""

    metrics_cls = Metrics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = self.metrics_cls.get_instance()

    def process_request(self, request):
        self.metrics.requests_total.inc()
        request.prometheus_before_middleware_event = Time()

    def process_response(self, request, response):
        self.metrics.responses_total.inc()
        if hasattr(request, "prometheus_before_middleware_event"):
            self.metrics.requests_latency_before.observe(TimeSince(request.prometheus_before_middleware_event))
        else:
            self.metrics.requests_unknown_latency_before.inc()
        return response


class PrometheusAfterMiddleware(MiddlewareMixin):
    """Monitoring middleware that should run after other middlewares."""

    metrics_cls = Metrics
    # URL_PATTERN = re.compile(r'([^/]+)')
    # URL_PARTS_REPLACEMENTS = {
    #     re.escape(part): replacement
    #     for part, replacement in {
    #         '<uuid:id>': '<id>',
    #         '<int:id>': '<id>',
    #         '<str:id>': '<id>',
    #         '<slug:id>': '<id>',
    #         '<uuid:pk>': '<pk>',
    #         '<int:pk>': '<pk>',
    #         '<str:pk>': '<pk>',
    #         '<slug:pk>': '<pk>',
    #     }.items()
    # }
    
    URL_PARTS_REPLACEMENTS = {
        re.escape('(?P'): '',
        re.escape('[0-9A-Fa-f-]+)'): '',
        re.escape('[^/.]+)'): '',
        re.escape('/$'): '/',
        re.escape('uuid:'): '',
        re.escape('str:'): '',
    }
    URL_PATTERN = re.compile('|'.join(URL_PARTS_REPLACEMENTS.keys()))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = self.metrics_cls.get_instance()
        self.resolver = get_resolver()

    def get_url_mask(self, request) -> str:
        url_mask = ''
        url_path = getattr(request, 'path', None)
        if not url_path:
            return url_mask

        try:
            resolver_match = getattr(request, 'resolver_match', None) or self.resolver.resolve(url_path)
            url_mask = self.URL_PATTERN.sub(
                lambda m: self.URL_PARTS_REPLACEMENTS[re.escape(m.group(0))],
                resolver_match.route
            )
        except Resolver404:
            pass

        return url_mask

    def _get_view_or_path(self, request):
        if PROMETHEUS_USE_PATH_LABELS:
            return self.get_url_mask(request) or request.path
        return self._get_view_name(request)

    def _transport(self, request):
        return "https" if request.is_secure() else "http"

    def _method(self, request):
        m = request.method
        if m not in (
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "DELETE",
            "TRACE",
            "OPTIONS",
            "CONNECT",
            "PATCH",
        ):
            return "<invalid method>"
        return m

    def label_metric(self, metric, request, response=None, **labels):
        return metric.labels(**labels) if labels else metric

    def process_request(self, request):
        transport = self._transport(request)
        method = self._method(request)
        self.label_metric(self.metrics.requests_by_method, request, method=method).inc()
        self.label_metric(self.metrics.requests_by_transport, request, transport=transport).inc()

        # Mimic the behaviour of the deprecated "Request.is_ajax()" method.
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            self.label_metric(self.metrics.requests_ajax, request).inc()

        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        self.label_metric(self.metrics.requests_body_bytes, request).observe(content_length)
        request.prometheus_after_middleware_event = Time()

    def _get_view_name(self, request):
        view_name = "<unnamed view>"
        if hasattr(request, "resolver_match"):
            if request.resolver_match is not None:
                if request.resolver_match.view_name is not None:
                    view_name = request.resolver_match.view_name
        return view_name

    def process_view(self, request, view_func, *view_args, **view_kwargs):
        transport = self._transport(request)
        method = self._method(request)
        if hasattr(request, "resolver_match"):
            label_value = self._get_view_or_path(request)
            label_name = "path" if PROMETHEUS_USE_PATH_LABELS else "view"
            self.label_metric(
                self.metrics.requests_by_view_transport_method,
                request,
                **{
                    label_name: label_value,
                    "transport": transport,
                    "method": method,
                }
            ).inc()

    def process_template_response(self, request, response):
        if hasattr(response, "template_name"):
            self.label_metric(
                self.metrics.responses_by_templatename,
                request,
                response=response,
                templatename=str(response.template_name),
            ).inc()
        return response

    def process_response(self, request, response):
        method = self._method(request)
        label_value = self._get_view_or_path(request)
        label_name = "path" if PROMETHEUS_USE_PATH_LABELS else "view"
        status = str(response.status_code)

        self.label_metric(self.metrics.responses_by_status, request, response, status=status).inc()

        self.label_metric(
            self.metrics.responses_by_status_view_method,
            request,
            response,
            **{
                "status": status,
                label_name: label_value,
                "method": method
            }
        ).inc()
        if hasattr(response, "charset"):
            self.label_metric(
                self.metrics.responses_by_charset,
                request,
                response,
                charset=str(response.charset),
            ).inc()
        if hasattr(response, "streaming") and response.streaming:
            self.label_metric(self.metrics.responses_streaming, request, response).inc()
        if hasattr(response, "content"):
            self.label_metric(self.metrics.responses_body_bytes, request, response).observe(len(response.content))
        if hasattr(request, "prometheus_after_middleware_event"):
            self.label_metric(
                self.metrics.requests_latency_by_view_method,
                request,
                response,
                **{
                    label_name: label_value,
                    "method": request.method,
                }
            ).observe(TimeSince(request.prometheus_after_middleware_event))
        else:
            self.label_metric(self.metrics.requests_unknown_latency, request, response).inc()
        return response

    def process_exception(self, request, exception):
        self.label_metric(self.metrics.exceptions_by_type, request, type=type(exception).__name__).inc()
        if hasattr(request, "resolver_match"):
            label_value = self._get_view_or_path(request)
            label_name = "path" if PROMETHEUS_USE_PATH_LABELS else "view"
            self.label_metric(
                self.metrics.requests_latency_by_view_method,
                request,
                **{
                    label_name: label_value,
                    "method": request.method,
                }
            ).observe(TimeSince(request.prometheus_after_middleware_event))
        else:
            self.label_metric(self.metrics.requests_unknown_latency, request).inc()
