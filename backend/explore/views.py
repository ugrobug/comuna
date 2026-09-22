import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from communities.models import Comun
from users.service import _get_user_from_request
from .models import Edge, Node
from .services import GraphEditor, GraphQuery, SubscriptionService
from .images import NodeImageService


@method_decorator(csrf_exempt, name="dispatch")
class ExploreView(View):
    staff_required = False
    login_required = False

    def dispatch(self, request, *args, **kwargs):
        self.user = _get_user_from_request(request)
        if (self.login_required or self.staff_required) and not self.user:
            return JsonResponse({"error": "Войдите или зарегистрируйтесь."}, status=401)
        if self.staff_required and not self.user.is_staff:
            return JsonResponse({"error": "Доступ только модераторам сайта."}, status=403)
        try:
            response = super().dispatch(request, *args, **kwargs)
        except ValidationError as error:
            response = JsonResponse({"error": " ".join(error.messages)}, status=400)
        response["Cache-Control"] = "private, no-store"
        return response

    def body(self):
        try:
            data = json.loads(self.request.body)
        except (ValueError, UnicodeDecodeError):
            raise ValidationError("Некорректный JSON.") from None
        if not isinstance(data, dict):
            raise ValidationError("Ожидается объект JSON.")
        return data


class GraphView(ExploreView):
    def get(self, request):
        return JsonResponse(GraphQuery().serialize(self.user))


class ManageGraphView(ExploreView):
    staff_required = True

    def get(self, request):
        data = GraphQuery(include_hidden=True).serialize(self.user)
        data["communities"] = list(Comun.objects.filter(is_active=True).order_by("name").values("id", "name", "slug"))
        return JsonResponse(data)


class NodeListView(ExploreView):
    staff_required = True

    def post(self, request):
        data = self.body()
        node = GraphEditor.apply(lambda: GraphEditor.save_node(data))
        return JsonResponse({"id": node.pk}, status=201)


class NodeDetailView(ExploreView):
    staff_required = True

    def patch(self, request, node_id):
        data = self.body()
        node = GraphEditor.apply(lambda: GraphEditor.save_node(data, node_id))
        return JsonResponse({"id": node.pk})

    def delete(self, request, node_id):
        GraphEditor.apply(lambda: get_object_or_404(Node, pk=node_id).delete())
        return JsonResponse({"ok": True})


class NodeImageView(ExploreView):
    staff_required = True

    def post(self, request, node_id):
        node = NodeImageService.replace(node_id, request.FILES.get("image"))
        return JsonResponse({"image_url": node.image.url})

    def delete(self, request, node_id):
        NodeImageService.remove(node_id)
        return JsonResponse({"image_url": None})


class EdgeListView(ExploreView):
    staff_required = True

    def post(self, request):
        data = self.body()
        edge = GraphEditor.apply(lambda: GraphEditor.add_edge(data))
        return JsonResponse({"id": edge.pk}, status=201)


class EdgeDetailView(ExploreView):
    staff_required = True

    def delete(self, request, edge_id):
        GraphEditor.apply(lambda: get_object_or_404(Edge, pk=edge_id).delete())
        return JsonResponse({"ok": True})


class SubscriptionView(ExploreView):
    login_required = True

    def post(self, request, node_id):
        return self.set_subscription(node_id, True)

    def delete(self, request, node_id):
        return self.set_subscription(node_id, False)

    def set_subscription(self, node_id, enabled):
        count = SubscriptionService.set(self.user, node_id, enabled)
        return JsonResponse({"subscribed": enabled, "subscribers_count": count})
