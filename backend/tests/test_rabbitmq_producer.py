from adapters.outbound.messaging.rabbitmq_producer import RabbitMQProducer
from application.domain.entities.scraped_item import ScrapedData, ScrapedItem


class _FakeChannel:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.published = 0
        self.is_open = True

    def basic_publish(self, **kwargs):
        if self.should_fail:
            raise RuntimeError("channel publish error")
        self.published += 1


class _FakeConnection:
    def __init__(self, channel: _FakeChannel):
        self._channel = channel
        self.is_closed = False

    def channel(self):
        return self._channel

    def close(self):
        self.is_closed = True


def _item() -> ScrapedItem:
    return ScrapedItem(
        url="https://example.com/item/1",
        source_name="chaozao",
        category_name="agribusiness",
        scraped_data=ScrapedData(title="Item"),
    )


def test_producer_uses_lazy_connection_factory_only_on_publish() -> None:
    calls = {"count": 0}
    channel = _FakeChannel()

    def _factory():
        calls["count"] += 1
        return _FakeConnection(channel)

    producer = RabbitMQProducer(connection_factory=_factory)
    assert calls["count"] == 0

    producer.publish(_item(), routing_key="agribusiness")
    assert calls["count"] == 1
    assert channel.published == 1


def test_producer_reconnects_and_retries_after_publish_failure() -> None:
    calls = {"count": 0}
    first_channel = _FakeChannel(should_fail=True)
    second_channel = _FakeChannel(should_fail=False)

    def _factory():
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeConnection(first_channel)
        return _FakeConnection(second_channel)

    producer = RabbitMQProducer(connection_factory=_factory)
    producer.publish(_item(), routing_key="agribusiness")

    assert calls["count"] == 2
    assert second_channel.published == 1
