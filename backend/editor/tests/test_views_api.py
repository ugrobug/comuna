from django.test import SimpleTestCase
from django.urls import resolve

from editor import views as editor_views


class EditorViewsRoutingTests(SimpleTestCase):
    def test_editor_routes_resolve_to_editor_app(self):
        self.assertIs(resolve("/api/auth/post-templates/movie-review/autofill/").func, editor_views.auth_movie_review_autofill)
        self.assertIs(resolve("/api/auth/posts/").func, editor_views.user_posts)
        self.assertIs(resolve("/api/auth/posts/1/").func, editor_views.user_post_update)
        self.assertIs(resolve("/api/auth/drafts/shared/token/").func, editor_views.shared_draft_detail)
        self.assertIs(resolve("/api/auth/uploads/").func, editor_views.user_upload)
        self.assertIs(resolve("/api/posts/1/poll-vote/").func, editor_views.post_poll_vote)
        self.assertIs(resolve("/api/posts/1/rating-vote/").func, editor_views.post_rating_vote)
        self.assertIs(
            resolve("/api/posts/1/bug-report-confirmation/").func,
            editor_views.bug_report_confirmation_update,
        )
