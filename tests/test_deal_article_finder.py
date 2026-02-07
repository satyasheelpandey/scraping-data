"""
Test suite for deal_article_finder.py

Following TDD principles - tests for enhanced Google search with URL ranking.
Based on ranking logic from news_deals_pipeline/app/structured_imports/article_expander.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict


class TestURLScoring:
    """Tests for URL relevance scoring logic."""

    def test_baseline_score(self):
        """Test that URLs start with baseline score of 50."""
        from deal_article_finder import score_url_for_deal_relevance

        url = "https://example.com/some-page"
        score = score_url_for_deal_relevance(url)

        # Should be around baseline (50) with minor adjustments
        assert 40 <= score <= 60

    def test_high_value_domain_bonus(self):
        """Test +30 bonus for high-value domains."""
        from deal_article_finder import score_url_for_deal_relevance

        high_value_urls = [
            "https://www.reuters.com/article/deal",
            "https://bloomberg.com/news/merger",
            "https://www.businesswire.com/press-release",
            "https://prnewswire.com/news-releases/acquisition",
            "https://www.wsj.com/articles/buyout",
            "https://ft.com/content/takeover",
        ]

        for url in high_value_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) + High-value domain (30) = 80 minimum
            assert score >= 80, f"URL {url} should have high-value bonus"

    def test_low_value_domain_penalty(self):
        """Test -40 penalty for low-value domains."""
        from deal_article_finder import score_url_for_deal_relevance

        low_value_urls = [
            "https://www.linkedin.com/company/acme",
            "https://facebook.com/acmecorp",
            "https://twitter.com/acme",
            "https://www.wikipedia.org/wiki/Acme",
            "https://youtube.com/watch?v=123",
        ]

        for url in low_value_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) - Low-value domain (40) = 10, but deep paths add +5
            # So maximum is 15 for URLs with deep paths
            assert score <= 20, f"URL {url} should have low-value penalty"

    def test_deal_keyword_bonus(self):
        """Test +20 bonus for deal keywords in path."""
        from deal_article_finder import score_url_for_deal_relevance

        keyword_urls = [
            "https://example.com/news/acquisition-announced",
            "https://example.com/press/merger-completed",
            "https://example.com/2024/deal-closes",
            "https://example.com/articles/takeover-bid",
            "https://example.com/buyout-transaction",
            "https://example.com/press-release/divestiture",
        ]

        for url in keyword_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) + Deal keyword (20) = 70 minimum
            assert score >= 70, f"URL {url} should have deal keyword bonus"

    def test_news_path_bonus(self):
        """Test +10 bonus for news-style paths."""
        from deal_article_finder import score_url_for_deal_relevance

        news_urls = [
            "https://example.com/news/story-123",
            "https://example.com/press/release-456",
            "https://example.com/media/article-789",
            "https://example.com/article/company-news",
            "https://example.com/stories/business-update",
        ]

        for url in news_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) + News path (10) + Deep path (5) = 65 minimum
            assert score >= 65, f"URL {url} should have news path bonus"

    def test_deep_path_bonus(self):
        """Test +5 bonus for deep paths (2+ segments)."""
        from deal_article_finder import score_url_for_deal_relevance

        url_shallow = "https://example.com/news"
        url_deep = "https://example.com/news/2024/company-acquires-target"

        score_shallow = score_url_for_deal_relevance(url_shallow)
        score_deep = score_url_for_deal_relevance(url_deep)

        # Deep URL should score higher
        assert score_deep > score_shallow

    def test_homepage_penalty(self):
        """Test -30 penalty for bare homepages."""
        from deal_article_finder import score_url_for_deal_relevance

        homepage_urls = [
            "https://example.com/",
            "https://example.com",
            "https://example.com/index.html",
            "https://example.com/index.htm",
        ]

        for url in homepage_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) - Homepage penalty (30) = 20 maximum
            assert score <= 20, f"URL {url} should have homepage penalty"

    def test_non_article_path_penalty(self):
        """Test -20 penalty for non-article paths."""
        from deal_article_finder import score_url_for_deal_relevance

        # Use URLs without deal keywords to isolate the penalty
        non_article_urls = [
            "https://example.com/category/business",
            "https://example.com/tag/technology",  # Changed from "mergers"
            "https://example.com/search?q=companies",  # Changed from "deals"
            "https://example.com/profile/john-doe",
        ]

        for url in non_article_urls:
            score = score_url_for_deal_relevance(url)
            # Base (50) - Non-article penalty (20) + Deep path (5) = 35 maximum
            assert score <= 40, f"URL {url} should have non-article penalty"

    def test_non_article_extension_penalty(self):
        """Test -15 penalty for non-article file extensions."""
        from deal_article_finder import score_url_for_deal_relevance

        file_urls = [
            "https://example.com/report.pdf",
            "https://example.com/image.jpg",
            "https://example.com/data.csv",
            "https://example.com/archive.zip",
        ]

        for url in file_urls:
            score = score_url_for_deal_relevance(url)
            # Should be penalized
            assert score < 50, f"URL {url} should have file extension penalty"

    def test_combined_scoring(self):
        """Test realistic combined scoring scenarios."""
        from deal_article_finder import score_url_for_deal_relevance

        # Perfect article: high-value domain + deal keyword + news path
        perfect_url = "https://www.reuters.com/article/acquisition-completed"
        perfect_score = score_url_for_deal_relevance(perfect_url)
        # Base (50) + High-value (30) + Deal keyword (20) + News path (10) + Deep (5) = 115
        assert perfect_score >= 100

        # Poor article: low-value domain + no keywords
        poor_url = "https://linkedin.com/company/acme"
        poor_score = score_url_for_deal_relevance(poor_url)
        # Base (50) - Low-value (40) = 10
        assert poor_score <= 20


class TestGoogleSearch:
    """Tests for Google Search API integration."""

    def test_google_search_query_format(self):
        """Test that Google search uses correct query format."""
        from deal_article_finder import search_google_for_articles

        with patch('deal_article_finder.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"items": []}
            mock_get.return_value = mock_response

            search_google_for_articles("Acme Corp", "Vista Equity")

            # Verify query parameter
            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get('url')
            params = call_args.kwargs.get('params', {})

            assert "Acme Corp" in params.get('q', '')
            assert "Vista Equity" in params.get('q', '')

    def test_google_search_returns_10_results(self):
        """Test that we request 10 results from Google."""
        from deal_article_finder import search_google_for_articles

        with patch('deal_article_finder.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "items": [{"link": f"https://example.com/article-{i}"} for i in range(10)]
            }
            mock_get.return_value = mock_response

            results = search_google_for_articles("Acme Corp", "Vista Equity")

            # Should get 10 results
            assert len(results) == 10

    def test_google_search_handles_errors(self):
        """Test error handling for Google API failures."""
        from deal_article_finder import search_google_for_articles

        with patch('deal_article_finder.requests.get') as mock_get:
            # Simulate API error
            mock_get.side_effect = Exception("API timeout")

            results = search_google_for_articles("Acme Corp", "Vista Equity")

            # Should return empty list on error
            assert results == []

    def test_google_search_handles_no_results(self):
        """Test handling when Google returns no results."""
        from deal_article_finder import search_google_for_articles

        with patch('deal_article_finder.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # No 'items' key
            mock_get.return_value = mock_response

            results = search_google_for_articles("Acme Corp", "Vista Equity")

            # Should return empty list
            assert results == []


class TestArticleRanking:
    """Tests for article ranking and selection."""

    def test_returns_top_3_articles(self):
        """Test that exactly 3 top articles are returned."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            # Return 10 URLs with varying quality
            mock_search.return_value = [
                f"https://reuters.com/article-{i}" for i in range(5)
            ] + [
                f"https://linkedin.com/company-{i}" for i in range(5)
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # Should return exactly 3 articles
            assert len(result['articles']) == 3

    def test_articles_sorted_by_score(self):
        """Test that articles are sorted by score (descending)."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            # Mix of high and low value URLs
            mock_search.return_value = [
                "https://linkedin.com/company/acme",  # Low score
                "https://reuters.com/article/acquisition",  # High score
                "https://example.com/news/deal",  # Medium score
                "https://bloomberg.com/news/merger",  # High score
                "https://facebook.com/acme",  # Low score
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # First article should have higher score than second
            assert result['articles'][0]['score'] >= result['articles'][1]['score']
            assert result['articles'][1]['score'] >= result['articles'][2]['score']

    def test_returns_company_info(self):
        """Test that result includes company and investor names."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            mock_search.return_value = [
                "https://reuters.com/article-1"
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            assert result['company_name'] == "Acme Corp"
            assert result['investor_name'] == "Vista Equity"


class TestCompanyWebsiteDiscovery:
    """Tests for discovering company website."""

    def test_discovers_company_website(self):
        """Test that company website is discovered from Google results."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            # Include company domain in results
            mock_search.return_value = [
                "https://acmecorp.com",  # Official website
                "https://reuters.com/article/acme-deal",
                "https://bloomberg.com/news/acme-acquisition",
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # Should identify official website
            assert result['company_website'] is not None
            assert 'acmecorp.com' in result['company_website']

    def test_excludes_company_website_from_articles(self):
        """Test that company website is not included in article list."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            mock_search.return_value = [
                "https://acmecorp.com",  # Official website
                "https://reuters.com/article/acme-deal",
                "https://bloomberg.com/news/acme-acquisition",
                "https://businesswire.com/press-release/acme",
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # Articles should not include the company website
            article_urls = [a['url'] for a in result['articles']]
            assert not any('acmecorp.com' in url for url in article_urls)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_company_name(self):
        """Test handling of empty company name."""
        from deal_article_finder import find_deal_articles

        result = find_deal_articles("", "Vista Equity")

        # Should return empty result
        assert result['articles'] == []

    def test_handles_empty_investor_name(self):
        """Test handling of empty investor name."""
        from deal_article_finder import find_deal_articles

        result = find_deal_articles("Acme Corp", "")

        # Should still work with just company name
        assert result['company_name'] == "Acme Corp"

    def test_handles_special_characters(self):
        """Test handling of special characters in names."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            mock_search.return_value = [
                "https://reuters.com/article-1"
            ]

            # Should not crash with special characters
            result = find_deal_articles("Acme & Co.", "Vista Equity (PE)")
            assert result is not None

    def test_handles_duplicate_urls(self):
        """Test that duplicate URLs are handled properly."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.search_google_for_articles') as mock_search:
            # Return duplicates
            mock_search.return_value = [
                "https://reuters.com/article-1",
                "https://reuters.com/article-1",  # Duplicate
                "https://bloomberg.com/news-1",
                "https://bloomberg.com/news-1",  # Duplicate
            ]

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # Should deduplicate
            article_urls = [a['url'] for a in result['articles']]
            assert len(article_urls) == len(set(article_urls))


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow(self):
        """Test complete workflow from search to ranked results."""
        from deal_article_finder import find_deal_articles

        with patch('deal_article_finder.requests.get') as mock_get:
            # Mock Google API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "items": [
                    {"link": "https://acmecorp.com"},
                    {"link": "https://reuters.com/article/acme-acquisition"},
                    {"link": "https://bloomberg.com/news/acme-merger"},
                    {"link": "https://businesswire.com/press/acme-deal"},
                    {"link": "https://linkedin.com/company/acme"},
                    {"link": "https://example.com/news/acme-buyout"},
                    {"link": "https://ft.com/content/acme-takeover"},
                    {"link": "https://wsj.com/articles/acme-transaction"},
                    {"link": "https://twitter.com/acme"},
                    {"link": "https://facebook.com/acme"},
                ]
            }
            mock_get.return_value = mock_response

            result = find_deal_articles("Acme Corp", "Vista Equity")

            # Verify structure
            assert 'company_name' in result
            assert 'investor_name' in result
            assert 'company_website' in result
            assert 'articles' in result

            # Should have 3 articles
            assert len(result['articles']) == 3

            # Each article should have url and score
            for article in result['articles']:
                assert 'url' in article
                assert 'score' in article
                assert isinstance(article['score'], int)

            # High-value domains should be ranked higher
            article_urls = [a['url'] for a in result['articles']]
            high_value_count = sum(
                1 for url in article_urls
                if any(domain in url for domain in ['reuters', 'bloomberg', 'businesswire', 'ft', 'wsj'])
            )
            assert high_value_count >= 2  # At least 2 out of 3 should be high-value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
