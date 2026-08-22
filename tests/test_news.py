import pytest
from automation.news_fetcher import NewsFetcher

def test_hindi_category_news():
    fetcher = NewsFetcher()
    res = fetcher.get_hinglish_news_bulletin("Sir Vanshil", category="gaming", lang="hi")
    assert isinstance(res, dict)
    assert "speech_reply" in res
    assert "headlines" in res

def test_government_news():
    fetcher = NewsFetcher()
    res = fetcher.get_hinglish_news_bulletin("Sir Vanshil", category="government", lang="hi")
    assert isinstance(res, dict)
    assert "speech_reply" in res
