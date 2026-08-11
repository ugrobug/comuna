import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from feeds.models import Author, Post, PostComment
from users.models import AuthorAdmin
from users.service import _issue_token


User = get_user_model()


class QuestionAnswerApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="question_owner", password="password")
        self.outsider = User.objects.create_user(username="question_outsider", password="password")
        self.answerer = User.objects.create_user(username="question_answerer", password="password")
        self.author = Author.objects.create(username="question_author", title="Question author")
        AuthorAdmin.objects.create(
            user=self.owner,
            author=self.author,
            verified_at=timezone.now(),
        )
        self.post = Post.objects.create(
            author=self.author,
            message_id=1001,
            title="How does this work?",
            content="Question body",
            raw_data={"template": {"type": "question", "version": 1, "data": {}}},
        )
        self.comment = PostComment.objects.create(
            post=self.post,
            user=self.answerer,
            body="This is the answer.",
        )

    def headers_for(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(user)}"}

    def test_owner_can_select_comment_as_correct_answer(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/question-answer/",
            data=json.dumps({"comment_id": self.comment.id}),
            content_type="application/json",
            **self.headers_for(self.owner),
        )

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.accepted_answer_id, self.comment.id)
        self.assertTrue(response.json()["question_answer"]["is_solved"])
        self.assertTrue(response.json()["comment"]["is_accepted_answer"])

        comments_response = self.client.get(f"/api/posts/{self.post.id}/comments/")
        comments_payload = comments_response.json()
        self.assertEqual(
            comments_payload["question_answer"]["accepted_comment_id"],
            self.comment.id,
        )
        self.assertTrue(comments_payload["comments"][0]["is_accepted_answer"])

    def test_non_author_cannot_select_correct_answer(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/question-answer/",
            data=json.dumps({"comment_id": self.comment.id}),
            content_type="application/json",
            **self.headers_for(self.outsider),
        )

        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertIsNone(self.post.accepted_answer_id)

    def test_comment_from_another_post_cannot_be_selected(self):
        other_post = Post.objects.create(
            author=self.author,
            message_id=1002,
            title="Another question",
            raw_data={"template": {"type": "question", "version": 1, "data": {}}},
        )
        other_comment = PostComment.objects.create(
            post=other_post,
            user=self.answerer,
            body="Wrong post answer",
        )

        response = self.client.post(
            f"/api/posts/{self.post.id}/question-answer/",
            data=json.dumps({"comment_id": other_comment.id}),
            content_type="application/json",
            **self.headers_for(self.owner),
        )

        self.assertEqual(response.status_code, 404)

    def test_deleting_accepted_comment_reopens_question(self):
        self.post.accepted_answer = self.comment
        self.post.question_solved_at = timezone.now()
        self.post.save(update_fields=["accepted_answer", "question_solved_at", "updated_at"])

        response = self.client.delete(
            f"/api/comments/{self.comment.id}/",
            **self.headers_for(self.answerer),
        )

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertIsNone(self.post.accepted_answer_id)
        self.assertIsNone(self.post.question_solved_at)
