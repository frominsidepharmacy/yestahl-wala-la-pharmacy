from .base import RetailerAdapter


class BinSinaAdapter(RetailerAdapter):
    key = "binsina"

    def product(self, url: str, category: str):
        product = super().product(url, category)
        if product.primary_image:
            product.primary_image = product.primary_image.replace("www.binsina.ae/en/pub/media/", "www.binsina.ae/media/")
        product.secondary_images = [x.replace("www.binsina.ae/en/pub/media/", "www.binsina.ae/media/") for x in product.secondary_images]
        return product
