import scrapy
from w3lib.url import add_or_replace_parameters

from carhatt.items import CarhattItem


class CarhattSpider(scrapy.Spider):
    name = 'carhatt'
    allowed_domains = ['carhartt-wip.co.kr']
    BASE_URL = 'https://api.carhartt-wip.co.kr/v1'
    PRODUCTS_URL = '{base_url}/products?sort=&size=12&brandIds=15'
    PRODUCT_DETAIL = '{base_url}/products/{product_id}/detail'
    start_urls = [f'{BASE_URL}/categories?sourceSite=CARHARTT']

    def parse(self, response):
        category_data = response.json()

        for item in category_data.get('payload', []):
            if category_id := item.get('categoryId'):
                products_base_url = self.PRODUCTS_URL.format(base_url=self.BASE_URL)
                params = {
                    'mainCategoryId': category_id,
                    'page': '0',
                }
                products_url = add_or_replace_parameters(products_base_url, params)

            yield scrapy.Request(
                    products_url,
                    callback=self.parse_products_pages,
                    meta={'category_id': category_id}
                )

    def parse_products_pages(self, response):
        products_page_info = response.json()
        total_pages = products_page_info['payload']['totalPages']
        category_id = response.meta['category_id']

        for page in range(total_pages+1):
            products_base_url = self.PRODUCTS_URL.format(base_url=self.BASE_URL)
            params = {
                'mainCategoryId': category_id,
                'page': str(page),
            }
            product_url = add_or_replace_parameters(products_base_url, params)

            yield scrapy.Request(
                product_url,
                callback=self.parse_products,
            )

    def parse_products(self, response):
        products_page = response.json()
        products = products_page['payload']['content']
        parser = CarhattParser()

        for product in products:
            product_id = product.get('productId')
            product_detail_url = (
                self.PRODUCT_DETAIL.format(
                    base_url=self.BASE_URL,
                    product_id=product_id
                )
            )

            yield scrapy.Request(
                product_detail_url,
                callback=parser.parse,
            )


class CarhattParser(scrapy.Spider):
    name = 'carhatt_item'

    def extract_gender(self, product_details):
        gender_map = {'M': 'men', 'W': 'women', 'U': 'unisex-adults', 'C': 'C'}
        return gender_map.get(product_details['genderCode'], 'unisex-adults')

    def extract_retailer_sku(self, product_details):
        return product_details['productId']

    def extract_images(self, product_details):
        colour = product_details['productInfo']['color']
        return {colour: product_details['productImageUrls']}

    def extract_brand(self, product_details):
        return product_details['brandName']

    def extract_description(self, product_details):
        return product_details['info']

    def extract_name(self, product_details):
        return product_details['productName']

    def extract_sku(self, product_details):
        product_info = product_details['productInfo']
        product_sizes = product_details['productSizes']
        colour = product_info['color']
        price = product_details['currentPrice']

        sku = {}
        for size_info in product_sizes:
            size = size_info['sizeCode']
            sku_id = f'{colour}_{size}'
            sku_details = {
                'out_of_stock': size_info['currentStock'] == 0,
                'size': size,
                'price': price,
                'currency': 'KRW',
            }
            sku[sku_id] = sku_details

        return sku

    def extract_care(self, product_details):
        return [product_details['productInfo']['material']]

    def extract_category(self, product_details):
        return [product_details['categoryName']]

    def extract_product_url(self, product_details):
        product_id = product_details['productId']
        return f'https://www.carhartt-wip.co.kr/product/{product_id}'

    def parse(self, response):
        raw_product = response.json()
        product_details = raw_product['payload']
        item = CarhattItem()

        item['url'] = self.extract_product_url(product_details)
        item['category'] = self.extract_category(product_details)
        item['care'] = self.extract_care(product_details)
        item['gender'] = self.extract_gender(product_details)
        item['retailer_sku'] = self.extract_retailer_sku(product_details)
        item['name'] = self.extract_name(product_details)
        item['brand'] = self.extract_brand(product_details)
        item['image_url'] = self.extract_images(product_details)
        item['description'] = self.extract_description(product_details)
        item['skus'] = self.extract_sku(product_details)

        yield item
