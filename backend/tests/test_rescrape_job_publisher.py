from adapters.outbound.messaging.rescrape_job_publisher import RescrapeJobPublisher


class _FakeChannel:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.published = []
        self.declared_queues = []
        self.is_open = True

    def queue_declare(self, queue: str, durable: bool = True):
        self.declared_queues.append((queue, durable))

    def basic_publish(self, **kwargs):
        if self.should_fail:
            raise RuntimeError("channel publish error")
        self.published.append(kwargs)


class _FakeConnection:
    def __init__(self, channel: _FakeChannel):
        self._channel = channel
        self.is_closed = False

    def channel(self):
        return self._channel

    def close(self):
        self.is_closed = True


def test_rescrape_job_publisher_declares_queue_and_publishes_job_id() -> None:
    calls = {"count": 0}
    channel = _FakeChannel()

    def _factory():
        calls["count"] += 1
        return _FakeConnection(channel)

    publisher = RescrapeJobPublisher(connection_factory=_factory)
    publisher.publish(42)

    assert calls["count"] == 1
    assert channel.declared_queues == [("hunt-scraping-rescrape", True)]
    assert channel.published[0]["routing_key"] == "hunt-scraping-rescrape"
    assert '"job_id": 42' in channel.published[0]["body"]


def test_rescrape_job_publisher_reconnects_after_failure() -> None:
    calls = {"count": 0}
    first_channel = _FakeChannel(should_fail=True)
    second_channel = _FakeChannel()

    def _factory():
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeConnection(first_channel)
        return _FakeConnection(second_channel)

    publisher = RescrapeJobPublisher(connection_factory=_factory)
    publisher.publish(7)

    assert calls["count"] == 2
    assert second_channel.published[0]["routing_key"] == "hunt-scraping-rescrape"
