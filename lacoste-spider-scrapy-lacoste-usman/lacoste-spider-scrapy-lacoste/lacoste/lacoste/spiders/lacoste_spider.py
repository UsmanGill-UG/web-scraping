import json

from scrapy import Request, Spider

from lacoste.items import LacosteItem


class LacosteSpider(Spider):
    name = 'lacoste'
    BASE_URL = 'https://www.lacoste.co.th'
    start_urls = f'{BASE_URL}/graphql'
    headers = {
        'Content-Type': 'application/json',
    }

    def start_requests(self):
        home_page_payload = {
            "operationName": "navigationMenu",
            "query": """
            query navigationMenu($id: Int!) {
              category(id: $id) {
                id
                name
                description
                children {
                  id
                  url_path
                  children {
                    id
                    position
                    url_path
                    children {
                      id
                      url_path
                      children {
                        id
                        url_path
                      }
                    }
                  }
                }
              }
            }
          """,
            "variables": {
                "id": 2
            }
        }

        yield Request(
            url=self.start_urls,
            method='POST',
            headers=self.headers,
            body=json.dumps(home_page_payload),
            callback=self.parse,
            dont_filter=True
        )

    def get_listings_payload(self, id_value, current_page=1):
        return {
            "operationName": "category",
            "query": """
            query category(
                    $id: Int!,
                    $pageSize: Int!,
                    $currentPage: Int!,
                    $filter: ProductAttributeFilterInput,
                    $sort: ProductAttributeSortInput
            ) {
              category(id: $id) {
                id
                description
                name
                name_en
                image
                product_count
              }
              products(
                pageSize:
                $pageSize,
                currentPage: $currentPage,
                filter: $filter,
                sort: $sort
              ) {
                items {
                  id
                  meta_description
                  name
                  item_category
                  item_category2
                  item_category3
                  item_category4
                  item_category5
                  url_key
                  price {
                    regularPrice {
                      amount {
                        value
                        currency
                      }
                    }
                  }
                  lacoste_colours
                }
                page_info {
                  total_pages
                }
                total_count
              }
            }""",
            "variables": {
                "currentPage": current_page,
                "id": id_value,
                "idString": str(id_value),
                "onServer": True,
                "pageSize": 32,
                "filter": {"category_id": {"eq": str(id_value)}},
                "sort": {"position": "DESC"}
            }
        }

    def get_product_payload(self, url_key):
        return {
            "operationName": "productDetail",
            "query": """
                query productDetail($urlKey: String) {
                    productDetail: products(filter: {url_key: {eq: $urlKey}}) {
                        items {
                            __typename
                            meta_description
                            name
                            item_category
                            item_category3
                            price {
                                regularPrice {
                                    amount {
                                        currency
                                        value
                                    }
                                }
                            }
                            sku
                            care_instructions
                            url_key
                            ... on ConfigurableProduct {
                                configurable_options {
                                    attribute_code
                                    attribute_id
                                    label
                                    values {
                                        label
                                        value_index
                                    }
                                }
                                variants {
                                    attributes {
                                        code
                                        value_index
                                    }
                                    product {
                                        media_gallery_entries {
                                            file
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            """,
            "variables": {
                "onServer": True,
                "urlKey": url_key
            }
        }

    def remove_second_to_last_word(self, s):
        parts = s.split('-')
        if len(parts) > 2:
            del parts[-2]
        return '-'.join(parts)

    def parse_products(self, response):
        parser = LacosteParser()
        raw_products = response.json()['data']
        products = raw_products['products']['items']

        for product in products:
            url_key = self.remove_second_to_last_word(product['url_key'])
            yield Request(
                url=self.start_urls,
                method='POST',
                headers=self.headers,
                body=json.dumps(self.get_product_payload(url_key)),
                callback=parser.parse,
                meta={
                    'url_path': response.meta["url_path"],
                    'url_key': url_key,
                },
                dont_filter=True
            )

    def parse_listings(self, response):
        total_pages = response.meta['total_pages']
        id_value = response.meta['id']
        yield from (
            Request(
                url=self.start_urls,
                method='POST',
                headers=self.headers,
                body=json.dumps(self.get_listings_payload(id_value, page)),
                callback=self.parse_products,
                meta={
                    'id': id_value,
                    'url_path': response.meta['url_path'],
                },
                dont_filter=True
            ) for page in range(1, total_pages + 1)
        )

    def parse_total_pages_listings(self, response):
        page_details = response.json()['data']
        total_pages = page_details['products']['page_info']['total_pages']
        id_value = response.meta['id']
        yield Request(
            url=self.start_urls,
            method='POST',
            headers=self.headers,
            body=json.dumps(self.get_listings_payload(id_value)),
            callback=self.parse_listings,
            meta={
                'id': id_value,
                'url_path': response.meta['url_path'],
                'total_pages': total_pages,
            },
            dont_filter=True
        )

    def extract_last_sub_categories(self, item_list):
        result = []

        for item in item_list:
            if "children" in item:
                result.extend(self.extract_last_sub_categories(item["children"]))
            else:
                result.append({
                    "id": item["id"],
                    "url_path": item["url_path"],
                })

        return result

    def parse(self, response):
        main_page_details = response.json()
        all_categories = main_page_details['data']['category']['children'][0]['children']
        sub_categories = self.extract_last_sub_categories(all_categories)

        yield from (
            Request(
                url=self.start_urls,
                method='POST',
                headers=self.headers,
                body=json.dumps(self.get_listings_payload(category['id'])),
                callback=self.parse_total_pages_listings,
                meta={
                    'id': category['id'],
                    'url_path': category['url_path']
                },
                dont_filter=True
            ) for category in sub_categories
        )


