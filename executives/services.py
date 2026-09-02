# executives/services.py

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User

from .models import Executive


class ExecutiveService:
    """
    Service layer for KUCSA executive management.

    Responsibilities
    ----------------
    This service handles:

        - Executive profile creation
        - Executive profile updates
        - Executive retrieval
        - Executive filtering/searching
        - Executive board management
        - Executive role assignment/removal
        - Executive activation/deactivation
        - Executive term management
        - Executive statistics

    Architecture
    ------------
    The accounts.User model remains the source of truth for:

        - Authentication
        - User identity
        - Account status
        - Executive role

    The Executive model remains responsible for:

        - Committee
        - Office location
        - Responsibilities
        - Biography
        - Vision
        - Term information
        - Executive profile activation

    The service layer keeps these responsibilities separate.
    """

    # =========================================================
    # EXECUTIVE ROLES
    # =========================================================

    EXECUTIVE_ROLES = (
        User.Role.CHAIRPERSON,
        User.Role.VICE_CHAIRPERSON,
        User.Role.SECRETARY,
        User.Role.SECRETARY_GENERAL,
        User.Role.TREASURER,
        User.Role.ORGANIZING_SECRETARY,
        User.Role.PUBLICITY_SECRETARY,
    )

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================

    @staticmethod
    def _today():
        """
        Return today's local date.

        Kept in one place so all term-status calculations
        use the same date source.
        """

        return timezone.localdate()

    @staticmethod
    def _is_executive_role(role):
        """
        Return True when the supplied role is an official
        KUCSA executive role.
        """

        return role in ExecutiveService.EXECUTIVE_ROLES

    @staticmethod
    def _executive_queryset():
        """
        Return Executive profiles belonging to users who
        currently hold official KUCSA executive roles.

        User information is loaded together with the profile
        to avoid unnecessary database queries.
        """

        return (
            Executive.objects
            .select_related("user")
            .filter(
                user__role__in=ExecutiveService.EXECUTIVE_ROLES
            )
        )

    @staticmethod
    def _profile_queryset():
        """
        Return all Executive profiles regardless of the
        user's current role.

        This is useful for administrative operations where
        historical/deactivated profiles may still need to
        be accessed.
        """

        return (
            Executive.objects
            .select_related("user")
        )

    # =========================================================
    # CREATE EXECUTIVE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def create_executive(user, **data):
        """
        Create or update an Executive profile for a user
        who already holds an official executive role.

        Returns
        -------
        Executive
            The executive profile.
        """

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        if not getattr(user, "is_authenticated", True):
            raise ValueError(
                "An authenticated user is required."
            )

        if not ExecutiveService.is_executive(user):
            raise ValueError(
                "The selected user does not have "
                "an official KUCSA executive role."
            )

        protected_fields = {
            "id",
            "user",
            "created_at",
            "updated_at",
            "is_active",
        }

        allowed_data = {
            field: value
            for field, value in data.items()
            if field not in protected_fields
            and hasattr(Executive, field)
        }

        executive, created = (
            Executive.objects.get_or_create(
                user=user,
                defaults=allowed_data,
            )
        )

        if not created and allowed_data:

            for field, value in allowed_data.items():
                setattr(
                    executive,
                    field,
                    value,
                )

            executive.save()

        return executive

    # =========================================================
    # UPDATE EXECUTIVE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_executive(executive, **data):
        """
        Update an existing executive profile.

        User account information and executive role are not
        modified here. Those remain under the User model
        and executive assignment workflow.
        """

        if not executive:
            raise ValueError(
                "A valid executive profile is required."
            )

        protected_fields = {
            "id",
            "user",
            "created_at",
            "updated_at",
        }

        model_fields = {
            field.name
            for field in Executive._meta.fields
        }

        for field, value in data.items():

            if field in protected_fields:
                continue

            if field not in model_fields:
                continue

            setattr(
                executive,
                field,
                value,
            )

        executive.full_clean()
        executive.save()

        return executive

    # =========================================================
    # GET EXECUTIVE BY USER
    # =========================================================

    @staticmethod
    def get_executive(user):
        """
        Retrieve the executive profile belonging to a user
        who currently holds an official executive role.

        Returns None when no current executive profile exists.
        """

        if not user:
            return None

        return (
            ExecutiveService
            ._executive_queryset()
            .filter(user=user)
            .first()
        )

    # =========================================================
    # GET ANY EXECUTIVE PROFILE BY USER
    # =========================================================

    @staticmethod
    def get_profile_by_user(user):
        """
        Retrieve an Executive profile regardless of whether
        the user still holds an executive role.

        Useful for administrative/history operations.
        """

        if not user:
            return None

        return (
            ExecutiveService
            ._profile_queryset()
            .filter(user=user)
            .first()
        )

    # =========================================================
    # GET EXECUTIVE BY ID
    # =========================================================

    @staticmethod
    def get_executive_by_id(executive_id):
        """
        Retrieve a current executive profile by primary key.
        """

        if not executive_id:
            return None

        return (
            ExecutiveService
            ._executive_queryset()
            .filter(pk=executive_id)
            .first()
        )

    # =========================================================
    # GET ANY PROFILE BY ID
    # =========================================================

    @staticmethod
    def get_profile_by_id(executive_id):
        """
        Retrieve an Executive profile by primary key,
        regardless of current User role.
        """

        if not executive_id:
            return None

        return (
            ExecutiveService
            ._profile_queryset()
            .filter(pk=executive_id)
            .first()
        )

    # =========================================================
    # GET EXECUTIVE BY REGISTRATION NUMBER
    # =========================================================

    @staticmethod
    def get_executive_by_registration_number(
        registration_number,
    ):
        """
        Retrieve a current executive using the university
        registration number.
        """

        if not registration_number:
            return None

        return (
            ExecutiveService
            ._executive_queryset()
            .filter(
                user__registration_number=registration_number
            )
            .first()
        )

    # =========================================================
    # GET ALL CURRENT EXECUTIVES
    # =========================================================

    @staticmethod
    def get_all_executives():
        """
        Return all users currently holding official
        KUCSA executive roles.
        """

        return (
            ExecutiveService
            ._executive_queryset()
        )

    # =========================================================
    # GET ACTIVE CURRENT EXECUTIVES
    # =========================================================

    @staticmethod
    def get_active_executives():
        """
        Return executives who are:

            1. Official KUCSA executives
            2. Administratively active
            3. Currently serving according to their term
        """

        today = ExecutiveService._today()

        queryset = (
            ExecutiveService
            ._executive_queryset()
            .filter(is_active=True)
        )

        queryset = queryset.filter(
            Q(term_start__isnull=True)
            | Q(term_start__lte=today)
        )

        queryset = queryset.filter(
            Q(term_end__isnull=True)
            | Q(term_end__gte=today)
        )

        return queryset

    # =========================================================
    # GET INACTIVE EXECUTIVES
    # =========================================================

    @staticmethod
    def get_inactive_executives():
        """
        Return executive profiles that are administratively
        inactive.
        """

        return (
            ExecutiveService
            ._executive_queryset()
            .filter(is_active=False)
        )

    # =========================================================
    # GET UPCOMING EXECUTIVES
    # =========================================================

    @staticmethod
    def get_upcoming_executives():
        """
        Return active executives whose leadership term has
        not yet started.
        """

        today = ExecutiveService._today()

        return (
            ExecutiveService
            ._executive_queryset()
            .filter(
                is_active=True,
                term_start__gt=today,
            )
            .order_by(
                "term_start",
                "user__first_name",
                "user__last_name",
            )
        )

    # =========================================================
    # GET ENDED EXECUTIVE TERMS
    # =========================================================

    @staticmethod
    def get_ended_executives():
        """
        Return executive profiles whose term has ended.

        This is useful for historical/administrative views.
        """

        today = ExecutiveService._today()

        return (
            ExecutiveService
            ._profile_queryset()
            .filter(
                term_end__lt=today,
            )
            .order_by(
                "-term_end",
                "user__first_name",
                "user__last_name",
            )
        )

    # =========================================================
    # GET EXECUTIVES BY ROLE
    # =========================================================

    @staticmethod
    def get_executives_by_role(role):
        """
        Return currently serving active executives holding
        the specified official role.
        """

        if not ExecutiveService._is_executive_role(role):
            return Executive.objects.none()

        return (
            ExecutiveService
            .get_active_executives()
            .filter(
                user__role=role,
            )
        )

    # =========================================================
    # GET EXECUTIVES BY COMMITTEE
    # =========================================================

    @staticmethod
    def get_executives_by_committee(committee):
        """
        Return currently serving active executives belonging
        to the specified committee.
        """

        valid_committees = {
            choice[0]
            for choice in Executive.Committee.choices
        }

        if committee not in valid_committees:
            return Executive.objects.none()

        return (
            ExecutiveService
            .get_active_executives()
            .filter(
                committee=committee,
            )
        )

    # =========================================================
    # GET CHAIRPERSON
    # =========================================================

    @staticmethod
    def get_chairperson():
        """
        Return the current serving KUCSA Chairperson.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.CHAIRPERSON
            )
            .first()
        )

    # =========================================================
    # GET VICE CHAIRPERSON
    # =========================================================

    @staticmethod
    def get_vice_chairperson():
        """
        Return the current serving KUCSA Vice Chairperson.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.VICE_CHAIRPERSON
            )
            .first()
        )

    # =========================================================
    # GET SECRETARY
    # =========================================================

    @staticmethod
    def get_secretary():
        """
        Return the current serving KUCSA Secretary.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.SECRETARY
            )
            .first()
        )

    # =========================================================
    # GET SECRETARY GENERAL
    # =========================================================

    @staticmethod
    def get_secretary_general():
        """
        Return the current serving KUCSA Secretary General.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.SECRETARY_GENERAL
            )
            .first()
        )

    # =========================================================
    # GET TREASURER
    # =========================================================

    @staticmethod
    def get_treasurer():
        """
        Return the current serving KUCSA Treasurer.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.TREASURER
            )
            .first()
        )

    # =========================================================
    # GET ORGANIZING SECRETARY
    # =========================================================

    @staticmethod
    def get_organizing_secretary():
        """
        Return the current serving KUCSA Organizing Secretary.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.ORGANIZING_SECRETARY
            )
            .first()
        )

    # =========================================================
    # GET PUBLICITY SECRETARY
    # =========================================================

    @staticmethod
    def get_publicity_secretary():
        """
        Return the current serving KUCSA Publicity Secretary.
        """

        return (
            ExecutiveService
            .get_executives_by_role(
                User.Role.PUBLICITY_SECRETARY
            )
            .first()
        )

    # =========================================================
    # GET EXECUTIVE BOARD
    # =========================================================

    @staticmethod
    def get_executive_board():
        """
        Return the current KUCSA executive board.

        The board contains only executives who are currently
        serving according to both their administrative status
        and leadership term.
        """

        role_order = {
            User.Role.CHAIRPERSON: 1,
            User.Role.VICE_CHAIRPERSON: 2,
            User.Role.SECRETARY_GENERAL: 3,
            User.Role.SECRETARY: 4,
            User.Role.TREASURER: 5,
            User.Role.ORGANIZING_SECRETARY: 6,
            User.Role.PUBLICITY_SECRETARY: 7,
        }

        executives = list(
            ExecutiveService
            .get_active_executives()
        )

        executives.sort(
            key=lambda executive: (
                role_order.get(
                    executive.role_code,
                    99,
                ),
                executive.full_name.lower(),
            )
        )

        return executives

    # =========================================================
    # SEARCH EXECUTIVES
    # =========================================================

    @staticmethod
    def search_executives(query):
        """
        Search current KUCSA executives by:

            - First name
            - Last name
            - Username
            - Registration number
            - Email
            - Executive role
            - Committee
            - Office location
            - Biography
            - Responsibilities
        """

        queryset = (
            ExecutiveService
            ._executive_queryset()
        )

        query = (query or "").strip()

        if not query:
            return queryset

        return (
            queryset
            .filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(
                    user__registration_number__icontains=query
                )
                | Q(user__email__icontains=query)
                | Q(user__role__icontains=query)
                | Q(committee__icontains=query)
                | Q(office_location__icontains=query)
                | Q(responsibilities__icontains=query)
                | Q(vision__icontains=query)
                | Q(biography__icontains=query)
            )
            .distinct()
        )

    # =========================================================
    # FILTER EXECUTIVES
    # =========================================================

    @staticmethod
    def filter_executives(
        query=None,
        role=None,
        committee=None,
        is_active=None,
        is_verified=None,
    ):
        """
        Apply multiple executive management filters.
        """

        queryset = (
            ExecutiveService
            ._executive_queryset()
        )

        query = (query or "").strip()

        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(
                    user__registration_number__icontains=query
                )
                | Q(user__email__icontains=query)
                | Q(user__role__icontains=query)
                | Q(committee__icontains=query)
                | Q(office_location__icontains=query)
            )

        if role and ExecutiveService._is_executive_role(role):
            queryset = queryset.filter(
                user__role=role
            )

        if committee:
            queryset = queryset.filter(
                committee=committee
            )

        if is_active is not None:
            queryset = queryset.filter(
                is_active=is_active
            )

        if is_verified is not None:
            queryset = queryset.filter(
                user__is_verified=is_verified
            )

        return queryset.distinct()

    # =========================================================
    # ACTIVATE EXECUTIVE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def activate_executive(executive):
        """
        Activate an executive profile.

        The user must still hold an official executive role.
        """

        if not executive:
            raise ValueError(
                "A valid executive profile is required."
            )

        if not ExecutiveService.is_executive(
            executive.user
        ):
            raise ValueError(
                "This user does not currently hold "
                "an official KUCSA executive role."
            )

        executive.is_active = True

        executive.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        return executive

    # =========================================================
    # DEACTIVATE EXECUTIVE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def deactivate_executive(executive):
        """
        Deactivate an executive profile.

        This does not remove the User's executive role.
        """

        if not executive:
            raise ValueError(
                "A valid executive profile is required."
            )

        executive.is_active = False

        executive.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        return executive

    # =========================================================
    # ASSIGN EXECUTIVE ROLE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def assign_role(user, role):
        """
        Assign an official KUCSA executive role to a user.

        A corresponding Executive profile is automatically
        created when necessary.

        If an old Executive profile exists, it is reactivated.
        """

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        if not ExecutiveService._is_executive_role(role):
            raise ValueError(
                "Invalid KUCSA executive role."
            )

        if not getattr(user, "is_active", True):
            raise ValueError(
                "The selected user account is inactive."
            )

        # -----------------------------------------------------
        # ASSIGN USER ROLE
        # -----------------------------------------------------

        user.role = role

        update_fields = ["role"]

        if hasattr(user, "updated_at"):
            update_fields.append("updated_at")

        user.save(
            update_fields=update_fields
        )

        # -----------------------------------------------------
        # ENSURE EXECUTIVE PROFILE
        # -----------------------------------------------------

        executive, created = (
            Executive.objects.get_or_create(
                user=user
            )
        )

        # -----------------------------------------------------
        # REACTIVATE PROFILE
        # -----------------------------------------------------

        if not executive.is_active:

            executive.is_active = True

            executive.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

        return executive

    # =========================================================
    # REMOVE EXECUTIVE ROLE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def remove_executive_role(user):
        """
        Remove the executive role from a user.

        The user becomes a Student and the Executive profile
        is retained for historical purposes but deactivated.
        """

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        if not ExecutiveService.is_executive(user):
            return user

        # -----------------------------------------------------
        # CHANGE USER ROLE
        # -----------------------------------------------------

        user.role = User.Role.STUDENT

        update_fields = ["role"]

        if hasattr(user, "updated_at"):
            update_fields.append("updated_at")

        user.save(
            update_fields=update_fields
        )

        # -----------------------------------------------------
        # DEACTIVATE EXECUTIVE PROFILE
        # -----------------------------------------------------

        executive = (
            Executive.objects
            .filter(user=user)
            .first()
        )

        if executive:

            executive.is_active = False

            executive.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

        return user

    # =========================================================
    # UPDATE EXECUTIVE TERM
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_term(
        executive,
        term_start=None,
        term_end=None,
    ):
        """
        Update an executive's leadership term.
        """

        if not executive:
            raise ValueError(
                "A valid executive profile is required."
            )

        if (
            term_start
            and term_end
            and term_end < term_start
        ):
            raise ValueError(
                "The term end date cannot be earlier "
                "than the term start date."
            )

        executive.term_start = term_start
        executive.term_end = term_end

        executive.full_clean(
            exclude=[
                "user",
            ]
        )

        executive.save(
            update_fields=[
                "term_start",
                "term_end",
                "updated_at",
            ]
        )

        return executive

    # =========================================================
    # EXECUTIVE STATISTICS
    # =========================================================

    @staticmethod
    def get_executive_statistics():
        """
        Return executive statistics for the dashboard.

        Statistics distinguish between:

            - Total current executives
            - Currently serving executives
            - Administratively inactive executives
            - Verified executives
            - Unverified executives
            - Upcoming executives
            - Ended terms
        """

        current_queryset = (
            ExecutiveService
            ._executive_queryset()
        )

        active_queryset = (
            ExecutiveService
            .get_active_executives()
        )

        upcoming_queryset = (
            ExecutiveService
            .get_upcoming_executives()
        )

        today = ExecutiveService._today()

        ended_queryset = (
            ExecutiveService
            ._profile_queryset()
            .filter(
                term_end__lt=today
            )
        )

        return {
            "total": current_queryset.count(),

            "active": active_queryset.count(),

            "inactive": current_queryset.filter(
                is_active=False
            ).count(),

            "verified": current_queryset.filter(
                user__is_verified=True
            ).count(),

            "unverified": current_queryset.filter(
                user__is_verified=False
            ).count(),

            "upcoming": upcoming_queryset.count(),

            "ended": ended_queryset.count(),
        }

    # =========================================================
    # CHECK EXECUTIVE
    # =========================================================

    @staticmethod
    def is_executive(user):
        """
        Return True when a user currently holds an official
        KUCSA executive role.
        """

        if not user:
            return False

        return ExecutiveService._is_executive_role(
            getattr(user, "role", None)
        )

    # =========================================================
    # CHECK CURRENTLY SERVING EXECUTIVE
    # =========================================================

    @staticmethod
    def is_current_executive(user):
        """
        Return True only when the user has:

            1. An official executive role
            2. An Executive profile
            3. An active profile
            4. A currently valid leadership term
        """

        if not ExecutiveService.is_executive(user):
            return False

        executive = (
            Executive.objects
            .filter(user=user)
            .first()
        )

        if not executive:
            return False

        return executive.is_current

    # =========================================================
    # ENSURE EXECUTIVE PROFILE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def ensure_executive_profile(user):
        """
        Ensure that a user with an official executive role
        has an Executive profile.

        Existing profiles are returned unchanged.
        """

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        if not ExecutiveService.is_executive(user):
            raise ValueError(
                "The user does not currently have "
                "an official KUCSA executive role."
            )

        executive, created = (
            Executive.objects.get_or_create(
                user=user
            )
        )

        return executive