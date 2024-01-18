import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from clothscraper.items import ClothscraperItem


class SixPMSpiderParser(scrapy.Spider):
    name = '6pm_item'

    def product_retailer_sku(self, response):
        return response.css('span[itemprop="sku"]::text').get()

    def product_category(self, response):
        return response.css('#breadcrumbs a::text').getall()[1:-1]

    def product_name(self, response):
        return response.css('span[itemprop="name"]::text').get()

    def product_brand(self, response):
        brand_name_selector = 'span[itemprop="brand"] + span::text'
        return response.css(brand_name_selector).get()

    def product_images(self, response):
        colour = response.css('span:contains("Color:") + span::text').get()
        images_selector = '#productThumbnails source::attr(srcset)'
        images = response.css(images_selector).getall()
        return {colour: [img.split()[0] for img in images]}

    def product_sku_details(self, response):
        colour = response.css('span:contains("Color:") + span::text').get()
        price = response.css('span[itemprop="price"]::attr(content)').get()
        currency = response.css('span[itemprop="priceCurrency"]::attr(content)').get()
        sizes = response.css('input::attr(data-label)').getall()
        stocks = response.css('input::attr(aria-label)').getall()
        out_of_stock = ['Out of Stock' in stock for stock in stocks]

        sku_details = {}
        sku = {
            'colour': colour,
            'currency': currency,
            'price': price
        }

        for size, stock in zip(sizes, out_of_stock):
            sku['size'] = size
            sku['out_of_stock'] = stock
            sku_id = f'{sku["colour"]}_{size}'
            sku_details[sku_id] = sku.copy()

        if not sizes:
            sku_details[f'{sku["colour"]}_One Size'] = sku

        return sku_details

    def product_description(self, response):
        product_features = response.css('div[role="presentation"] li')
        description = [product_features[0].css('::text').get()]

        for feature in range(2, len(product_features)):
            text = product_features[feature].css('::text').get()
            description.append(text.strip().replace('\n', '') if text else '')

        return description

    def parse(self, response):
        item = ClothscraperItem()
        item['retailer_sku'] = self.product_retailer_sku(response)
        item['category'] = self.product_category(response)
        item['name'] = self.product_name(response)
        item['brand'] = self.product_brand(response)
        item['url'] = response.url
        item['description'] = self.product_description(response)
        item['image_url'] = self.product_images(response)
        item['skus'] = self.product_sku_details(response)
        item['gender'] = response.meta['gender']

        yield item


class SixPMSpiderCrawler(CrawlSpider):
    name = '6pmV2'
    allowed_domains = ['6pm.com']
    start_urls = ['https://www.6pm.com/']

    rules = (
        Rule(
            LinkExtractor(
                restrict_css='a:contains("View all..."), '
                             '#searchPagination a[rel="next"]'
            ),
            process_request='get_gender'
        ),
        Rule(
            LinkExtractor(restrict_css='article a'),
            process_request='get_gender',
            callback=SixPMSpiderParser().parse,
        ),
    )

    def get_gender(self, request, response):
        if response.meta.get('gender'):
            request.meta.update({'gender': response.meta['gender']})
            return request

        genders = ['women', 'men', 'boys', 'girls']
        gender = next(
            (gender for gender in genders if gender in request.url),
            'unisex-adults'
        )
        request.meta.update({'gender': gender})

        return request
