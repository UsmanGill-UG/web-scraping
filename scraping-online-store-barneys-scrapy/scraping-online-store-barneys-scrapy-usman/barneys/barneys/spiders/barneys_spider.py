import scrapy

from barneys.items import BarneysItem


class BarneysCrawler(scrapy.Spider):
    name = 'barneys'
    allowed_domains = ['onlinestore.barneys.co.jp']
    start_urls = ['https://onlinestore.barneys.co.jp/']

    def get_category_links(self, response):
        return response.xpath(
            '//div[@class="level-2-cc"]/preceding-sibling::a[1]/@href'
        ).getall()

    def get_next_page(self, response):
        return response.css('.infinite-scroll-placeholder::attr("data-grid-url")').get()

    def get_product_links(self, response):
        return response.css('.name-link::attr("href")').getall()

    def parse_category_page(self, response):
        parser = BarneysParser()
        products_link = self.get_product_links(response)

        yield from (
            scrapy.Request(
                url=response.urljoin(link),
                callback=parser.parse
            )
            for link in products_link
        )

        if next_page := self.get_next_page(response):
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_category_page
            )

    def parse(self, response):
        category_links = self.get_category_links(response)

        yield from (
            scrapy.Request(
                url=response.urljoin(link),
                callback=self.parse_category_page
            )
            for link in category_links
        )


class BarneysParser(scrapy.Spider):
    name = 'barneys_item'

    def extract_retailer_sku(self, response):
        return response.css('dt:contains("・品番") + dd::text').get().strip()

    def extract_category(self, response):
        return response.css('dt:contains("・カテゴリー") + dd a::text').get().strip()

    def extract_gender(self, response):
        genders = {
            "ウィメンズ": 'women',
            "メンズ": 'men',
            "キッズ＆ベビー": 'kids'
        }
        gender = response.css('dt:contains("・タイプ") + dd a::text').get().strip()

        return genders.get(gender, 'unisex-adults')

    def extract_care(self, response):
        return response.css('dt:contains("・素材") + dd::text').get().strip()

    def extract_name(self, response):
        return response.css('.product-name::text').get()

    def extract_brand(self, response):
        return response.css('.brand-link::text').get().strip()

    def extract_price(self, response):
        currency_price = response.css('.product-sales-price::text').get()
        return currency_price.split()[1]

    def extract_colour(self, response):
        return response.css('.selectable.selected .color img::attr("alt")').get()

    def extract_colour_links(self, response):
        return response.css('#color_select .selectable .swatchanchor::attr("href")').getall()

    def extract_images(self, response):
        return {
            self.extract_colour(response): response.css('.gallery-thumbs img::attr("src")').getall()
        }

    def extract_sizes(self, response):
        sizes = response.css('div#size_select span::text').getall()
        return ['One_Size'] if sizes[0] == 'NONE' else sizes

    def extract_stock_status(self, response):
        stock_message = response.css('.in-stock-msg::text').get()
        return stock_message not in ['在庫あり', '残り1 点']

    def extract_sku_details(self, response):
        colour = self.extract_colour(response)
        price = self.extract_price(response)
        sizes = self.extract_sizes(response)

        sku_details = {}
        sku = {
            'colour': colour,
            'currency': 'YEN',
            'price': price
        }
        for size in sizes:
            sku['size'] = size
            sku['out_of_stock'] = self.extract_stock_status(response)
            sku_id = f'{sku["colour"]}_{size}'
            sku_details[sku_id] = sku.copy()

        return sku_details

    def extract_description(self, response):
        raw_product_description = response.css('.data_text::text').getall()
        return [
            description.strip() for description in raw_product_description if description.strip()
        ]

    def parse_color_item(self, response):
        item = response.meta['item']

        item['url'] = response.url
        item['skus'] = self.extract_sku_details(response)
        item['image_url'] = self.extract_images(response)

        yield item

    def parse(self, response):
        raw_product_color_links = self.extract_colour_links(response)
        product_color_links = [url for url in raw_product_color_links if url]
        product_color_links = [response.url if "color=&" in url else url for url in product_color_links]

        item = BarneysItem()
        item['retailer_sku'] = self.extract_retailer_sku(response)
        item['category'] = self.extract_category(response)
        item['name'] = self.extract_name(response)
        item['brand'] = self.extract_brand(response)
        item['description'] = self.extract_description(response)
        item['gender'] = '' if 'home' in response.url else self.extract_gender(response)
        item['care'] = self.extract_care(response)

        for link in product_color_links:
            yield scrapy.Request(
                url=link,
                callback=self.parse_color_item,
                meta={
                    'item': item
                }
            )
