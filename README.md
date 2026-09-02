pip freeze > requirements.txt

python manage.py collectstatic

python manage.py collectstatic --noinput

from accounts.models import User

u = User.objects.create_user(
    username="adminA",
    password="@Hublab!1",
    first_name="Computing",
    last_name="Association",
    email="computing@gmail.com",
    role="ADMIN",
    is_staff=True,
    is_superuser=True,
    is_active=True,
    is_verified=True,
)