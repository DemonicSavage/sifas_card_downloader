from bs4 import BeautifulSoup
from pathlib import Path
import re
import operator
import asyncio
import aiohttp


import utils
import json_utils
import consts
from classes import Card, Still


class Downloader:
    def __init__(self, path, img_type):
        self.path = utils.init_path(Path(path))
        self.objs = {}

        self.img_type = img_type

        utils.init_path(Path(self.path) / self.img_type.get_folder())

        self.list_parser = self.img_type.get_list_parser()
        self.item_parser = self.img_type.get_parser()

        self.updateables = []

    async def write_to_file(self, session, dest, url):
        response = await session.get(f"https:{url}")
        response_data = await response.read()
        with open(dest, 'wb') as f:
            f.write(response_data)

    async def get_images(self, session, item):
        paths = item.get_paths(self.path)
        try:
            await self.download_images(session, paths, item)
        except Exception as e:
            print(f"Couldn't download card {item.key}: {e}.")

    async def create_image_file(self, session, path, item, i):
        if not Path(path).exists() or item.key in self.updateables:
            await self.write_to_file(session, Path(path), item.get_urls()[i])

            message = f"Downloaded item {item.key}"
            if type(item) is Card:
                message += f", {'idolized' if i == 1 else 'normal'}"
            message += "."

            print(message)

    async def download_images(self, session, paths, item):
        for i, path in enumerate(paths):
            await self.create_image_file(session, path, item, i)

    async def update_if_needed(self, item):
        if item.needs_update():
            async with aiohttp.ClientSession() as item_session:
                self.item_parser.set_session(item_session)
                n, updated_item = await self.item_parser.get_item(item.key)

            if item.get_urls()[0] != updated_item.get_urls()[0]:
                self.updateables.append(item.key)

            for i in range(len(item.get_urls())):
                item.set_url(i, updated_item.get_urls()[i])

    async def add_item_to_object_list(self, item):
        n, obj = await self.item_parser.get_item(item)
        self.objs[n] = obj
        print(f"Getting item {n}.")

    async def get_cards_from_parser(self):
        page_num = 1

        async with aiohttp.ClientSession() as list_session:
            self.list_parser.set_session(list_session)
            page_requests = [self.list_parser.get_page(
                i) for i in range(1, await self.list_parser.get_num_pages()+1)]

            pages = await asyncio.gather(*page_requests, return_exceptions=False)

        async with aiohttp.ClientSession() as item_session:
            self.item_parser.set_session(item_session)

            for page in pages:
                tasks = []
                for item in page:
                    if item not in self.objs:
                        tasks.append(self.add_item_to_object_list(item))
                results = await asyncio.gather(*tasks, return_exceptions=False)
                page_num += 1

    async def download(self):
        async with aiohttp.ClientSession() as item_session:
            tasks = []
            for key, item in self.objs.items():
                tasks.append(self.get_images(item_session, item))
            results = await asyncio.gather(*tasks, return_exceptions=False)

    async def update(self):
        print("Searching for new or missing items...")
        await self.get_cards_from_parser()

        print("Checking if items can be updated to better resolution...")
        for key, item in self.objs.items():
            await self.update_if_needed(item)

        self.update_json_file()
        print("Updated items database.")

    def update_json_file(self):
        self.objs = dict(sorted(self.objs.items(), reverse=True))
        json_utils.dump_to_file(json_utils.to_json(
            self.objs), self.path, self.img_type)