class LacosteParser(Spider):
    name = 'lacoste_item'
    BASE_URL = 'https://www.lacoste.co.th/'

    def product_retailer_sku(self, product_details):
        return product_details['sku']

    def product_gender(self, product_details):
        genders = ['Women', 'Men', 'Girl', 'Boy']
        gender = product_details.get('item_category3')
        return gender if gender in genders else 'Unisex'

    def product_category(self, product_details):
        return product_details['item_category']

    def product_name(self, product_details):
        return product_details['name']

    def product_images(self, product_details):
        relative_image_urls = [
            entry['file']
            for entry in product_details['variants'][0]['product']['media_gallery_entries']
        ]
        return [
            f'{self.BASE_URL}pub/media/catalog/product/{image_url}'
            for image_url in relative_image_urls
        ]

    def product_price(self, product_details):
        return product_details['price']['regularPrice']['amount']['value']

    def product_currency(self, product_details):
        return product_details['price']['regularPrice']['amount']['currency']

    def product_colour(self, product_details):
        config_options = product_details['configurable_options']
        return config_options[1]['values'][0]['label'] if len(config_options) > 1 else []

    def product_available_sizes(self, product_details):
        available_sizes = [
            variant['attributes'][0]['value_index'] for variant in product_details['variants']
        ]
        return [
            value['label']
            for option in product_details['configurable_options']
            for value in option['values']
            if value['value_index'] in available_sizes
        ]

    def product_sku_details(self, product_details):
        available_sizes_id = [
            variant['attributes'][0]['value_index'] for variant in product_details['variants']
        ]
        all_sizes_label = [
            value['label']
            for option in product_details['configurable_options']
            for value in option['values']
        ]
        available_sizes_label = [
            value['label']
            for option in product_details['configurable_options']
            for value in option['values']
            if value['value_index'] in available_sizes_id
        ]
        common_sku = {
            'price': self.product_price(product_details),
            'currency': self.product_currency(product_details),
            'color': self.product_colour(product_details),
        }
        return [
            {
                **common_sku,
                'size': size,
                'sku_id': f'{common_sku["color"]}_{size}',
                'out_of_stock': size not in available_sizes_label,
            }
            for size in all_sizes_label
        ]

    def product_description(self, product_details):
        if description := product_details['meta_description']:
            return description.split('.')
        return []

    def product_url(self, product_details, url_path):
        return f'{self.BASE_URL}en/{url_path}/{product_details["url_key"]}.html'

    def product_care(self, product_details):
        if care_instructions := product_details['care_instructions']:
            return [item.split(":")[1] for item in care_instructions.split(",")]
        return []

    def extract_json_from_response(self, raw_product_details_response):
        response_str = raw_product_details_response.decode('utf-8')
        product_parts = response_str.split('</html>')
        if len(product_parts) > 1:
            product_json_str = product_parts[1].strip()
        else:
            product_json_str = product_parts[0].strip()
        return json.loads(product_json_str)

    def parse(self, response):
        raw_product_details = self.extract_json_from_response(response.body)
        product_details = raw_product_details['data']['productDetail']['items']

        item = LacosteItem()
        item['url'] = self.product_url(*product_details, response.meta['url_path'])
        item['skus'] = self.product_sku_details(*product_details)
        item['name'] = self.product_name(*product_details)
        item['retailer_sku'] = self.product_retailer_sku(*product_details)
        item['category'] = self.product_category(*product_details)
        item['care'] = self.product_care(*product_details)
        item['brand'] = 'Lacoste'
        item['description'] = self.product_description(*product_details)
        item['image_url'] = self.product_images(*product_details)
        item['gender'] = self.product_gender(*product_details)

        yield item
