from pytest import fixture
from flask_datadog import StatsD, TimerWrapper

from config import DEFAULTS


@fixture(scope="function", name="default_statsd")
def get_blank_client(mocker):
    app = mocker.patch("flask.Flask")
    config = {}
    return StatsD(app, config)


@fixture(scope="function", name="custom_config")
def get_custom_config():
    return {
        "STATSD_HOST": '127.0.0.1',
        "STATSD_MAX_BUFFER_SIZE": 100,
        "STATSD_NAMESPACE": "test_flask",
        "STATSD_PORT": 8124,
        "STATSD_TAGS": ["key:value"],
        "STATSD_USEMS": True,
    }


@fixture(scope="function", name="custom_statsd")
def get_custom_client(custom_config, mocker):
    app = mocker.patch("flask.Flask")
    return StatsD(app, custom_config)


@fixture(scope="function", name="mocked_statsd")
def get_mocked_client(mocker):
    app = mocker.patch("flask.Flask")
    statsd = mocker.patch("datadog.dogstatsd.base.DogStatsd")
    config = {}
    return StatsD(app, config, statsd)


def test_statsd_client_default_settings(default_statsd):
    internal_client = default_statsd.statsd
    assert internal_client.host == DEFAULTS["STATSD_HOST"]
    assert internal_client.port == DEFAULTS["STATSD_PORT"]
    assert internal_client.namespace == DEFAULTS["STATSD_NAMESPACE"]
    assert internal_client.max_buffer_size == DEFAULTS["STATSD_MAX_BUFFER_SIZE"]
    assert not len(internal_client.constant_tags)
    assert internal_client.use_ms == DEFAULTS["STATSD_USEMS"]


def test_statsd_client_custom_settings(custom_statsd, custom_config):
    internal_client = custom_statsd.statsd
    assert internal_client.host == custom_config["STATSD_HOST"]
    assert internal_client.port == custom_config["STATSD_PORT"]
    assert internal_client.namespace == custom_config["STATSD_NAMESPACE"]
    assert internal_client.max_buffer_size == custom_config["STATSD_MAX_BUFFER_SIZE"]
    assert internal_client.constant_tags[0] == custom_config["STATSD_TAGS"][0]
    assert internal_client.use_ms


def test_statsd_client_internal_client(mocked_statsd):
    metric = "metric"
    value = "value"
    tags = ["key:value"]
    mocked_statsd.incr(metric, value, tags)
    mocked_statsd.statsd.increment.assert_called_once_with(metric, value, tags)
    mocked_statsd.decr(metric, value, tags)
    mocked_statsd.statsd.decrement.assert_called_once_with(metric, value, tags)
    mocked_statsd.count(metric, value, tags)
    mocked_statsd.statsd.count.assert_called_once_with(metric, value, tags)
    assert isinstance(mocked_statsd.timer(), TimerWrapper)


def test_statsd_client_lifecycle(mocked_statsd):
    mocked_statsd.initialize_lifecycle_hooks()
    mocked_statsd.app.before_request.assert_called_once_with(mocked_statsd.before_request)
    mocked_statsd.app.after_request.assert_called_once_with(mocked_statsd.after_request)
