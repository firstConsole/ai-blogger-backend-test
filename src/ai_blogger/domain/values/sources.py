"""Адреса, откуда канал берёт темы"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit, urlunsplit

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_URL_LENGTH = 2048
MAX_QUERY_LENGTH = 200
BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", "metadata"})
MAX_FEEDS = 40
MAX_QUERIES = 20
BRAVE_FREE_MONTHLY_QUERIES = 600
DAYS_IN_BILLING_MONTH = 30


@dataclass(frozen=True, slots=True)
class SourceUrl:
    """Адрес, по которому сервер пойдёт сам: лента или статья

    Проверки здесь дешёвые и не окончательные: имя может разрешиться в
    петлевой адрес, а ответ DNS — поменяться между проверкой и запросом.
    При загрузке адрес нужно проверить ещё раз, уже разрешённым.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > MAX_URL_LENGTH:
            raise InvalidValueError(f"адрес длиннее {MAX_URL_LENGTH} символов")

        parts = urlsplit(self.value)
        if parts.scheme not in ALLOWED_SCHEMES:
            raise InvalidValueError(
                f"поддерживаются только http и https, получено «{parts.scheme or 'без схемы'}»"
            )
        if parts.username or parts.password:
            raise InvalidValueError("адрес с логином и паролем внутри хранить не будем")

        host = _hostname(parts.netloc)
        if not host:
            raise InvalidValueError(f"в адресе не разобрать хост: «{self.value}»")
        if host in BLOCKED_HOSTS:
            raise InvalidValueError(f"«{host}» — это сам сервер, а не источник новостей")

        _check_host(host)

        if self.value != _normalized(self.value):
            raise InvalidValueError("адрес не приведён к каноническому виду, используйте parse")

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Привести адрес к каноническому виду"""
        return cls(_normalized(raw.strip()))

    @property
    def host(self) -> str:
        """Хост без порта и учётных данных"""
        return _hostname(urlsplit(self.value).netloc)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Поисковый запрос, которым канал ищет свежие темы"""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidValueError("пустой поисковый запрос ничего не найдёт")
        if len(self.value) > MAX_QUERY_LENGTH:
            raise InvalidValueError(
                f"запрос длиннее {MAX_QUERY_LENGTH} символов — это уже не запрос"
            )
        if any(character.isspace() and character != " " for character in self.value):
            raise InvalidValueError("в запросе допустимы только обычные пробелы")
        if self.value != " ".join(self.value.split()):
            raise InvalidValueError("лишние пробелы в запросе, используйте parse")

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Свернуть пробелы и убрать края"""
        return cls(" ".join(raw.split()))

    def __str__(self) -> str:
        return self.value


def _normalized(raw: str) -> str:
    parts = urlsplit(raw)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, parts.fragment)
    )


def _hostname(netloc: str) -> str:
    try:
        return urlsplit(f"//{netloc}").hostname or ""
    except ValueError:
        return ""


def _check_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        _reject_numeric_lookalike(host)
        return

    if not address.is_global:
        raise InvalidValueError(
            f"адрес {host} принадлежит служебному диапазону — оттуда новостей не бывает, "
            "зато бывают ключи доступа самой машины"
        )


def _reject_numeric_lookalike(host: str) -> None:
    """Отсекает адрес, записанный числом в обход проверки диапазонов"""
    last_label = host.rstrip(".").rsplit(".", 1)[-1]

    if not last_label or not last_label[0].isalpha():
        raise InvalidValueError(
            f"«{host}» не похоже на доменное имя: так записывают числовой адрес, "
            "чтобы обойти проверку"
        )


@dataclass(frozen=True, slots=True)
class TopicSources:
    """Источники тем канала: ленты и поисковые запросы"""

    feeds: tuple[SourceUrl, ...] = ()
    queries: tuple[SearchQuery, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.feeds)) != len(self.feeds):
            raise InvalidValueError("одна и та же лента добавлена дважды")
        if len(set(self.queries)) != len(self.queries):
            raise InvalidValueError("один и тот же запрос добавлен дважды")
        if len(self.feeds) > MAX_FEEDS:
            raise InvalidValueError(
                f"лент больше {MAX_FEEDS}: каждую опрашивают в каждом цикле, "
                f"и очередь захлебнётся раньше, чем принесёт пользу"
            )
        if len(self.queries) > MAX_QUERIES:
            raise InvalidValueError(
                f"запросов больше {MAX_QUERIES}: столько не укладывается "
                "в бесплатный бюджет поиска даже при одном цикле в сутки"
            )

    @classmethod
    def of(cls, feeds: Iterable[SourceUrl] = (), queries: Iterable[SearchQuery] = ()) -> Self:
        """Собрать набор, выбросив повторы и сохранив порядок владельца"""
        return cls(tuple(dict.fromkeys(feeds)), tuple(dict.fromkeys(queries)))

    @property
    def is_empty(self) -> bool:
        """Нечего опрашивать — темы могут приходить только вручную"""
        return not self.feeds and not self.queries

    def monthly_search_requests(self, cycles_per_day: int) -> int:
        """Сколько запросов к поиску уйдёт за месяц при такой частоте опроса"""
        if cycles_per_day < 0:
            raise InvalidValueError("частота опроса не может быть отрицательной")
        return len(self.queries) * cycles_per_day * DAYS_IN_BILLING_MONTH

    def fits_free_search_budget(self, cycles_per_day: int) -> bool:
        return self.monthly_search_requests(cycles_per_day) <= BRAVE_FREE_MONTHLY_QUERIES
