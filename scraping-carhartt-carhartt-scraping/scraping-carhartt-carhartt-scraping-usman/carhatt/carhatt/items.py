import scrapy


class CarhattItem(scrapy.Item):
    retailer_sku = scrapy.Field()
    gender = scrapy.Field()
    care = scrapy.Field()
    category = scrapy.Field()
    name = scrapy.Field()
    brand = scrapy.Field()
    url = scrapy.Field()
    description = scrapy.Field()
    image_url = scrapy.Field()
    skus = scrapy.Field()
