import factory
from django.contrib.auth.models import User
from users.models import UserContact


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")


class UserContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserContact

    user = factory.SubFactory(UserFactory)
    phone_number = factory.Sequence(lambda n: f"+79991234{n:03d}")
    telegram_profile = factory.Sequence(lambda n: f"https://t.me/user{n}")
