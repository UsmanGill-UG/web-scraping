import json
import time

from selenium.webdriver.common.by import By
from selenium import webdriver


class ProductScraper:
    def __init__(self, driver):
        self.driver = driver

    def _extract_by_css(self, css_selector):
        return self.driver.find_element(By.CSS_SELECTOR, css_selector).text

    def product_name(self):
        return self._extract_by_css("#productName > span")

    def product_description(self):
        return self._extract_by_css("#description")

    def product_retailer_id(self):
        return self._extract_by_css("#itemLabelDesktop > span")

    def product_colour(self):
        return self._extract_by_css(".basesize")

    def product_care(self):
        try:
            care_details_clickable = self.driver.find_element(By.CSS_SELECTOR, ".fnc")
            self.driver.execute_script("arguments[0].scrollIntoView();", care_details_clickable)
            care_details_clickable.click()
            return self._extract_by_css(".fnc .content")
        except:
            return None

    def product_price(self):
        return float(self._extract_by_css('span[itemprop="price"]'))

    def product_currency(self):
        currency_span = self.driver.find_element(By.CSS_SELECTOR, 'span[itemprop="priceCurrency"]')
        return currency_span.get_attribute('content')

    def product_image_url(self):
        return {
            self.product_colour(): [
                element.get_attribute("href") for element in self.driver.find_elements(By.CSS_SELECTOR, ".alt_dtl")
            ]
        }

    def product_category(self):
        return [element.text for element in self.driver.find_elements(By.CSS_SELECTOR, ".pagingBreadCrumb a")]

    def product_skus(self):
        size_div = self.driver.find_elements(By.CSS_SELECTOR, '.box.size')
        sizes = ['One Size']
        stocks = ['avail']

        if size_div:
            sizes = [a.text for a in size_div]
            stocks = [a.get_attribute('class') for a in size_div]

        common_sku = {
            'price': self.product_price(),
            'currency': self.product_currency(),
            'colour': self.product_colour()
        }

        skus = []
        for size, stock in zip(sizes, stocks):
            sku = {
                'size': size,
                'out_of_stock': stock == 'notavail',
                'sku_id': f"{common_sku['colour']}_{size}"
            }
            sku.update(common_sku)
            skus.append(sku)

        return skus

    def scrape(self, product_type):
        return {
            'retailer_sku': self.product_retailer_id(),
            'gender': '' if product_type == 'home-wellness' else 'women',
            'category': self.product_category(),
            'brand': 'Soft Surroundings',
            'url': self.driver.current_url,
            'name': self.product_name(),
            'description': self.product_description(),
            'care': self.product_care(),
            'image_urls': self.product_image_url(),
            'skus': self.product_skus(),
        }


class Crawler:
    def __init__(self, driver):
        self.driver = driver

    def close_dialog(self):
        try:
            close_dialog_button = self.driver.find_element(By.CLASS_NAME, 'ltkpopup-close')
            close_dialog_button.click()
        except:
            pass

    def get_product_details(self, product_type):
        products_links = [
            element.get_attribute("href") for element in self.driver.find_elements(By.CSS_SELECTOR, "a.viewProduct")
        ]
        products_details = []

        for link in products_links:
            driver.get(link)
            scraper = ProductScraper(driver)
            product_info = scraper.scrape(product_type)
            products_details.append(product_info)

        return products_details

    def scroll_down(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def get_category_links(self):
        categories = self.driver.find_elements(By.CSS_SELECTOR, "#menubar li.clMn.dropdown > a")
        return [a.get_attribute("href") for a in categories]

    def crawl(self):
        self.close_dialog()
        category_links = self.get_category_links()
        scraped_data = {}

        for link in category_links:
            driver.get(link)
            product_type = 'home-wellness' if 'home-wellness' in link else ''
            self.scroll_down()
            scraped_data |= self.get_product_details(product_type)

        with open("output.json", 'a') as json_file:
            json.dump(scraped_data, json_file, indent=4)


if __name__ == "__main__":
    HOME_PAGE_URL = 'https://www.softsurroundings.com/'
    driver = webdriver.Chrome()
    driver.implicitly_wait(30)
    driver.get(HOME_PAGE_URL)
    crawler = Crawler(driver)
    crawler.crawl()
    driver.quit()
