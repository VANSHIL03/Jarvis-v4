import pytest
from automation.shopping import ShoppingAutomation

def test_amazon_shopping():
    shop = ShoppingAutomation()
    res = shop.shop_on_amazon("wireless mouse")
    assert res["status"] == "success"
    assert res["platform"] == "Amazon"
    assert "amazon.in" in res["url"]

def test_flipkart_shopping():
    shop = ShoppingAutomation()
    res = shop.shop_on_flipkart("running shoes")
    assert res["status"] == "success"
    assert res["platform"] == "Flipkart"
    assert "flipkart.com" in res["url"]
