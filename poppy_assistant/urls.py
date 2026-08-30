from django.urls import path

from poppy_assistant import views

app_name = "poppy"

urlpatterns = [
    path("chat", views.chat_api, name="chat"),
    path("call", views.call_api, name="call"),
    path("voice/incoming", views.voice_incoming_api, name="voice_incoming"),
]
