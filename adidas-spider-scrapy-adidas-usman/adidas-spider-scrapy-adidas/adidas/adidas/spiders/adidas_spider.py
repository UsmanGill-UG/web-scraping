from scrapy import Spider, Request

from adidas.items import AdidasItem


class Mixin:
    start_urls = ['https://ecp-public.api.adidas.com.cn/o2cms/v2/pub/navigation?']

    allowed_domains = [
        'www.adidas.com.cn', 'static1.adidas.com.cn',
        'ecp-public.api.adidas.com.cn'
    ]

    SITE_URL = 'https://www.adidas.com.cn'

    listings_api_t = 'https://ecp-public.api.adidas.com.cn/o2srh/v1/pub/platform-products/search?'\
                     'page={page}&pageSize=6&abTest=A&contentId={content_id}'

    sku_api_t = 'https://ecp-public.api.adidas.com.cn/o2inv/v1/pub/inv-query/batch/'\
                'article-shop-inv?articleIdList={article_id}'

    product_detail_api_t = 'https://ecp-public.api.adidas.com.cn/o2pcm/v1/pub/platform-products/'\
                           'detail?articleId={article_id}'

    headers = {
        'x-source': 'COM',
        'origin': 'https://www.adidas.com.cn'
    }

    currency = 'YEN'


class AdidasCrawlSpider(Spider, Mixin):
    name = 'adidas-crawl'

    def start_requests(self):
        yield Request(self.start_urls[0], self.parse, headers=self.headers)

    def parse(self, response):
        categories_id = [raw_category['contentId'] for raw_category in response.json()['content']]
        yield from [
            Request(
                self.listings_api_t.format(page=0, content_id=content_id), self.parse_pagination,
                headers=self.headers, meta={'content_id': content_id}
            ) for content_id in categories_id
        ]

    def parse_pagination(self, response):
        yield from self.parse_products(response)
        content_id = response.meta['content_id']

        yield from [
            Request(
                self.listings_api_t.format(page=page, content_id=content_id),
                self.parse_products, headers=self.headers,
            ) for page in range(1, response.json()['totalPages'] + 1)
        ]

    def parse_products(self, response):
        yield from [
            Request(
                self.product_detail_api_t.format(article_id=product['articleId']),
                AdidasParserSpider().parse, headers=self.headers
            ) for product in response.json()['content']
        ]


class AdidasParserSpider(Spider, Mixin):
    name = 'adidas-parser'

    def parse(self, response):
        if '<PlatformProductDetailExpandVO>' in response.text:
            return

        raw_product = response.json()
        garment = AdidasItem()

        garment['image_url'] = self.product_image_url(raw_product)
        garment['name'] = self.product_name(raw_product)
        garment['retailer_sku'] = self.product_retailer_sku(raw_product)
        garment['url'] = self.product_url(garment['retailer_sku'])
        garment['category'] = self.product_category(raw_product)
        garment['brand'] = self.product_brand(raw_product)
        garment['description'] = []
        garment['care'] = []
        garment['skus'] = self.product_skus(raw_product)
        garment['request'] = [self.stock_request(garment)]

        yield self.next_request_or_garment(garment)

    def parse_product_skus(self, response):
        garment = response.meta['garment']
        sku_details = response.json()[0]['articleStockSkuVOList']

        for sku_id, sku in garment['skus'].items():
            stock_detail = next((detail for detail in sku_details if detail['sizeName'] == sku['size']), None)
            sku['out_of_stock'] = not stock_detail['available']

        return self.next_request_or_garment(garment)

    def next_request_or_garment(self, garment):
        return garment['request'].pop() if garment['request'] else garment

    def product_skus(self, raw_product):
        skus = {}
        common_sku = {
            'colour': self.product_color(raw_product),
            'price': self.product_price(raw_product),
            'currency': self.currency,
        }

        for sku_details in raw_product['skuList']:
            sku = common_sku.copy()
            sku_id = f'{sku["colour"]}_{sku_details["sizeName"]}'
            sku['size'] = sku_details['sizeName']
            skus[sku_id] = sku

        return skus

    def product_url(self, article_id):
        return f'{self.SITE_URL}/pdp?articleId={article_id}'

    def product_image_url(self, raw_product):
        return raw_product['imageUrlList']

    def product_retailer_sku(self, raw_product):
        return raw_product['articleId']

    def product_name(self, raw_product):
        return raw_product['enArticleName']

    def product_gender(self, raw_product):
        return raw_product['gender']

    def product_brand(self, raw_product):
        return raw_product['brandName']

    def product_category(self, raw_product):
        return raw_product['category']

    def product_price(self, raw_product):
        return raw_product['salePrice']

    def product_color(self, raw_product):
        return raw_product['colorDisplay']

    def stock_request(self, garment):
        return Request(
            self.sku_api_t.format(article_id=garment['retailer_sku']),
            self.parse_product_skus,
            headers=self.headers,
            meta={'garment': garment}
        )
