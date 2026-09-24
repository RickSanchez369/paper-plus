# path: apps/shared/views.py

"""
The frontend shell: the dashboard and the placeholder every module route
renders until Phase C builds it.

Views never write (the rule that used to say "Admin never writes" — money
and stock still go through `apps/*/services.py` inside `transaction.atomic`).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class ModulePlaceholderView(LoginRequiredMixin, TemplateView):
    """
    A route that exists so the sidebar works, saying plainly that its page
    is not built yet.

    Phase B's job is the shell — navigation, login, layout — and every
    module needs a resolvable URL for the sidebar to link to. Rendering an
    honest placeholder is better than a nav full of dead links or a page
    pretending to be empty when it is simply unbuilt.
    """

    template_name = "shared/placeholder.html"

    # Set per route in each app's urls.py.
    title = ""
    description = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.title
        context["page_description"] = self.description
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    The landing page after login (REDESIGN_VISION 4.10).

    A stub until Phase C: the dashboard only aggregates the other modules,
    so it is built last, once there is something true to aggregate. Showing
    invented numbers here would be worse than showing none.
    """

    template_name = "shared/dashboard.html"
