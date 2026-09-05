pip freeze > requirements.txt

python manage.py collectstatic

python manage.py collectstatic --noinput

from accounts.models import User

u = User.objects.create_user(
    username="admin",
    password="@Hublab!1",
    first_name="Kucsa",
    last_name="Association",
    email="computing@gmail.com",
    role="ADMIN",
    is_staff=True,
    is_superuser=True,
    is_active=True,
    is_verified=True,
)






{% extends "base.html" %}

{% load static %}

{% block title %}
    Attendance Sessions | KUCSA Platform
{% endblock %}

{% block content %}

<!-- Custom Styling Injection matching the KUCSA Design System -->
<style>
    :root {
        --kucsa-primary: #0d6efd;
        --kucsa-primary-hover: #0b5ed7;
        --kucsa-bg-gradient: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }

    body {
        background: var(--kucsa-bg-gradient);
    }

    .kucsa-card {
        border-radius: 1rem;
        transition: all 0.2s ease-in-out;
    }

    .metric-card {
        border-radius: 1rem;
        border: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.08) !important;
    }

    .table-hover tbody tr {
        transition: background-color 0.15s ease-in-out;
    }

    .dropdown-menu {
        border-radius: 0.75rem;
        box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.1);
        border: none;
    }

    .quick-action-card {
        border-radius: 1rem;
        transition: all 0.2s ease-in-out;
    }

    .quick-action-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 0.75rem 1.5rem rgba(0, 0, 0, 0.1) !important;
    }
</style>

