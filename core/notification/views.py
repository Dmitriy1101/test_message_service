from logging import Logger, getLogger

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import ValidationError as DRFValidationError
from rest_framework.views import APIView

from .serializers import MassNotificationCreateSerializer
from .tasks import notification_immediately

log: Logger = getLogger(__name__)


class NotificationView(APIView):
    """
    API endpoint для создания массовых рассылок уведомлений.

    Требует аутентификации по токену и предоставляет функциональность
    для создания рассылок с множеством получателей.

    Authentication:
        - TokenAuthentication

    Permissions:
        - IsAuthenticated

    Methods:
        post: Создание новой массовой рассылки уведомлений
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Создание новой массовой рассылки уведомлений.

        Принимает данные для создания рассылки, валидирует их через сериализатор
        и создает рассылку с указанными получателями.

        Request Body:
            - subject: string (required) - Тема уведомления
            - message: string (required) - Текст сообщения
            - user_id: array[integer] (required) - Список ID получателей
            - immediately: boolean (optional, default: false) - Немедленная отправка
            - priority_order: array[string] (optional, default: ["email", "telegram", "sms"]) - Порядок каналов
            - scheduled_for: string (optional) - Дата и время запланированной отправки (ISO format)

        Responses:
            - 204: Рассылка успешно создана
            - 400: Невалидные данные запроса
            - 401: Пользователь не аутентифицирован
            - 500: Внутренняя ошибка сервера

        Example Request:
            POST /api/notification/
            {
                "subject": "Важное обновление",
                "message": "Система будет обновлена завтра",
                "user_id": [1, 2, 3],
                "immediately": false,
                "priority_order": ["email", "telegram"]
            }
        """

        try:
            request_data: dict = request.data.copy()
            serializer = MassNotificationCreateSerializer(data=request_data)
            if serializer.is_valid():
                inst = serializer.save(created_by=request.user)
                log.info(
                    "User ID: %s create notification ID: %s",
                    request.user.id,
                    inst.id,
                )
                if inst.immediately:
                    notification_immediately.delay_on_commit(inst.id)
                return Response(status=status.HTTP_204_NO_CONTENT)
            log.debug(
                "User ID: %s invalid POST request data: %s",
                request.user.id,
                request_data,
            )
            print(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except (DjangoValidationError, DRFValidationError) as e:
            log.exception(
                "Validation error", extra={"error": e, "request_data": request_data}
            )
            return Response(
                {"error": "Validation error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            log.error(
                "Uncnoun error for user: %s, \n%s",
                request.user,
                {"error": e, "request_data": request_data},
            )
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
