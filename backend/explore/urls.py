from django.urls import path
from . import views

app_name = "explore"
urlpatterns = [
    path("", views.GraphView.as_view(), name="graph"),
    path("manage/", views.ManageGraphView.as_view(), name="manage"),
    path("nodes/", views.NodeListView.as_view(), name="nodes"),
    path("nodes/<int:node_id>/", views.NodeDetailView.as_view(), name="node"),
    path("nodes/<int:node_id>/image/", views.NodeImageView.as_view(), name="node-image"),
    path("nodes/<int:node_id>/subscription/", views.SubscriptionView.as_view(), name="subscription"),
    path("edges/", views.EdgeListView.as_view(), name="edges"),
    path("edges/<int:edge_id>/", views.EdgeDetailView.as_view(), name="edge"),
]