<div class="container-fluid py-4">

    <!-- ===================================================== -->
    <!-- PAGE HEADER -->
    <!-- ===================================================== -->
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1 text-dark">
                <i class="bi bi-calendar-check-fill text-primary me-2"></i>Attendance Sessions
            </h1>
            <p class="text-muted mb-0">
                Create, monitor, and manage KUCSA member attendance records securely.
            </p>
        </div>

        {% if can_manage %}
            <a href="{% url 'attendance:create' %}" class="btn btn-primary shadow-sm px-4 fw-bold">
                <i class="bi bi-plus-circle-fill me-1"></i>Create Attendance Session
            </a>
        {% endif %}
    </div>


    <!-- ===================================================== -->
    <!-- SUMMARY METRIC CARDS -->
    <!-- ===================================================== -->
    <div class="row g-3 mb-4">

        <!-- Total Sessions -->
        <div class="col-12 col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm h-100 bg-white">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <p class="text-muted small mb-1 fw-semibold text-uppercase tracking-wider">Total Sessions</p>
                            <h3 class="mb-0 fw-bold text-dark">{{ total_sessions|default:0 }}</h3>
                        </div>
                        <div class="bg-primary bg-opacity-10 rounded-circle p-3 d-flex align-items-center justify-content-center text-primary" style="width: 52px; height: 52px;">
                            <i class="bi bi-calendar-check fs-4"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Open Sessions -->
        <div class="col-12 col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm h-100 bg-white">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <p class="text-muted small mb-1 fw-semibold text-uppercase tracking-wider">Open Sessions</p>
                            <h3 class="mb-0 fw-bold text-success">{{ open_sessions|default:0 }}</h3>
                        </div>
                        <div class="bg-success bg-opacity-10 rounded-circle p-3 d-flex align-items-center justify-content-center text-success" style="width: 52px; height: 52px;">
                            <i class="bi bi-broadcast fs-4"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Closed Sessions -->
        <div class="col-12 col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm h-100 bg-white">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <p class="text-muted small mb-1 fw-semibold text-uppercase tracking-wider">Closed Sessions</p>
                            <h3 class="mb-0 fw-bold text-secondary">{{ closed_sessions|default:0 }}</h3>
                        </div>
                        <div class="bg-secondary bg-opacity-10 rounded-circle p-3 d-flex align-items-center justify-content-center text-secondary" style="width: 52px; height: 52px;">
                            <i class="bi bi-lock fs-4"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- My Attendance -->
        <div class="col-12 col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm h-100 bg-white">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <p class="text-muted small mb-1 fw-semibold text-uppercase tracking-wider">My Attendance</p>
                            <a href="{% url 'attendance:my_attendance' %}" class="btn btn-sm btn-outline-primary mt-1 shadow-sm fw-semibold px-3">
                                View History
                            </a>
                        </div>
                        <div class="bg-info bg-opacity-10 rounded-circle p-3 d-flex align-items-center justify-content-center text-info" style="width: 52px; height: 52px;">
                            <i class="bi bi-person-check fs-4"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>


    <!-- ===================================================== -->
    <!-- ACTIVE ATTENDANCE ALERT BANNER -->
    <!-- ===================================================== -->
    {% if active_sessions %}
        <div class="alert alert-success border-0 shadow-sm mb-4 rounded-3 p-4 bg-success bg-opacity-10 text-success border-start border-success border-5">
            <div class="d-flex flex-wrap justify-content-between align-items-center gap-3">
                <div class="d-flex align-items-center">
                    <div class="fs-3 me-3 text-success">
                        <i class="bi bi-broadcast-pin"></i>
                    </div>
                    <div>
                        <strong class="text-dark fs-6">Live Attendance Sessions Active!</strong>
                        <div class="small text-secondary">
                            {{ active_sessions|length }} active attendance session{{ active_sessions|length|pluralize }} currently open for check-in.
                        </div>
                    </div>
                </div>
                <a href="{% url 'attendance:active' %}" class="btn btn-success shadow-sm px-4 fw-bold">
                    View Active Attendance <i class="bi bi-arrow-right ms-1"></i>
                </a>
            </div>
        </div>
    {% endif %}


    <!-- ===================================================== -->
    <!-- FILTERS CARD -->
    <!-- ===================================================== -->
    <div class="card kucsa-card border-0 shadow-sm mb-4 bg-white">
        <div class="card-header bg-transparent border-0 py-3 px-4">
            <div class="d-flex align-items-center text-dark">
                <i class="bi bi-funnel-fill text-primary me-2 fs-5"></i>
                <h5 class="mb-0 fw-bold">Filter Attendance Sessions</h5>
            </div>
        </div>

        <div class="card-body px-4 pb-4 pt-0">
            <form method="get">
                <div class="row g-3">
                    <!-- Search Field -->
                    <div class="col-12 col-md-6">
                        <label for="{{ form.search.id_for_label }}" class="form-label fw-semibold small text-muted">Search Sessions</label>
                        {{ form.search }}
                        {% if form.search.errors %}
                            <div class="text-danger small mt-1">{{ form.search.errors|striptags }}</div>
                        {% endif %}
                    </div>

                    <!-- Status Field -->
                    <div class="col-12 col-md-3">
                        <label for="{{ form.status.id_for_label }}" class="form-label fw-semibold small text-muted">Status</label>
                        {{ form.status }}
                        {% if form.status.errors %}
                            <div class="text-danger small mt-1">{{ form.status.errors|striptags }}</div>
                        {% endif %}
                    </div>

                    <!-- Filter Action Buttons -->
                    <div class="col-12 col-md-3 d-flex align-items-end gap-2">
                        <button type="submit" class="btn btn-primary flex-grow-1 shadow-sm fw-semibold">
                            <i class="bi bi-search me-1"></i>Filter
                        </button>
                        <a href="{% url 'attendance:list' %}" class="btn btn-outline-secondary shadow-sm" title="Reset Filters">
                            <i class="bi bi-arrow-counterclockwise"></i>
                        </a>
                    </div>
                </div>
            </form>
        </div>
    </div>


    <!-- ===================================================== -->
    <!-- SESSIONS TABLE CARD -->
    <!-- ===================================================== -->
    <div class="card kucsa-card border-0 shadow-sm bg-white overflow-hidden mb-4">
        <div class="card-header bg-transparent border-0 py-3 px-4">
            <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <div>
                    <h5 class="mb-0 fw-bold text-dark">Attendance Sessions Directory</h5>
                    <small class="text-muted">{{ session_count|default:0 }} session{{ session_count|default:0|pluralize }} found matching criteria</small>
                </div>

                {% if can_manage %}
                    <a href="{% url 'attendance:create' %}" class="btn btn-sm btn-primary shadow-sm fw-semibold">
                        <i class="bi bi-plus-circle me-1"></i>New Session
                    </a>
                {% endif %}
            </div>
        </div>

        <div class="card-body p-0">
            {% if sessions %}
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light text-uppercase fs-7 text-muted">
                            <tr>
                                <th class="px-4 py-3">#</th>
                                <th class="py-3">Attendance Session</th>
                                <th class="py-3">Status</th>
                                <th class="py-3">Opens</th>
                                <th class="py-3">Closes</th>
                                <th class="py-3">Created</th>
                                <th class="text-end px-4 py-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for session in sessions %}
                                <tr>
                                    <!-- Number -->
                                    <td class="px-4 fw-semibold text-muted">
                                        {{ forloop.counter }}
                                    </td>

                                    <!-- Session Details -->
                                    <td>
                                        <div class="fw-bold text-dark">{{ session.title }}</div>
                                        {% if session.description %}
                                            <div class="small text-muted text-truncate" style="max-width: 320px;">
                                                {{ session.description }}
                                            </div>
                                        {% endif %}
                                    </td>

                                    <!-- Status Badge -->
                                    <td>
                                        {% if session.status == "DRAFT" %}
                                            <span class="badge bg-secondary shadow-sm"><i class="bi bi-pencil me-1"></i>Draft</span>
                                        {% elif session.status == "OPEN" %}
                                            <span class="badge bg-success shadow-sm"><i class="bi bi-broadcast me-1"></i>Open</span>
                                        {% elif session.status == "CLOSED" %}
                                            <span class="badge bg-dark shadow-sm"><i class="bi bi-lock me-1"></i>Closed</span>
                                        {% elif session.status == "EXPIRED" %}
                                            <span class="badge bg-warning text-dark shadow-sm"><i class="bi bi-clock-history me-1"></i>Expired</span>
                                        {% else %}
                                            <span class="badge bg-secondary shadow-sm">{{ session.get_status_display }}</span>
                                        {% endif %}
                                    </td>

                                    <!-- Opens At -->
                                    <td>
                                        {% if session.opens_at %}
                                            <div class="fw-semibold text-dark">{{ session.opens_at|date:"d M Y" }}</div>
                                            <small class="text-muted">{{ session.opens_at|time:"H:i" }}</small>
                                        {% else %}
                                            <span class="text-muted">—</span>
                                        {% endif %}
                                    </td>

                                    <!-- Closes At -->
                                    <td>
                                        {% if session.closes_at %}
                                            <div class="fw-semibold text-dark">{{ session.closes_at|date:"d M Y" }}</div>
                                            <small class="text-muted">{{ session.closes_at|time:"H:i" }}</small>
                                        {% else %}
                                            <span class="text-muted">—</span>
                                        {% endif %}
                                    </td>

                                    <!-- Created At -->
                                    <td>
                                        {% if session.created_at %}
                                            <div class="text-dark">{{ session.created_at|date:"d M Y" }}</div>
                                            <small class="text-muted">{{ session.created_at|time:"H:i" }}</small>
                                        {% else %}
                                            <span class="text-muted">—</span>
                                        {% endif %}
                                    </td>

                                    <!-- Actions Dropdown -->
                                    <td class="text-end px-4">
                                        <div class="dropdown">
                                            <button class="btn btn-sm btn-outline-secondary dropdown-toggle shadow-sm px-3 fw-semibold" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                                Actions
                                            </button>
                                            <ul class="dropdown-menu dropdown-menu-end shadow-sm py-2">
                                                <li>
                                                    <a class="dropdown-item py-2" href="{% url 'attendance:detail' session.pk %}">
                                                        <i class="bi bi-eye me-2 text-primary"></i>View Attendance
                                                    </a>
                                                </li>
                                                {% if session.status == "DRAFT" and can_manage %}
                                                    <li>
                                                        <a class="dropdown-item py-2" href="{% url 'attendance:update_timing' session.pk %}">
                                                            <i class="bi bi-clock me-2 text-warning"></i>Set Timing
                                                        </a>
                                                    </li>
                                                {% endif %}
                                                {% if session.attendance_is_open %}
                                                    <li>
                                                        <a class="dropdown-item py-2" href="{% url 'attendance:active_status' session.pk %}">
                                                            <i class="bi bi-broadcast me-2 text-success"></i>Active Session
                                                        </a>
                                                    </li>
                                                {% endif %}
                                            </ul>
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <!-- Empty State -->
                <div class="text-center py-5 px-3">
                    <div class="mb-3">
                        <div class="bg-light rounded-circle d-inline-flex p-4 text-muted shadow-sm">
                            <i class="bi bi-calendar-x fs-1"></i>
                        </div>
                    </div>
                    <h5 class="fw-bold text-dark">No Attendance Sessions Found</h5>
                    <p class="text-muted mb-4">There are currently no attendance sessions matching your search query or filter parameters.</p>
                    {% if can_manage %}
                        <a href="{% url 'attendance:create' %}" class="btn btn-primary shadow-sm px-4 fw-bold">
                            <i class="bi bi-plus-circle me-1"></i>Create First Attendance Session
                        </a>
                    {% endif %}
                </div>
            {% endif %}
        </div>
    </div>


    <!-- ===================================================== -->
    <!-- QUICK ACTIONS FOOTER CARDS -->
    <!-- ===================================================== -->
    {% if can_manage %}
        <div class="row g-3 mt-4">
            <div class="col-12 col-md-4">
                <a href="{% url 'attendance:create' %}" class="text-decoration-none">
                    <div class="card quick-action-card border-0 shadow-sm h-100 bg-white">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center">
                                <div class="bg-primary bg-opacity-10 rounded-3 p-3 me-3 text-primary">
                                    <i class="bi bi-plus-circle fs-4"></i>
                                </div>
                                <div>
                                    <h6 class="mb-1 fw-bold text-dark">Create Session</h6>
                                    <small class="text-muted">Start a new member attendance session.</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </a>
            </div>

            <div class="col-12 col-md-4">
                <a href="{% url 'attendance:active' %}" class="text-decoration-none">
                    <div class="card quick-action-card border-0 shadow-sm h-100 bg-white">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center">
                                <div class="bg-success bg-opacity-10 rounded-3 p-3 me-3 text-success">
                                    <i class="bi bi-broadcast fs-4"></i>
                                </div>
                                <div>
                                    <h6 class="mb-1 fw-bold text-dark">Active Attendance</h6>
                                    <small class="text-muted">Monitor currently open live sessions.</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </a>
            </div>

            <div class="col-12 col-md-4">
                <a href="{% url 'attendance:report' %}" class="text-decoration-none">
                    <div class="card quick-action-card border-0 shadow-sm h-100 bg-white">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center">
                                <div class="bg-info bg-opacity-10 rounded-3 p-3 me-3 text-info">
                                    <i class="bi bi-bar-chart-fill fs-4"></i>
                                </div>
                                <div>
                                    <h6 class="mb-1 fw-bold text-dark">Attendance Reports</h6>
                                    <small class="text-muted">Analyze and export attendance analytics.</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </a>
            </div>
        </div>
    {% endif %}

</div>


<!-- ========================================================= -->
<!-- AUTOMATED CSS CLASS INJECTOR JAVASCRIPT -->
<!-- ========================================================= -->
<script>
    document.addEventListener("DOMContentLoaded", function() {
        const textInputs = document.querySelectorAll('input[type="text"], input[type="search"], input[type="email"], input[type="url"], input[type="number"]');
        const selectInputs = document.querySelectorAll('select');

        textInputs.forEach(el => {
            if (!el.classList.contains('form-control')) el.classList.add('form-control', 'shadow-sm');
        });

        selectInputs.forEach(el => {
            if (!el.classList.contains('form-select')) el.classList.add('form-select', 'shadow-sm');
        });
    });
</script>

{% endblock %}