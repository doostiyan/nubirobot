import os
from datetime import timedelta
from uuid import uuid4

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.crm.models import News, NewsTag


class NewsTest(TestCase):
    NEWS_URL = '/crm/news/list'

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        cache.delete(News.CACHE_KEY)

    @staticmethod
    def add_tags(news: News, *names: str) -> None:
        for name in names:
            tag = NewsTag.get_tag(name)
            news.tags.add(tag)

    @staticmethod
    def add_image(news, image):
        news.image_name = uuid4()
        with open(news.image_disk_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)
        news.save()

    def test_news_list(self):
        news1 = News.objects.create(title='news1', context='context1')
        self.add_tags(news1, 'tag1', 'tag 2')
        news2 = News.objects.create(title='news2', context='context2', link='link', image='https://image')
        self.add_tags(news2, 'tag1', 'تگ فارسی')

        old_news = News.objects.create(
            title='old', context='old', publish_at=timezone.now() - timedelta(days=90, minutes=1),
        )
        disable_news = News.objects.create(
            title='disable_news', context='context', publish_at=timezone.now(), is_disabled=True,
        )
        unpublished_news = News.objects.create(
            title='future_news', context='context', publish_at=timezone.now() + timedelta(minutes=1),
        )

        response = self.client.get(self.NEWS_URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 2
        response_news_ids = {n['id'] for n in news}
        assert response_news_ids == {news1.id, news2.id}

        assert 'id' in news[0]
        assert 'title' in news[0]
        assert 'context' in news[0]
        assert 'createdAt' in news[0]
        assert 'link' in news[0]
        assert 'image' in news[0]
        assert 'publishAt' in news[0]
        assert 'tags' in news[0]

        assert news[0]['id'] is not None
        assert news[0]['title'] == 'news2'
        assert news[0]['subtitle'] is None
        assert news[0]['context'] == 'context2'
        assert news[0]['createdAt'] is not None
        assert news[0]['link'] == 'link'
        assert news[0]['image'] == 'https://image'
        assert news[0]['publishAt'] is not None

        assert news[0]['tags'] == [
            dict(name='tag1', slug='tag1', color=None),
            dict(name='تگ فارسی', slug='تگ-فارسی', color=None),
        ]
        assert news[1]['tags'] == [
            dict(name='tag1', slug='tag1', color=None),
            dict(name='tag 2', slug='tag-2', color=None),
        ]

        bad_news_ids = set([disable_news.id, unpublished_news.id, old_news.id])
        assert response_news_ids.intersection(bad_news_ids) == set()

        response = self.client.get(self.NEWS_URL + '?page=2')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 0

    def test_news_list_filter_by_tag(self):
        news1 = News.objects.create(title='news1', context='context1', subtitle='test1')
        self.add_tags(news1, 'tag1', 'tag 2')
        news2 = News.objects.create(title='news2', context='context2')
        self.add_tags(news2, 'tag1')
        news3 = News.objects.create(title='news3', context='context3')
        self.add_tags(news3, 'تگ فارسی')

        response = self.client.get(self.NEWS_URL + '?tag=tag1')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 2
        assert news[0]['tags'] == [dict(name='tag1', slug='tag1', color=None)]
        assert news[1]['tags'] == [
            dict(name='tag1', slug='tag1', color=None),
            dict(name='tag 2', slug='tag-2', color=None),
        ]
        assert news[1]['subtitle'] == 'test1'
        assert news[0]['subtitle'] is None

        response = self.client.get(self.NEWS_URL + '?tag=tag-2')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 1
        assert news[0]['tags'] == [
            dict(name='tag1', slug='tag1', color=None),
            dict(name='tag 2', slug='tag-2', color=None),
        ]

        response = self.client.get(self.NEWS_URL + '?tag=تگ-فارسی')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 1
        assert news[0]['tags'] == [dict(name='تگ فارسی', slug='تگ-فارسی', color=None)]

        response = self.client.get(self.NEWS_URL + '?tag=tag4')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        news = response.json()['result']
        assert len(news) == 0

    def test_news_add_image(self):
        news = News.objects.create(title='news', context='content')
        file = SimpleUploadedFile('image.png', b'')
        self.add_image(news, file)

        assert news.image_name is not None
        assert news.image_relative_path is not None
        assert news.image_disk_path is not None
        assert news.image_serve_url is not None
        assert os.path.exists(news.image_disk_path)
        self.addCleanup(os.remove, news.image_disk_path)

    def test_news_list_pagination(self):
        News.objects.create(title='news1', context='context1')
        News.objects.create(title='news2', context='context2')

        response = self.client.get(self.NEWS_URL, dict(page=1, pageSize=1))
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['result']) == 1
        assert data['hasNext'] is True

        response = self.client.get(self.NEWS_URL, dict(page=100, pageSize=1))
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['result'] == []
        assert data['hasNext'] is False

    def test_news_list_caching(self):
        News.objects.create(title='news1', context='context1')
        response = self.client.get(self.NEWS_URL, dict(page=1, pageSize=20))
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['result']) == 1
        assert data['hasNext'] is False

        News.objects.create(title='news2', context='context2')
        response = self.client.get(self.NEWS_URL, dict(page=1, pageSize=20))
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['result']) == 1
        assert data['hasNext'] is False

        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user202token'
        response = self.client.get(self.NEWS_URL, dict(page=1, pageSize=19))
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['result']) == 1
        assert data['hasNext'] is False


class NewsTagsTest(TestCase):
    NEWS_TAGS_URL = '/crm/news/tags/list'

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def test_news_tags_list(self):
        NewsTag.objects.create(name='tag1')
        NewsTag.objects.create(name='tag2', color='#ffffff')

        response = self.client.get(self.NEWS_TAGS_URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        tags = response.json()['result']
        assert len(tags) == 2
        assert tags == [
            dict(name='tag1', slug='tag1', color=None),
            dict(name='tag2', slug='tag2', color="#ffffff"),
        ]

    def test_news_tags_list_unauthorized(self):
        del self.client.defaults['HTTP_AUTHORIZATION']
        response = self.client.get(self.NEWS_TAGS_URL)
        assert response.status_code == 401
