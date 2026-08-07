from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike
from ratings.models import RatingSettings
from ratings.service import (
    calculate_author_rating,
    calculate_author_ratings,
    calculate_home_feed_post_metrics,
    calculate_post_total_rating,
    home_feed_community_day_key,
)


User = get_user_model()


class RatingServiceTests(TestCase):
    def setUp(self) -> None:
        self.settings = RatingSettings.objects.create(pk=1)

    def test_bulk_author_ratings_match_individual_calculation(self):
        alice = Author.objects.create(username="Alice")
        bob = Author.objects.create(username="Bob")
        alice_user = User.objects.create_user(username="aLiCe")
        bob_user = User.objects.create_user(username="bob")
        liker = User.objects.create_user(username="liker")

        alice_post = Post.objects.create(
            author=alice,
            message_id=1,
            rating=3,
            comments_count=1,
        )
        bob_post = Post.objects.create(
            author=bob,
            message_id=2,
            rating=-1,
            comments_count=2,
        )
        alice_comment = PostComment.objects.create(
            post=bob_post,
            user=alice_user,
            body="Alice comment",
        )
        bob_comment = PostComment.objects.create(
            post=alice_post,
            user=bob_user,
            body="Bob comment",
        )
        PostCommentLike.objects.create(comment=alice_comment, user=liker)
        PostCommentLike.objects.create(comment=bob_comment, user=liker)

        expected = {
            author.id: calculate_author_rating(author, settings=self.settings)
            for author in (alice, bob)
        }
        with CaptureQueriesContext(connection) as queries:
            actual = calculate_author_ratings((alice, bob), settings=self.settings)

        self.assertEqual(actual, expected)
        self.assertLessEqual(len(queries), 3)

    def test_bulk_home_feed_metrics_match_individual_calculation(self):
        author = Author.objects.create(username="community-author")
        comun = Comun.objects.create(
            name="Community",
            slug="community",
            telegram_source_author=author,
            rating_score=4,
        )
        post = Post.objects.create(
            author=author,
            message_id=3,
            rating=2,
            comments_count=1,
            raw_data={"comun_slug": comun.slug},
        )
        author_rating = calculate_author_rating(author, settings=self.settings)
        expected_score = calculate_post_total_rating(
            post,
            settings=self.settings,
            author_rating=author_rating,
        )
        expected_key = home_feed_community_day_key(post)

        with CaptureQueriesContext(connection) as queries:
            scores, community_day_keys = calculate_home_feed_post_metrics(
                [post],
                settings=self.settings,
                author_ratings={author.id: author_rating},
            )

        self.assertEqual(scores[post.id], expected_score)
        self.assertEqual(community_day_keys[post.id], expected_key)
        self.assertLessEqual(len(queries), 2)
