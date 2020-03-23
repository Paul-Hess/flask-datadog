import time

from datadog.dogstatsd.base import DogStatsd
from datadog.dogstatsd.context import TimedContextManagerDecorator
from flask import g, request

from src.main.config import DEFAULTS


class TimerWrapper(TimedContextManagerDecorator):
    def __init__(self, statsd, *args, **kwargs):
        super(TimerWrapper, self).__init__(statsd, *args, **kwargs)

    def start(self):
        self.__enter__()

    def stop(self):
        self.__exit__(None, None, None)


class StatsD(object):

    def __init__(self, app, config, statsd=None):
        self.config = config
        for key, value in DEFAULTS.items():
            self.config.setdefault(key, value)
        self.statsd = DogStatsd(host=self.config['STATSD_HOST'],
                                port=self.config['STATSD_PORT'],
                                max_buffer_size=self.config['STATSD_MAX_BUFFER_SIZE'],
                                namespace=self.config['STATSD_NAMESPACE'],
                                constant_tags=self.config['STATSD_TAGS'],
                                use_ms=self.config['STATSD_USEMS']) \
            if statsd is None \
            else statsd
        self.app = app

    def timer(self, *args, **kwargs):
        return TimerWrapper(self.statsd, *args, **kwargs)

    def incr(self, *args, **kwargs):
        return self.statsd.increment(*args, **kwargs)

    def decr(self, *args, **kwargs):
        return self.statsd.decrement(*args, **kwargs)

    def initialize_lifecycle_hooks(self):
        self.app.before_request(self.before_request)
        self.app.after_request(self.after_request)

    def before_request(self):

        g.flask_datadog_start_time = time.time()
        g.flask_datadog_request_tags = []

        if self.config['DATADOG_RESPONSE_AUTO_TAG']:
            self.add_request_tags([
                '{tag_name}:{endpoint}'.format(tag_name=self.config['DATADOG_RESPONSE_ENDPOINT_TAG_NAME'],
                                               endpoint=str(request.endpoint).lower()),
                '{tag_name}:{method}'.format(tag_name=self.config['DATADOG_RESPONSE_METHOD_TAG_NAME'],
                                             method=request.method.lower()),
            ])

    def after_request(self, response):

        if not hasattr(g, 'flask_datadog_start_time'):
            return response

        elapsed = time.time() - g.flask_datadog_start_time
        if self.use_ms:
            elapsed = int(round(1000 * elapsed))

        if self.config['DATADOG_RESPONSE_AUTO_TAG']:
            self.add_request_tags(['status_code:%s' % (response.status_code, )])

        tags = self.get_request_tags()
        sample_rate = self.config['DATADOG_RESPONSE_SAMPLE_RATE']

        self.statsd.timing(self.config['DATADOG_RESPONSE_METRIC_NAME'],
                           elapsed,
                           tags,
                           sample_rate)

        if 'content-length' in response.headers:
            size = int(response.headers['content-length'])
            self.statsd.histogram(self.config['DATADOG_RESPONSE_SIZE_METRIC_NAME'],
                                  size,
                                  tags,
                                  sample_rate)
        return response

    def get_request_tags(self):
        return getattr(g, 'flask_datadog_request_tags', [])

    def add_request_tags(self, tags):
        current_tags = self.get_request_tags()
        g.flask_datadog_request_tags = current_tags + tags
        return g.flask_datadog_request_tags

    def __getattr__(self, name):
        if self.statsd and hasattr(self.statsd, name):
            return getattr(self.statsd, name)
        raise AttributeError('\'StatsD\' has attribute \'{name}\''.format(name=name))

    def __enter__(self):
        return self.statsd.__enter__()

    def __exit__(self, *args, **kwargs):
        return self.statsd.__exit__(*args, **kwargs)
