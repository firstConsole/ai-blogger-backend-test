"""Тесты адресов источников"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.sources import (
    MAX_FEEDS,
    MAX_QUERIES,
    MAX_QUERY_LENGTH,
    MAX_URL_LENGTH,
    SearchQuery,
    SourceUrl,
    TopicSources,
)


def test_parse_lowercases_scheme_and_host_but_not_the_path() -> None:
    """Схема и хост регистр не различают, а путь различает"""
    feed = SourceUrl.parse("  HTTPS://News.Example.COM/Feeds/RSS.xml  ")

    assert feed.value == "https://news.example.com/Feeds/RSS.xml"
    assert feed.host == "news.example.com"


def test_constructor_refuses_non_canonical_value() -> None:
    with pytest.raises(InvalidValueError, match="каноническому виду"):
        SourceUrl("HTTPS://news.example.com/rss")


@pytest.mark.parametrize(
    "raw",
    [
        "file:///etc/passwd",
        "gopher://internal:70/",
        "ftp://files.example.com/feed",
        "//news.example.com/rss",
        "news.example.com/rss",
    ],
)
def test_only_http_and_https_are_accepted(raw: str) -> None:
    """file:// прочитал бы файлы сервера, gopher:// — поговорил бы с внутренними сервисами"""
    with pytest.raises(InvalidValueError, match="http и https"):
        SourceUrl.parse(raw)


def test_credentials_inside_the_url_are_refused() -> None:
    """Такой адрес утечёт в логи и в настройки, а публичной ленте он не нужен"""
    with pytest.raises(InvalidValueError, match="логином и паролем"):
        SourceUrl.parse("https://user:secret@news.example.com/rss")


@pytest.mark.parametrize(
    "raw",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/rss",
        "http://10.0.0.5/rss",
        "http://192.168.1.1/rss",
        "http://172.16.0.1/rss",
        "http://0.0.0.0/rss",
        "http://[::1]/rss",
    ],
)
def test_service_ranges_are_refused(raw: str) -> None:
    """169.254.169.254 у облачных провайдеров отдаёт ключи доступа самой машины"""
    with pytest.raises(InvalidValueError, match="служебному диапазону"):
        SourceUrl.parse(raw)


def test_localhost_by_name_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="сам сервер"):
        SourceUrl.parse("http://localhost/rss")


@pytest.mark.parametrize("host", ["2130706433", "0x7f000001", "0177.0.0.1"])
def test_numeric_forms_of_a_loopback_address_are_refused(host: str) -> None:
    """127.0.0.1 можно записать числом, и ipaddress такие формы не разбирает

    Системный резолвер разбирает прекрасно: проверено, 2130706433 и
    0x7f000001 на этой машине дают 127.0.0.1. Без этой проверки они прошли
    бы мимо контроля диапазонов.
    """
    with pytest.raises(InvalidValueError, match="не похоже на доменное имя"):
        SourceUrl.parse(f"http://{host}/rss")


@pytest.mark.parametrize(
    "raw",
    [
        "https://news.example.com/rss",
        "http://8.8.8.8/feed.xml",
        "https://новости.рф/rss",
        "https://xn--b1agh1afp.xn--p1ai/rss",
        "https://news.example.com:8443/rss?lang=ru",
    ],
)
def test_ordinary_addresses_pass(raw: str) -> None:
    """Проект настраивается под любой канал, значит и под любую зону"""
    assert SourceUrl.parse(raw)


def test_address_without_a_host_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="не разобрать хост"):
        SourceUrl.parse("https:///rss")


def test_absurdly_long_address_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="длиннее"):
        SourceUrl.parse("https://news.example.com/" + "a" * MAX_URL_LENGTH)


def test_query_parse_collapses_whitespace() -> None:
    assert SearchQuery.parse("  нейросети   в    медицине \n").value == "нейросети в медицине"


def test_query_constructor_refuses_non_canonical_value() -> None:
    with pytest.raises(InvalidValueError, match="лишние пробелы"):
        SearchQuery("нейросети  в медицине")


@pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
def test_empty_query_is_refused(raw: str) -> None:
    with pytest.raises(InvalidValueError, match="ничего не найдёт"):
        SearchQuery.parse(raw)


def test_overlong_query_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="уже не запрос"):
        SearchQuery.parse("а" * (MAX_QUERY_LENGTH + 1))


@pytest.mark.parametrize("whitespace", ["\t", "\n", "\xa0"])
def test_exotic_whitespace_is_refused_by_the_constructor(whitespace: str) -> None:
    """Табуляция и перевод строки выдают склейку, а \xa0 — вставку из браузера"""
    with pytest.raises(InvalidValueError, match="обычные пробелы"):
        SearchQuery(f"нейросети{whitespace}в медицине")


def test_parse_turns_exotic_whitespace_into_ordinary_spaces() -> None:
    """Человеку, который вставил текст из браузера, отказывать незачем"""
    assert SearchQuery.parse("нейросети\xa0в\tмедицине\n").value == "нейросети в медицине"


def feed(number: int) -> SourceUrl:
    return SourceUrl.parse(f"https://news{number}.example.com/rss")


def test_sources_drop_repeats_and_keep_the_owner_order() -> None:
    sources = TopicSources.of(
        feeds=[feed(2), feed(1), feed(2)],
        queries=[SearchQuery.parse("нейросети"), SearchQuery.parse("нейросети")],
    )

    assert sources.feeds == (feed(2), feed(1))
    assert len(sources.queries) == 1


def test_channel_without_sources_is_allowed() -> None:
    """Темы можно добавлять руками — автоматический сбор просто не работает"""
    assert TopicSources().is_empty
    assert not TopicSources.of(feeds=[feed(1)]).is_empty


def test_too_many_feeds_are_refused() -> None:
    with pytest.raises(InvalidValueError, match="захлебнётся"):
        TopicSources.of(feeds=[feed(number) for number in range(MAX_FEEDS + 1)])


def test_too_many_queries_are_refused() -> None:
    with pytest.raises(InvalidValueError, match="бесплатный бюджет"):
        TopicSources.of(
            queries=[SearchQuery.parse(f"запрос {number}") for number in range(MAX_QUERIES + 1)]
        )


def test_constructor_refuses_a_repeated_feed() -> None:
    with pytest.raises(InvalidValueError, match="дважды"):
        TopicSources(feeds=(feed(1), feed(1)))


def test_search_budget_is_counted_before_the_bill_arrives() -> None:
    """Цикл в полчаса — это 48 опросов в сутки, и бюджет кончается втрое раньше

    Считать это нужно при настройке канала: у Brave бесплатны первые 600
    запросов в месяц, и один-единственный запрос, опрашиваемый каждые полчаса,
    даёт 1440. Поиск придётся опрашивать реже, чем ленты.
    """
    sources = TopicSources.of(queries=[SearchQuery.parse("нейросети")])

    assert sources.monthly_search_requests(cycles_per_day=48) == 1440
    assert not sources.fits_free_search_budget(cycles_per_day=48)

    assert sources.monthly_search_requests(cycles_per_day=20) == 600
    assert sources.fits_free_search_budget(cycles_per_day=20)


def test_budget_of_an_empty_set_costs_nothing() -> None:
    assert TopicSources().monthly_search_requests(cycles_per_day=48) == 0
    assert TopicSources().fits_free_search_budget(cycles_per_day=48)
