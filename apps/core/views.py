from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import redis
from django.conf import settings
from services.vector_store import get_vector_store_service


class HealthCheckView(APIView):
    """General health check returning healthy status and database connectivity."""
    permission_classes = [AllowAny]

    def get(self, request):
        health_status = {
            "status": "healthy",
            "database": "unknown",
        }
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status["database"] = "connected"
            return Response(health_status, status=status.HTTP_200_OK)
        except Exception as e:
            health_status["database"] = "unreachable"
            health_status["status"] = "unhealthy"
            return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class HealthLiveView(APIView):
    """Liveness probe: verifies the Django process is up and responding."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "live"}, status=status.HTTP_200_OK)


class HealthReadyView(APIView):
    """Readiness probe: verifies PostgreSQL, Redis, and Qdrant connectivity."""
    permission_classes = [AllowAny]

    def get(self, request):
        readiness = {
            "status": "ready",
            "database": "unknown",
            "redis": "unknown",
            "vector_store": "unknown",
        }
        all_ok = True

        # 1. Check Database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            readiness["database"] = "connected"
        except Exception:
            readiness["database"] = "unreachable"
            all_ok = False

        # 2. Check Redis
        try:
            r = redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2.0)
            r.ping()
            readiness["redis"] = "connected"
        except Exception:
            readiness["redis"] = "disconnected"

        # 3. Check Qdrant
        try:
            vs = get_vector_store_service()
            vs.client.get_collections()
            readiness["vector_store"] = "connected"
        except Exception:
            readiness["vector_store"] = "disconnected"

        status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        if not all_ok:
            readiness["status"] = "degraded"

        return Response(readiness, status=status_code)
