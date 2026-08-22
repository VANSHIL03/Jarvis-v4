import pytest
from automation.food_delivery import FoodDeliveryAutomation

def test_swiggy_search():
    food = FoodDeliveryAutomation()
    res = food.search_swiggy("Pav Bhaji")
    assert res["status"] == "success"
    assert res["platform"] == "Swiggy"
    assert "swiggy.com" in res["url"]

def test_zomato_search():
    food = FoodDeliveryAutomation()
    res = food.search_zomato("Biryani")
    assert res["status"] == "success"
    assert res["platform"] == "Zomato"
    assert "zomato.com" in res["url"]
