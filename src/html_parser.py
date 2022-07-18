from __future__ import annotations

import re
from abc import ABC, abstractmethod
from html import unescape
from typing import TYPE_CHECKING, Optional, cast

import aiohttp

import consts

if TYPE_CHECKING:
    from classes import Card, Item, Still


class Parser(ABC):
    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None

    def set_session(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def get_html(self, num: int) -> str:
        if isinstance(self.session, aiohttp.ClientSession):
            html: aiohttp.ClientResponse = await self.session.get(self.get_url(num))

        return unescape(await html.text())

    async def get_item(self, num: int) -> tuple[int, Item]:
        return await self.create_item(num)

    @abstractmethod
    async def create_item(self, num: int) -> tuple[int, Item]:
        ...

    @abstractmethod
    def get_url(self, num: int) -> str:
        ...


class ListParser(Parser):
    def __init__(self, img_type: type[Item]):
        super().__init__()
        self.url: str = img_type.get_list_template()

    def get_url(self, num: int) -> str:
        return f"{self.url}{num}"

    async def get_page(self, num: int) -> list[int]:
        pattern: re.Pattern[str] = re.compile(
            r'<div class=".+" data-item="allstars/card" data-item-id="([0-9]+)">'
        )

        page: str = await self.get_html(num)
        nums: list[int] = [int(num) for num in pattern.findall(page)]

        return sorted(nums, reverse=True)

    async def get_num_pages(self) -> int:
        pattern: re.Pattern[str] = re.compile(
            r'<a href="/allstars/cards/\?page=([0-9]+)">[0-9]+</a>'
        )

        page: str = await self.get_html(1)
        num: str = pattern.findall(page)[-1]

        return int(num)

    async def create_item(self, num: int) -> tuple[int, Item]:
        ...


class CardParser(Parser):
    def get_url(self, num: int) -> str:
        return f"{consts.CARD_URL_TEMPLATE}{num}"

    async def create_item(self, num: int) -> tuple[int, Card]:
        from classes import Card

        self.html = await self.get_html(num)

        urls: tuple[str, str] = self.get_item_image_urls()

        idol: str = self.get_item_info("idol")
        rarity: str = self.get_item_info("rarity")
        attr: str = self.get_item_info("attribute")
        unit: str = self.get_item_info("i_unit")
        sub: str = self.get_item_info("i_subunit")
        year: str = self.get_item_info("i_year")

        new_card: Card = Card(
            num, idol, rarity, attr, unit, sub, year, urls[0], urls[1]
        )
        return num, new_card

    def get_item_image_urls(self) -> tuple[str, str]:
        pattern: re.Pattern[str] = re.compile(
            r'<a href="(//i.idol.st/u/card/art/.+?)" target="_blank">'
        )

        all_urls: list[str] = pattern.findall(self.html)

        return all_urls[0], all_urls[1]

    def get_data_field(self, field: str) -> str:

        match: re.Match[str] = cast(
            re.Match[str],
            re.search(
                f'<tr data-field="{field}" class="">(.+?)</tr>', self.html, re.DOTALL
            ),
        )
        return match.group(0)

    def get_item_info(self, info: str) -> str:
        if info == "idol":
            data: str = self.get_data_field("idol")
            pattern: re.Pattern[str] = re.compile(
                r'<span class="text_with_link">(.+?)<br>'
            )
            match: re.Match[str] = cast(re.Match[str], pattern.search(data))
            return match.group(1)

        data = self.get_data_field(info)
        match = cast(re.Match[str], re.findall(r"<td>(.+?)</td>", data, re.DOTALL))
        return match[-1].strip()


class StillParser(Parser):
    def get_url(self, num: int) -> str:
        return f"{consts.STILL_URL_TEMPLATE}{num}"

    async def create_item(self, num: int) -> tuple[int, Still]:
        from classes import Still

        self.html = await self.get_html(num)

        url: str = self.get_item_image_url()

        new_item: Still = Still(num, url)
        return num, new_item

    def get_item_image_url(self) -> str:
        pattern: re.Pattern[str] = re.compile(
            r'<a href="(//i.idol.st/u/card/art/.+?)" target="_blank">'
        )

        all_urls: list[str] = pattern.findall(self.html)

        return all_urls[0]
